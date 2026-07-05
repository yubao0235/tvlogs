import os, sys, requests, re, concurrent.futures
from urllib.parse import urlparse

# --- 路径配置区 ---
# 获取当前脚本所在目录 (即 md 文件夹)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 你的底库现在就在 md 文件夹内
LOCAL_BASE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt")
# 原始抓取源通常在根目录 (md 的上一级)
INPUT_RAW = os.path.join(os.path.dirname(CURRENT_DIR), "tvbox_output.txt")

# 中转文件也放在 md 文件夹内，防止根目录混乱
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")

TIMEOUT = 3
MAX_WORKERS = 30

def is_valid_ip(ip_str):
    """校验 IP:Port 或 域名:Port 格式"""
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def main():
    ip_map = {} # 结构: { "IP:Port": { "频道名": "URL" } }

    # 打印路径确认，方便在 Actions 日志中排查
    print(f"📂 正在定位底库: {LOCAL_BASE}", flush=True)
    if os.path.exists(LOCAL_BASE):
        print(f"📏 底库文件大小: {os.path.getsize(LOCAL_BASE)} bytes", flush=True)
    else:
        print(f"⚠️ 警告：未在 md 目录下找到 aggregated_hotel.txt！", flush=True)

    def load_data(path, label):
        if not os.path.exists(path): return
        print(f"📖 正在从 [{label}] 加载基因...", flush=True)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            cur_ip = None
            for line in f:
                line = line.strip()
                if not line: continue
                if "#genre#" in line:
                    potential_ip = line.split(',')[0].strip()
                    if is_valid_ip(potential_ip):
                        cur_ip = potential_ip
                        if cur_ip not in ip_map: ip_map[cur_ip] = {}
                    else: cur_ip = None
                    continue
                if ',' in line and cur_ip:
                    name, url = line.split(',', 1)
                    # 关键：优先保护已存在的内容 (底库内容)
                    name_s, url_s = name.strip(), url.strip()
                    if name_s not in ip_map[cur_ip]:
                        ip_map[cur_ip][name_s] = url_s

    # ！！！加载顺序：1.底库(md/) 2.新源(根目录) ！！！
    load_data(LOCAL_BASE, "MD底库(含手动修改)")
    load_data(INPUT_RAW, "根目录新源")

    all_ips = list(ip_map.keys())
    total_ips = len(all_ips)
    
    if total_ips == 0:
        print("❌ 错误：未加载到任何有效 IP，请检查文件内容和路径！", flush=True)
        return

    print(f"📡 共有 {total_ips} 个 IP 网段参与探测...", flush=True)

    revived, dead = [], []
    processed = 0

    def check(ip):
        try:
            first_name = list(ip_map[ip].keys())[0]
            test_url = ip_map[ip][first_name]
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"Mozilla/5.0"})
            return ip, r.status_code == 200
        except: return ip, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(check, ip): ip for ip in all_ips}
        for f in concurrent.futures.as_completed(futures):
            processed += 1
            ip, ok = f.result()
            
            # 重组文件块
            block_content = f"{ip},#genre#\n"
            for name, url in ip_map[ip].items():
                block_content += f"{name},{url}\n"
            block_content += "\n"
            
            if ok:
                revived.append(block_content)
                print(f"[{processed}/{total_ips}] ✅ [存活] {ip}", flush=True)
            else:
                dead.append(block_content)
                print(f"[{processed}/{total_ips}] 💀 [失效] {ip}", flush=True)

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead)
    print(f"📊 探测完成。存活: {len(revived)} | 待抢救: {len(dead)}", flush=True)

if __name__ == "__main__":
    main()
