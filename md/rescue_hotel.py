import os, requests, re, concurrent.futures
from urllib.parse import urlparse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")
OUTPUT_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")

TIMEOUT = 4 
MAX_WORKERS = 60

def check_url(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True)
        return r.status_code == 200
    except: return False

def main():
    if not os.path.exists(INPUT_DEAD) or os.path.getsize(INPUT_DEAD) == 0:
        print("🚑 没有待抢救的任务。", flush=True)
        return

    with open(INPUT_DEAD, 'r', encoding='utf-8') as f:
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]

    rescued_blocks = []
    for idx, block in enumerate(blocks):
        lines = block.split('\n')
        old_ip = lines[0].split(',')[0].strip()
        
        # --- 修复逻辑：必须包含冒号且符合 IP 结构 ---
        if ':' not in old_ip or not re.match(r'^\d', old_ip):
            print(f"[{idx+1}/{len(blocks)}] ⚠️ 跳过非 IP 格式: {old_ip}", flush=True)
            continue

        print(f"[{idx+1}/{len(blocks)}] 🔎 爆破抢救: {old_ip}", flush=True)
        
        try:
            ip_part, port = old_ip.split(':')
            prefix = ".".join(ip_part.split('.')[:3])
            path = urlparse(lines[1].split(',')[1]).path
            
            tasks = [f"http://{prefix}.{i}:{port}{path}" for i in range(1, 256)]
            new_host = None
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                fut_to_url = {exe.submit(check_url, u): u for u in tasks}
                for fut in concurrent.futures.as_completed(fut_to_url):
                    if fut.result():
                        new_host = urlparse(fut_to_url[fut]).netloc
                        break
            
            if new_host:
                print(f"  ✨ 成功: {new_host}", flush=True)
                res = f"{new_host},#genre#\n"
                for l in lines[1:]:
                    if ',' in l:
                        name, url = l.split(',', 1)
                        res += f"{name},http://{new_host}{urlparse(url).path}\n"
                rescued_blocks.append(res + "\n\n")
            else:
                print("  ❌ 失败", flush=True)
        except Exception as e:
            print(f"  ⚠️ 错误: {e}", flush=True)

    with open(OUTPUT_RESCUED, 'w', encoding='utf-8') as f:
        f.writelines(rescued_blocks)

if __name__ == "__main__":
    main()
