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

# 🎯 新增：失效死机源输出路径（存放在 md/ 文件夹下）
MD_DIR = os.path.join(WORKSPACE, "md")
DEAD_TXT = os.path.join(MD_DIR, "dead_hosts.txt")
# ==========================================================

TIMEOUT = 10 
MAX_WORKERS = 150 
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def check_url(url):
    try:
        # 允许自动处理重定向 allow_redirects=True
        r = requests.get(url.replace('&amp;', '&'), headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True)
        # 放宽状态码限制，只要不是明确的 4xx 错误或 5xx 错误，或者属于常见可用状态码
        return url if r.status_code in [200, 206, 301, 302] else None
    except Exception as e:
        # 如果你想调试，可以把报错打印出来看看它究竟是因为超时还是被拒绝
        # print(f"DEBUG 报错: {url} -> {e}")
        return None
        return None

def extract_from_m3u(file_path):
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
    return {"host": host, "channels": channels}

def save_realtime(host, channels, tag=""):
    with open(RESULT_TXT, "a", encoding="utf-8") as f:
        f.write(f"{host},#genre#\n")
        for c in channels:
            f.write(f"{c['name']},http://{host}{c['path']}\n")
        f.write("\n")
    print(f"✨ [{tag}] 已上线: {host}", flush=True)

    
def run_scan():
    if os.path.exists(RESULT_TXT):
        os.path.remove(RESULT_TXT)
    
    print(f"📂 正在聚合原始基因，目标防区: {HOTEL_DIR}", flush=True)
    if not os.path.exists(HOTEL_DIR):
        print(f"❌ 致命错误: 找不到原始种子目录 {HOTEL_DIR}", flush=True)
        sys.exit(1)

    all_genes = {}
    m3u_files = [f for f in os.listdir(HOTEL_DIR) if f.lower().endswith(".m3u")]
    for f in m3u_files:
        gene = extract_from_m3u(os.path.join(HOTEL_DIR, f))
        if gene:
            all_genes[gene['host']] = gene['channels']

    final_live_hosts = set()
    
    # 🎯 改进点 1：不管第一阶段成败，直接提取所有种子对应的“网段 (C段) 与 端口”
    # 这样可以确保类似 139.214.181.x 的整个网段都会被纳入轰炸区，不会漏掉同网段的可用 IP
    target_nets = {} # 格式: { "139.214.181:9901": channels, ... }

    print(f"⚡ 阶段 1: 快速探测 {len(all_genes)} 个原始 IP 的健康状态...", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_host = {
            executor.submit(check_url, f"http://{h}{c[0]['path']}"): (h, c) 
            for h, c in all_genes.items()
        }
        for future in concurrent.futures.as_completed(future_to_host):
            host, channels = future_to_host[future]
            if future.result():
                save_realtime(host, channels, tag="现成")
                final_live_hosts.add(host)

    # 🎯 改进点 2：无论第一阶段命中与否，把所有原始基因的 C 段全部收集起来准备进行全方位扫描
    for host, channels in all_genes.items():
        ip_part = host.split(':')[0]
        ip_pieces = ip_part.split('.')
        if len(ip_pieces) == 4:
            prefix = ".".join(ip_pieces[:3]) # 例如 139.214.181
            port = host.split(':')[1] if ':' in host else "80"
            net_key = f"{prefix}:{port}"
            if net_key not in target_nets:
                target_nets[net_key] = channels

    print(f"\n📡 阶段 2: 启动 C 段全覆盖深度扫描 (共计锁定 {len(target_nets)} 个独特网段，开始 0-255 毯式轰炸)...", flush=True)
    
    completely_dead_hosts = []
    processed_nets = set()

    for net_key, channels in target_nets.items():
        prefix, port = net_key.split(':')
        
        if prefix in processed_nets:
            continue
        processed_nets.add(prefix)
        
        print(f"🔍 正在地毯式扫荡网段: {prefix}.1-254 端口 {port}...", flush=True)
        
        # 构造该网段从 1 到 254 的所有 IP 组合
        scan_urls = [f"http://{prefix}.{i}:{port}{channels[0]['path']}" for i in range(1, 255)]
        
        net_rescued = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(check_url, url): url for url in scan_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                res_url = future.result()
                if res_url:
                    new_host = urlparse(res_url).netloc
                    if new_host not in final_live_hosts:
                        save_realtime(new_host, channels, tag="网段捕获")
                        final_live_hosts.add(new_host)
                        net_rescued = True

        # 如果整个网段 1-254 全部挂掉，才记录为彻底失效源
        if not net_rescued:
            # 顺便把该网段代表性的 host 记录进去
            completely_dead_hosts.append(f"{prefix}.x:{port}")

    # 保存失效清单
    os.makedirs(MD_DIR, exist_ok=True)
    with open(DEAD_TXT, "w", encoding="utf-8") as f_dead:
        f_dead.write("# ==========================================\n")
        f_dead.write("# ❌ 全网段扫描后仍无响应的死机网段/IP汇总\n")
        f_dead.write("# ==========================================\n")
        for dead_host in sorted(list(set(completely_dead_hosts))):
            f_dead.write(f"{dead_host}\n")
            
    print(f"\n✅ 智能全网段深度扫描结束！有效大表已生成: {RESULT_TXT}", flush=True)
    print(f"🗑️ 彻底死机的网段清单已同步写入: {DEAD_TXT}", flush=True)

if __name__ == "__main__":
    run_scan()
