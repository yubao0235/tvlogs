import os, requests, re, sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")

TIMEOUT = 3

def check_url(url):
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except: return False

def main():
    if not os.path.exists(MANUAL_FIX): return

    with open(MANUAL_FIX, 'r', encoding='utf-8') as f:
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]
    
    revived_list, dead_list = [], []
    
    for idx, block in enumerate(blocks):
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 2: continue
        
        base_host = lines[0].split(',')[0].strip()
        test_url = lines[1].split(',', 1)[1].strip()
        
        print(f"[{idx+1}/{len(blocks)}] ⚖️ 体检: {base_host}", flush=True)
        
        if check_url(test_url):
            print("  ✅ 存活", flush=True)
            revived_list.append(block + "\n\n")
        else:
            print("  💀 失效 -> 送入抢救队列", flush=True)
            dead_list.append(block + "\n\n")

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived_list)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead_list)

if __name__ == "__main__":
    main()
