import os
import sys
import time
import json
import random
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 屏蔽自签名证书警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# --- 配置参数 ---
TEST_DURATION = 6          # 每个流最大测试持续时间（秒）
MAX_WORKERS = 10           # 并发线程数

# 路径自适应适配
WORKSPACE = os.environ.get('LIVE_WORKSPACE') or os.getcwd()
OUTPUT_TXT = os.path.join(WORKSPACE, "md", "traffic_report.txt")
OUTPUT_JSON = os.path.join(WORKSPACE, "md", "traffic_summary.json")

def test_stream_traffic(url, timeout=TEST_DURATION):
    """测试单个视频流的下载速度与稳定性"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Range': 'bytes=0-'
    }
    start_time = time.time()
    downloaded_bytes = 0
    speed_samples = []
    
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=5, verify=False)
        if response.status_code not in [200, 206]:
            return None
            
        chunk_size = 32 * 1024  # 32KB
        last_time = start_time
        chunk_bytes = 0
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            current_time = time.time()
            elapsed_total = current_time - start_time
            
            if elapsed_total >= timeout:
                break
                
            if chunk:
                downloaded_bytes += len(chunk)
                chunk_bytes += len(chunk)
                
            if current_time - last_time >= 1.0:
                inst_speed = (chunk_bytes / (current_time - last_time)) / (1024 * 1024 * 8) * 8
                speed_samples.append(inst_speed)
                chunk_bytes = 0
                last_time = current_time
                
        total_time = time.time() - start_time
        if total_time <= 0 or downloaded_bytes == 0:
            return None
            
        avg_speed_mbps = (downloaded_bytes / total_time) / (1024 * 1024) * 8
        max_speed_mbps = max(speed_samples) if speed_samples else avg_speed_mbps
        
        return {
            "avg_mbps": round(avg_speed_mbps, 2),
            "max_mbps": round(max_speed_mbps, 2),
            "stability": len(speed_samples) / timeout if timeout > 0 else 1.0
        }
    except Exception:
        return None

def run_speed_test_pipeline():
    print(f"🚀 [分段引擎] 开始执行 IPTV 流量测速任务，工作区路径: {WORKSPACE}", flush=True)
    
    all_m3u_path = os.path.join(WORKSPACE, "hotels", "ALL.m3u")
    if not os.path.exists(all_m3u_path):
        print(f"⚠️ 未找到目标播放列表文件: {all_m3u_path}，测速退出。", flush=True)
        return

    # 解析 M3U
    channels = []
    current_name = ""
    with open(all_m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#EXTINF:'):
                if ',' in line:
                    current_name = line.split(',')[-1].strip()
            elif line and not line.startswith('#'):
                if current_name:
                    channels.append({"name": current_name, "url": line})
                current_name = ""

    if not channels:
        print("⚠️ 没有解析到任何可测试的频道链接。", flush=True)
        return

    total_channels = len(channels)
    print(f"📦 成功加载 ALL.m3u，总计待测频道数: {total_channels} 个。多线程并发启动...", flush=True)

    results = []
    group_summary = {}

    def worker(ch):
        res = test_stream_traffic(ch['url'])
        if res:
            import urllib.parse
            parsed_url = urllib.parse.urlparse(ch['url'])
            ip_port = parsed_url.netloc or "unknown"
            return {
                "ip_port": ip_port,
                "name": ch['name'],
                "url": ch['url'],
                **res
            }
        return None

    # 分段实时输出进度
    completed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(worker, ch): ch for ch in channels}
        
        for future in as_completed(futures):
            completed_count += 1
            res = future.result()
            
            # 🎯 强制每完成一个或每隔几个打印一次日志，并利用 sys.stdout.flush() 刷新
            if res:
                results.append(res)
                print(f"[{completed_count}/{total_channels}] ⚡ [有效] IP: {res['ip_port']} | {res['name']} | 速度: {res['avg_mbps']} Mbps", flush=True)
                
                ip = res['ip_port']
                if ip not in group_summary:
                    group_summary[ip] = {"alive_count": 0, "total_speed": 0, "max_mbps": 0}
                group_summary[ip]["alive_count"] += 1
                group_summary[ip]["total_speed"] += res["avg_mbps"]
                if res["max_mbps"] > group_summary[ip]["max_mbps"]:
                    group_summary[ip]["max_mbps"] = res["max_mbps"]
            else:
                # 即使失败也打印心跳，防止日志长时间沉寂
                if completed_count % 10 == 0 or completed_count == total_channels:
                    print(f"[{completed_count}/{total_channels}] 🔄 正在测速中... (已过滤失效源)", flush=True)

    # 计算网段平均速度
    for ip, summ in group_summary.items():
        if summ["alive_count"] > 0:
            summ["avg_mbps"] = round(summ["total_speed"] / summ["alive_count"], 2)
        else:
            summ["avg_mbps"] = 0.0

    # 保存报告
    os.makedirs(os.path.dirname(OUTPUT_TXT), exist_ok=True)
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write("="*75 + "\n")
        f.write(f"📡 IPTV 流量测速报告 (频道明细) | 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*75 + "\n")
        for res in results:
            f.write(f"{res['ip_port']:<25} | {res['name'][:12]:<15} | {res['avg_mbps']:>6} Mbps | 稳定性:{res['stability']*100:>3.0f}%\n")

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({"summary": group_summary, "details": results}, f, ensure_ascii=False, indent=2)

    print(f"✅ [完成] 测速全部结束！有效频道: {len(results)}/{total_channels}。报告已安全落盘。", flush=True)

if __name__ == "__main__":
    run_speed_test_pipeline()
