import os
import re
import requests
import concurrent.futures
import sys
from urllib.parse import urlparse

# ================= ⚡ 跨库核心动态路径锁定 =================
WORKSPACE = os.environ.get("LIVE_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOTEL_DIR = os.path.join(WORKSPACE, "hotel")          # 指向私库下的 hotel 文件夹
RESULT_TXT = os.path.join(WORKSPACE, "hotel_output.txt") # 扫描临时大表存放在私库根目录

# 黑白名单输出路径（存放在 md/ 文件夹下）
MD_DIR = os.path.join(WORKSPACE, "md")
DEAD_TXT = os.path.join(MD_DIR, "dead_hosts.txt")
WHITE_TXT = os.path.join(MD_DIR, "white_hosts.txt")    # 🌟 活跃网段白名单
# ==========================================================

TIMEOUT = 3 
MAX_WORKERS = 150 
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def check_url(url):
    try:
        r = requests.get(url.replace('&amp;', '&'), headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True)
        return url if r.status_code in [200, 206, 301, 302] else None
    except Exception as e:
        return None

def extract_from_m3u(file_path):
    """提取 M3U 内容，并顺便把原文件名作为核心标签返回"""
    filename = os.path.basename(file_path)
    tag = os.path.splitext(filename)[0]
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    pattern = r'#EXTINF:.*?,(.*?)\n(https?://[^\s,\"\']+)'
    items = re.findall(pattern, content)
    if not items:
        return None
    first_url = items[0][1].replace('&amp;', '&')
    host = urlparse(first_url).netloc
    channels = []
    for name, url in items:
        p = urlparse(url.replace('&amp;', '&'))
        channels.append({"name": name.strip(), "path": p.path + (f"?{p.query}" if p.query else "")})
    return {"tag": tag, "host": host, "channels": channels}

def save_realtime(tag, host, channels):
    with open(RESULT_TXT, "a", encoding="utf-8") as f:
        f.write(f"{tag}|{host},#genre#\n")
        for c in channels:
            f.write(f"{c['name']},http://{host}{c['path']}\n")
        f.write("\n")
    print(f"✨ [{tag}] 已上线: {host}", flush=True)

def load_dead_hosts():
    dead_set = set()
    if os.path.exists(DEAD_TXT):
        with open(DEAD_TXT, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    normalized_line = line.replace(".x", "")
                    dead_set.add(normalized_line)
        print(f"🛡️ 成功加载历史死机黑名单，共计载入 {len(dead_set)} 条记录。", flush=True)
    else:
        print(f"ℹ️ 未发现黑名单文件 {DEAD_TXT}，本次将全新初始化。", flush=True)
    return dead_set

def load_white_hosts():
    """加载历史成功的白名单网段（如 1.196.157.*:999）"""
    white_nets = {} # key: net_key (1.196.157:999), value: 原始内容行
    if os.path.exists(WHITE_TXT):
        with open(WHITE_TXT, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(":")
                    if len(parts) == 2:
                        net_prefix = parts[0].replace(".*", "") # 变成 1.196.157
                        port = parts[1]
                        net_key = f"{net_prefix}:{port}"
                        white_nets[net_key] = line
        print(f"🌟 成功加载历史活跃白名单网段，共计载入 {len(white_nets)} 个。", flush=True)
    else:
        print(f"ℹ️ 未发现白名单文件 {WHITE_TXT}，将在本次扫描结束后自动生成。", flush=True)
    return white_nets

def save_white_hosts(all_live_hosts):
    """把本次扫描成功出过结果的网段归纳并沉淀到 white_hosts.txt"""
    white_set = set()
    if os.path.exists(WHITE_TXT):
        with open(WHITE_TXT, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    white_set.add(line)
                    
    for host in all_live_hosts:
        ip_part, port = host.split(':')
        ip_pieces = ip_part.split('.')
        if len(ip_pieces) == 4:
            c_prefix = ".".join(ip_pieces[:3])
            white_set.add(f"{c_prefix}.*:{port}")
            
    os.makedirs(MD_DIR, exist_ok=True)
    with open(WHITE_TXT, "w", encoding="utf-8") as f:
        f.write("# ==========================================\n")
        f.write("# 🌟 历史验证有效的酒店 IPTV 活跃网段白名单\n")
        f.write("# ==========================================\n")
        for w in sorted(list(white_set)):
            f.write(f"{w}\n")

def run_scan():
    if os.path.exists(RESULT_TXT):
        os.remove(RESULT_TXT)
     
    print(f"📂 正在聚合原始基因，目标防区: {HOTEL_DIR}", flush=True)
    if not os.path.exists(HOTEL_DIR):
        print(f"❌ 致命错误: 找不到原始种子目录 {HOTEL_DIR}", flush=True)
        sys.exit(1)

    historical_dead_sets = load_dead_hosts()
    historical_white_nets = load_white_hosts()

    all_genes = {} # key: host, value: {"tag": tag, "channels": channels}
    
    # 1. 从 m3u 文件加载基因
    m3u_files = [f for f in os.listdir(HOTEL_DIR) if f.lower().endswith(".m3u")]
    for f in m3u_files:
        gene = extract_from_m3u(os.path.join(HOTEL_DIR, f))
        if gene:
            all_genes[gene['host']] = {"tag": gene['tag'], "channels": gene['channels']}

    final_live_hosts = set()
    target_nets = {} # key: net_key (1.196.157:999), value: data

    # 2. 🌟 优先注入白名单网段（确保白名单内的网段强行加入待扫池）
    for net_key, white_line in historical_white_nets.items():
        prefix, port = net_key.split(':')
        sample_channel_path = "/iptv/live/1000.m3u"
        sample_tag = f"白名单网段_{prefix}.*"
        # 尝试在现有基因中找一个同端口的频道路径作为爆破模版
        for h, d in all_genes.items():
            if h.endswith(f":{port}"):
                sample_channel_path = d['channels'][0]['path']
                sample_tag = d['tag']
                break
        target_nets[net_key] = {
            "tag": sample_tag,
            "channels": [{"path": sample_channel_path}]
        }

    # 3. 再把 m3u 里的网段收录/合并进待扫池（m3u 实时性更高，可覆盖或扩充）
    for host, data in all_genes.items():
        ip_part = host.split(':')
        ip_pieces = ip_part[0].split('.')
        if len(ip_pieces) == 4:
            prefix = ".".join(ip_pieces[:3])
            port = ip_part[1] if len(ip_part) > 1 else "80"
            net_key = f"{prefix}:{port}"
            target_nets[net_key] = data

    print(f"⚡ 阶段 1: 快速探测原始基因库健康状态...", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_host = {
            executor.submit(check_url, f"http://{h}{data['channels'][0]['path']}"): (h, data) 
            for h, data in all_genes.items()
        }
        for future in concurrent.futures.as_completed(future_to_host):
            host, data = future_to_host[future]
            if future.result():
                save_realtime(data['tag'], host, data['channels'])
                final_live_hosts.add(host)

    # 4. 过滤黑名单，编排最终待深度扫描的网段（🌟 引入白名单绝对豁免机制）
    valid_scan_nets = []
    skipped_count = 0
    processed_nets = set()

    for net_key, data in target_nets.items():
        if net_key in processed_nets:
            continue
        processed_nets.add(net_key)

        # 🌟 核心豁免：如果该网段在历史白名单中，特赦放行，绝不因黑名单被拦截！
        if net_key in historical_white_nets:
            valid_scan_nets.append((net_key, data))
            continue

        # 不在白名单中的普通网段，才走死机黑名单拦截
        if net_key in historical_dead_sets:
            skipped_count += 1
            continue
            
        valid_scan_nets.append((net_key, data))

    print(f"\n📡 阶段 2: 启动 C 段全覆盖深度扫描...", flush=True)
    print(f"📈 统计面板 -> 合并后待扫网段: {len(target_nets)} 个 | 🛡️ 命中黑名单跳过: {skipped_count} 个 | 🚀 实际深度扫描网段: {len(valid_scan_nets)} 个", flush=True)

    current_scan_dead_hosts = []

    for net_key, data in valid_scan_nets:
        prefix, port = net_key.split(':')
        tag = data['tag']
        channels = data['channels']
        
        clean_display_tag = re.sub(r'\d+\.\d+\.\d+\.\d+', f'{prefix}.*', tag)
        print(f"🔍 正在地毯式扫荡网段: {clean_display_tag} (端口 {port})...", flush=True)
        
        scan_urls = [f"http://{prefix}.{i}:{port}{channels[0]['path']}" for i in range(1, 255)]
        
        net_rescued = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(check_url, url): url for url in scan_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                res_url = future.result()
                if res_url:
                    new_host = urlparse(res_url).netloc
                    if new_host not in final_live_hosts:
                        save_realtime(tag, new_host, channels)
                        final_live_hosts.add(new_host)
                        net_rescued = True

        if not net_rescued:
            current_scan_dead_hosts.append(net_key)

    # 5. 更新并保存黑名单 dead_hosts.txt
    os.makedirs(MD_DIR, exist_ok=True)
    formatted_current_deads = {f"{k.split(':')[0]}.x:{k.split(':')[1]}" for k in current_scan_dead_hosts}
    all_dead_set = historical_dead_sets.union(formatted_current_deads)
    
    with open(DEAD_TXT, "w", encoding="utf-8") as f_dead:
        f_dead.write("# ==========================================\n")
        f_dead.write("# ❌ 全网段扫描后仍无响应的死机网段/IP汇总\n")
        f_dead.write("# ==========================================\n")
        for dead_host in sorted(list(all_dead_set)):
            if ".x:" not in dead_host and ":" in dead_host:
                parts = dead_host.split(':')
                dead_host = f"{parts[0]}.x:{parts[1]}"
            f_dead.write(f"{dead_host}\n")

    # 6. 自动提炼并滚动更新白名单 white_hosts.txt
    save_white_hosts(final_live_hosts)
            
    print(f"\n✅ 智能全网段深度扫描结束！有效大表已生成: {RESULT_TXT}", flush=True)

if __name__ == "__main__":
    run_scan()
