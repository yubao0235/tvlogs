import os, requests, re, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 基础配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 2
MAX_THREADS_CHECK = 100
MAX_THREADS_SCAN = 60 # 稍微提高爆破效率

def check_url(url):
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except:
        return False

def get_existing_ip_ports():
    """从现有的 manual_fix.txt 中提取所有 IP:端口，确保彻底去重"""
    ip_ports = set()
    if os.path.exists(MANUAL_FIX):
        try:
            with open(MANUAL_FIX, 'r', encoding='utf-8') as f:
                content = f.read()
                # 增强正则：确保匹配更精准
                found = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)', content)
                ip_ports.update(found)
        except Exception as e:
            print(f"⚠️ 读取现有库失败: {e}")
    return ip_ports

def main():
    if not os.path.exists(MERGED_SOURCE):
        print(f"❌ 错误：找不到源文件 {MERGED_SOURCE}")
        return

    # 1. 初始化已存在集合（这是去重的关键）
    existing_set = get_existing_ip_ports()
    print(f"📑 现有库检测：已存在 {len(existing_set)} 个唯一网段。")

    # 2. 解析原始网段
    ip_groups = {}
    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if "," not in line or "http" not in line: continue
            parts = line.split(',', 1)
            url = parts[1].strip()
            ip_port = urlparse(url).netloc
            if ip_port:
                if ip_port not in ip_groups: ip_groups[ip_port] = []
                ip_groups[ip_port].append(line)

    final_results_dict = {} # 使用字典存储 {ip_port: block_text} 实现自动去重
    to_rescue = []

    # --- 阶段 1：全量体检 ---
    print(f"\n📡 阶段 1：全量体检开始...")
    with ThreadPoolExecutor(max_workers=MAX_THREADS_CHECK) as executor:
        future_to_ip = {executor.submit(check_url, data[0].split(',')[1]): ip for ip, data in ip_groups.items()}
        for future in as_completed(future_to_ip):
            ip_port = future_to_ip[future]
            if future.result():
                # 查重：库里没有 且 还没被本次扫描记入
                if ip_port not in existing_set:
                    print(f"  ✅ [新发现-存活] {ip_port}")
                    block = f"{ip_port},#genre#\n" + "\n".join(ip_groups[ip_port]) + "\n\n"
                    final_results_dict[ip_port] = block
                    existing_set.add(ip_port) # 实时标记已存在，防止阶段2重复命中
            else:
                to_rescue.append(ip_port)

    # --- 阶段 2：失效 IP 爆破 ---
    if to_rescue:
        print(f"\n🚀 阶段 2：爆破失效网段 (数量:{len(to_rescue)})...")
        to_rescue.sort()
        for base_ip_port in to_rescue:
            ip_parts = base_ip_port.split(':')
            if len(ip_parts) != 2: continue
            ip, port = ip_parts
            prefix = '.'.join(ip.split('.')[:-1])
            channels = ip_groups[base_ip_port]
            
            # 获取请求路径
            sample_url = channels[0].split(',')[1]
            path = sample_url.split(base_ip_port)[-1]
            
            test_tasks = {f"http://{prefix}.{i}:{port}{path}": f"{prefix}.{i}:{port}" for i in range(1, 256)}
            
            with ThreadPoolExecutor(max_workers=MAX_THREADS_SCAN) as executor:
                future_to_url = {executor.submit(check_url, url): target_ip for url, target_ip in test_tasks.items()}
                for future in as_completed(future_to_url):
                    target_ip = future_to_url[future]
                    if future.result():
                        # 核心查重：防止爆破出的 IP 与 库内 或 阶段1 冲突
                        if target_ip not in existing_set:
                            print(f"  ✨ [命中新源!!] -> {target_ip}")
                            new_block = f"{target_ip},#genre#\n"
                            for ch in channels:
                                name, old_url = ch.split(',', 1)
                                new_url = old_url.replace(base_ip_port, target_ip)
                                new_block += f"{name},{new_url}\n"
                            final_results_dict[target_ip] = new_block + "\n"
                            existing_set.add(target_ip) # 再次实时标记

    # 3. 写入文件
    if final_results_dict:
        # 最后的防御：再提取一遍库文件 IP 再次对比，防止多实例运行冲突
        re_check_set = get_existing_ip_ports()
        unique_final = [text for ip, text in final_results_dict.items() if ip not in re_check_set]

        if unique_final:
            print(f"\n💾 写入中：过滤重复后，本次实际新增 {len(unique_final)} 个网段。")
            with open(MANUAL_FIX, 'a', encoding='utf-8') as f:
                content = "".join(unique_final)
                if os.path.exists(MANUAL_FIX) and os.path.getsize(MANUAL_FIX) > 0:
                    # 确保文件末尾有且只有一个空行再追加
                    f.write("\n\n")
                f.write(content.strip() + "\n")
            print(f"🎉 任务完成！")
        else:
            print("\n📭 过滤后无新网段可写入。")
    else:
        print("\n📭 本次扫描未发现新网段。")

if __name__ == "__main__":
    main()
