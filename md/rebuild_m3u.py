import os
import shutil
import re

# ================= ⚡ 跨库核心动态路径锁定 =================
WORKSPACE = os.environ.get("LIVE_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOTEL_OUTPUT = os.path.join(WORKSPACE, "hotel_output.txt")
REBORN_DIR = os.path.join(WORKSPACE, "hotels")  # 🎯 指向私库下的 hotels
LOGO_BASE_URL = "https://tb.yubo.qzz.io/logo/"
# ==========================================================

def clean_channel_name(name):
    name = re.sub(r'(标清|普清|超高清|H\.265|4K|HD|SD|hd|sd)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s]+', '', name)
    return name.strip()

def rebuild():
    if not os.path.exists(HOTEL_OUTPUT):
        print(f"⚠️ 找不到输入文件: {HOTEL_OUTPUT}")
        return
        
    # 确保目标目录存在，但不使用 rmtree 粗暴清空，以保护历史资产
    if not os.path.exists(REBORN_DIR):
        os.makedirs(REBORN_DIR)

    # 1. 读取本次扫描输出
    with open(HOTEL_OUTPUT, "r", encoding="utf-8") as f:
        content = f.read().strip().split("\n\n")

    # 记录本次新生成的REBORN文件名前缀，用于后续精准更新
    new_reborn_files = set()

    for section in content:
        lines = section.strip().split("\n")
        if not lines: continue
        host = lines[0].split(",")[0]
        safe_host = host.replace('.', '_').replace(':', '_')
        file_name = f"REBORN_{safe_host}.m3u"
        new_reborn_files.add(file_name)
        
        single_m3u = ["#EXTM3U"]
        for cl in lines[1:]:
            if "," in cl:
                name, url = cl.split(",", 1)
                clean_n = clean_channel_name(name)
                header = f'#EXTINF:-1 tvg-name="{clean_n}" tvg-logo="{LOGO_BASE_URL}{clean_n}.png" group-title="Hotel_{host}",{clean_n}'
                single_m3u.extend([header, url])
        
        # 写入本次新扫描出的单体 m3u 文件
        with open(os.path.join(REBORN_DIR, file_name), "w", encoding="utf-8") as f_out:
            f_out.write("\n".join(single_m3u))

    # 2. 🌟 核心升级：智能合流与聚合（新资产 + 未本次更新的历史老资产）
    all_m3u = ["#EXTM3U"]
    processed_urls = set() # 用于总表去重

    print("🔄 正在聚合目录下的所有新老 M3U 资产...")
    for filename in os.listdir(REBORN_DIR):
        if filename.endswith(".m3u") and filename != "ALL.m3u":
            file_path = os.path.join(REBORN_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                    lines = f_in.read().split("\n")
                    for i in range(len(lines)):
                        if lines[i].startswith("#EXTINF") and i + 1 < len(lines):
                            header = lines[i]
                            url = lines[i+1].strip()
                            if url and url not in processed_urls:
                                processed_urls.add(url)
                                all_m3u.extend([header, url])
            except Exception as e:
                print(f"⚠️ 读取文件 {filename} 出错: {e}")

    # 3. 写入终极聚合大表 ALL.m3u
    all_m3u_path = os.path.join(REBORN_DIR, "ALL.m3u")
    with open(all_m3u_path, "w", encoding="utf-8") as f_all:
        f_all.write("\n".join(all_m3u))

    print(f"🌟 洗版与全量融合完成！总表已更新，当前包含有效源地址数: {len(processed_urls)}")
    print(f"📂 目标目录: {REBORN_DIR}")

if __name__ == "__main__":
    rebuild()
