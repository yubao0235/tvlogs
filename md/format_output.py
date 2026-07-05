import os
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")
OUTPUT_TXT = os.path.join(PARENT_DIR, "final_hotel.txt")
OUTPUT_M3U = os.path.join(PARENT_DIR, "final_hotel.m3u")

LOGO_BASE_URL = "https://tb.yubo.qzz.io/logo/"
EPG_URL = "https://live.fanmingming.com/e.xml"

def clean_channel_name(name):
    """
    清理频道名称中的 HD, SD, 高清, 标清 标记
    """
    # 1. 移除 (HD), [HD], -HD 等括号或连字符包装的标记
    # 2. 移除独立的 HD, SD, 高清, 标清 关键字 (不区分大小写)
    # \s* 代表匹配可能存在的空格
    name = re.sub(r'\s*[\(\[（【]?(?:HD|SD|高清|标清)[\)\]）】]?\s*', '', name, flags=re.IGNORECASE)
    return name.strip()

def main():
    all_blocks = []
    for path in [MID_REVIVED, MID_RESCUED]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
                    all_blocks.extend(blocks)

    if not all_blocks:
        print("❌ 未发现有效数据。")
        return

    # 1. 生成 TXT (保持原始块结构，但清理名称)
    cleaned_blocks = []
    for block in all_blocks:
        lines = block.split('\n')
        new_block_lines = [lines[0]] # 保留 IP,#genre# 行
        for line in lines[1:]:
            if ',' in line:
                name, url = line.split(',', 1)
                new_name = clean_channel_name(name)
                new_block_lines.append(f"{new_name},{url.strip()}")
        cleaned_blocks.append('\n'.join(new_block_lines))

    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(cleaned_blocks))

    # 2. 生成 M3U
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    for block in cleaned_blocks:
        lines = block.split('\n')
        group_title = lines[0].split(',')[0].strip()
        for line in lines[1:]:
            if ',' in line:
                name, url = line.split(',', 1)
                # 此时 name 已经是清理过的了
                clean_n = name.strip()
                m3u_lines.append(f'#EXTINF:-1 tvg-id="{clean_n}" tvg-logo="{LOGO_BASE_URL}{clean_n}.png" group-title="{group_title}",{clean_n}')
                m3u_lines.append(url.strip())

    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines))
    
    print(f"🎉 处理完成，画质标记已剔除。网段总数: {len(all_blocks)}")

if __name__ == "__main__":
    main()
