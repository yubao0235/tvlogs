import os
import json
import time
import random
import re
import requests
import urllib3
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# 禁用 urllib3 的 InsecureRequestWarning 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

workspace = os.environ.get('LIVE_WORKSPACE', '.')

# 🎯 路径对齐：统一使用前面定义好的变量名
SOURCE_M3U = os.path.join(workspace, "hotels/ALL.m3u")
OUTPUT_JSON = os.path.join(workspace, "md/traffic_summary.json")
OUTPUT_TXT = os.path.join(workspace, "md/traffic_report.txt")
dead_hosts_path = os.path.join(workspace, "md/dead_hosts.txt")

# 确保目标输出目录存在
os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

TEST_DURATION = 8    
SAMPLES_PER_IP = 2  
MAX_WORKERS = 8     

def test_stream_traffic(name, url):
    ip_port = urlparse(url).netloc
    start_time = time.time()
    total_bytes = 0
    speeds_mbps = []
    headers = {'User-Agent': 'Mozilla/5.0 (Viera; rv:34.0) Gecko/20100101 Firefox/34.0'}
    
    try:
        with requests.get(url, timeout=4, headers=headers, verify=False, stream=True) as r:
            if r.status_code != 200:
                return None
            playlist_text = r.text

        lines = playlist_text.split('\n')
        base_dir = url.rsplit('/', 1)[0]
        ts_lines = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
        if not ts_lines:
            return None

        while time.time() - start_time < TEST_DURATION:
            target_ts = ts_lines[-2:] if len(ts_lines) > 2 else ts_lines
            for ts_path in target_ts:
                if time.time() - start_time > TEST_DURATION:
                    break
                ts_url = ts_path if ts_path.startswith('http') else f"{base_dir}/{ts_path}"
                ts_start = time.time()
                try:
                    with requests.get(ts_url, timeout=(3, 5), headers=headers, stream=True, verify=False) as ts_r:
                        if ts_r.status_code != 200:
                            continue
                        chunk_bytes = 0
                        for chunk in ts_r.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                chunk_bytes += len(chunk)
                                total_bytes += len(chunk)
                            if time.time() - start_time > TEST_DURATION or (time.time() - ts_start > 3):
                                break
                    
                    ts_duration = time.time() - ts_start
                    if ts_duration > 0 and chunk_bytes > 4096:
                        mbps = (chunk_bytes * 8) / (ts_duration * 1024 * 1024)
                        speeds_mbps.append(mbps)
                except:
                    continue
            time.sleep(0.3)
    except:
        return None

    test_time = time.time() - start_time
    if test_time > 0 and speeds_mbps:
        avg_speed = (total_bytes * 8) / (test_time * 1024 * 1024)
        max_speed = max(speeds_mbps)
        min_speed = min(speeds_mbps)
        stability = 1 - ((max_speed - min_speed) / avg_speed) if avg_speed > 0 else 0
        stability = max(0, min(1, stability))
        
        return {
            "name": name, "ip_port": ip_port,
            "avg_mbps": round(avg_speed, 2), "max_mbps": round(max_speed, 2),
            "stability": round(stability, 2)
        }
    return None

def save_reports(results, group_summary):
    os.makedirs(os.path.dirname(OUTPUT_TXT), exist_ok=True)
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write("="*75 + "\n")
        f.write(f"📡 IPTV 酒店源测速报告 | 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*75 + "\n")
        f.write(f"{'服务器 (IP:Port)':<25} | {'频道':<15} | {'速度':<12} | {'稳定性'}\n")
        f.write("-" * 75 + "\n")
        for res in results:
            f.write(f"{res['ip_port']:<25} | {res['name'][:12]:<15} | {res['avg_mbps']:>6} Mbps | {res['stability']*100:>3.0f}%\n")
        
        f.write("\n📊 综合汇总 (Summary):\n")
        for ip, summ in group_summary.items():
            f.write(f"{ip:<25} | 有效频道:{summ['alive_count']} | 平均:{summ['avg_mbps']:>5} Mbps\n")

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({"summary": group_summary, "details": results}, f, ensure_ascii=False, indent=2)

def main():
    print(f"🚀 启动流媒体全自动测速引擎...", flush=True)
    print(f"📂 正在读取成品大表: {SOURCE_M3U}", flush=True)
    
    if not os.path.exists(SOURCE_M3U):
        print(f"❌ 错误: 找不到源文件 {SOURCE_M3U}，测速被迫中断。", flush=True)
        return

    with open(SOURCE_M3U, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    groups = {}
    lines = content.split('\n')
    for i in range(len(lines)):
        if lines[i].startswith('#EXTINF') and i+1 < len(lines):
            url = lines[i+1].strip()
            if url.startswith('http'):
                ip_port = urlparse(url).netloc
                if ip_port not in groups:
                    groups[ip_port] = []
                name_match = re.search(r',(.+)$', lines[i])
                name = name_match.group(1).strip() if name_match else "Unknown"
                groups[ip_port].append((name, url))

    tasks = []
    for ip_port, urls in groups.items():
        samples = random.sample(urls, min(len(urls), SAMPLES_PER_IP))
        tasks.extend(samples)

    print(f"📡 识别到 {len(groups)} 个有效网段，随机抽取 {len(tasks)} 个流样本进行压测...", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_stream_traffic, n, u) for n, u in tasks]
        for future in futures:
            res = future.result()
            if res:
                results.append(res)

    group_summary = {}
    for res in results:
        ip = res['ip_port']
        if ip not in group_summary:
            group_summary[ip] = {"alive_count": 0, "speeds": [], "max_mbps": 0}
        s = group_summary[ip]
        s["alive_count"] += 1
        s["speeds"].append(res['avg_mbps'])
        s["max_mbps"] = max(s["max_mbps"], res['max_mbps'])

    for ip, data in group_summary.items():
        if data["speeds"]:
            data["avg_mbps"] = round(sum(data["speeds"]) / len(data["speeds"]), 2)
        else:
            data["avg_mbps"] = 0.0
        del data["speeds"]

    save_reports(results, group_summary)
    print(f"✅ 测速报告已成功输出至私库 md/ 目录！", flush=True)

if __name__ == "__main__":
    main()
