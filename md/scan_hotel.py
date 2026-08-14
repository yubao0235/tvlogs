import os
import re
import requests
import concurrent.futures
import sys
from urllib.parse import urlparse

# ================= ⚡ 跨库核心动态路径锁定 =================
WORKSPACE = os.environ.get("LIVE_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOTEL_DIR = os.path.join(WORKSPACE, "hotel")         # 指向私库下的 hotel 文件夹
RESULT_TXT = os.path.join(WORKSPACE, "hotel_output.txt") # 扫描临时大表存放在私库根目录

# 失效死机源输出路径（存放在 md/ 文件夹下）
MD_DIR = os.path.join(WORKSPACE, "md")
DEAD_TXT = os.path.join(MD_DIR, "dead_hosts.txt")
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
    """提取 M3U 内容，并顺便把原文件名（如 吉林长春_139.214.178.118_9901）作为核心标签返回"""
    filename = os.path.basename(file_path)
    tag = os.path.splitext(filename)[0] # 去掉 .m3u 后缀，完美保留原文件名
    
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
    """写入大表时，格式升级为: 标签名|主机IP|频道列表... 方便下游直接读取文件名"""
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
        print(f"🛡️ 成功加载历史死机黑名单，共计载入并规范化 {len(dead_set)} 条记录。", flush=True)
    return dead_set

def run_scan():
    if os.path.exists(RESULT_TXT):
        os.path.exists(RESULT_TXT) and os.remove(RESULT_TXT)
     
    print(f"📂 正在聚合原始基因，目标防区: {HOTEL_DIR}", flush=True)
    if not os.path.exists(HOTEL_DIR):
        print(f"❌ 致命错误: 找不到原始种子目录 {HOTEL_DIR}", flush=True)
        sys.exit(1)

    historical_dead_sets = load_dead_hosts()

    all_genes = {} # key: host, value: {"tag": tag, "channels": channels}
    m3u_files = [f for f in os.listdir(HOTEL_DIR) if f.lower().endswith(".m3u")]
    for f in m3u_files:
        gene = extract_from_m3u(os.path.join(HOTEL_DIR, f))
        if gene:
            all_genes[gene['host']] = {"tag": gene['tag'], "channels": gene['channels']}

    final_live_hosts = set()
    target_nets = {} 

    print(f"⚡ 阶段 1: 快速探测 {len(all_genes)} 个原始 IP 的健康状态...", flush=True)
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

    # 按照 IP 前三位归类
    for host, data in all_genes.items():
        ip_part = host.split(':')[0]
        ip_pieces = ip_part.split('.')
        if len(ip_pieces) == 4:
            prefix = ".".join(ip_pieces[:3]) 
            port = host.split(':')[1] if ':' in host else "80"
            net_key = f"{prefix}:{port}"
            if net_key not in target_nets:
                target_nets[net_key] = data

    valid_scan_nets = []
    skipped_count = 0
    processed_nets = set()

    for net_key, data in target_nets.items():
        if net_key in processed_nets:
            continue
        processed_nets.add(net_key)

        if net_key in historical_dead_sets:
            skipped_count += 1
            continue
            
        valid_scan_nets.append((net_key, data))

    print(f"\n📡 阶段 2: 启动 C 段全覆盖深度扫描...", flush=True)
    print(f"📈 统计面板 -> 原始归并网段: {len(target_nets)} 个 | 🛡️ 命中黑名单跳过: {skipped_count} 个 | 🚀 实际待深度扫描网段: {len(valid_scan_nets)} 个", flush=True)

    current_scan_dead_hosts = []

    for net_key, data in valid_scan_nets:
        prefix, port = net_key.split(':')
        tag = data['tag']
        channels = data['channels']
        
        print(f"🔍 正在地毯式扫荡网段 ({tag}): {prefix}.1-254 端口 {port}...", flush=True)
        
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
            
    print(f"\n✅ 智能全网段深度扫描结束！有效大表已生成: {RESULT_TXT}", flush=True)

if __name__ == "__main__":
    run_scan()
