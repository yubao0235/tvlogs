import os
import re
from urllib.parse import urlparse

# --- 配置 ---
BASE_DIR = "hotel"
SAVE_PATH = "hotel.txt"

def get_ip_from_url(url):
    """提取 IP:Port"""
    try:
        if not url.startswith("http"):
            url = "http://" + url
        return urlparse(url).netloc
    except:
        return None

def clean_name(name):
    """标准化频道名：CCTV-01 -> CCTV-1"""
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s\t]+', '', name)
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match:
        return f"CCTV-{int(cctv_match.group(1))}"
    return name

def main():
    # 数据结构: { "IP:Port": { "频道名": "URL" } }
    ip_groups = {}

    if not os.path.exists(BASE_DIR):
        print(f"Directory {BASE_DIR} not found.")
        return

    # 递归遍历所有子文件夹
    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith((".m3u", ".txt")):
                with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                    current_info = ""
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        if line.startswith("#EXTINF"):
                            current_info = line
                        elif line.startswith("http"):
                            url = line
                            # 获取频道名
                            raw_name = current_info.split(',')[-1] if current_info else "未知频道"
                            ip_port = get_ip_from_url(url)
                            
                            if ip_port:
                                if ip_port not in ip_groups:
                                    ip_groups[ip_port] = {}
                                
                                std_name = clean_name(raw_name)
                                # 去重：同一IP下同名频道只保留一个
                                if std_name not in ip_groups[ip_port]:
                                    ip_groups[ip_port][std_name] = url
                            current_info = ""

    # 写入结果
    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        # 按 IP 排序
        for ip in sorted(ip_groups.keys()):
            f.write(f"{ip},#genre#\n")
            channels = ip_groups[ip]
            # CCTV 优先排序
            for name in sorted(channels.keys(), key=lambda x: (not x.startswith("CCTV"), x)):
                f.write(f"{name},{channels[name]}\n")
            f.write("\n")

if __name__ == "__main__":
    main()
