import os
import re
import asyncio
import httpx
import subprocess

# 优先读取私库路径，若无则取上级目录
WORKSPACE = os.environ.get("LIVE_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOTELS_DIR = os.path.join(WORKSPACE, "hotels")

async def check_url_http(client, url):
    """方法一：快速检测 URL 是否返回 HTTP 200"""
    try:
        # 使用 GET 请求并开启 follow_redirects，仅读取头部或流一小段即可断开
        async with client.stream("GET", url, timeout=5.0) as resp:
            if resp.status_code == 200:
                return True
    except Exception:
        pass
    return False

def check_url_ffmpeg(url):
    """方法二：使用 FFmpeg 探测流是否真实可读（测试前两个频道）"""
    cmd = [
        "ffmpeg",
        "-y",
        "-timeout", "4000000",  # 微秒单位，即 4 秒超时
        "-i", url,
        "-vframes", "1",        # 只尝试抓取 1 帧
        "-f", "null",
        "-"
    ]
    try:
        # 运行 ffmpeg，设置总超时 6 秒
        result = subprocess.run(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            timeout=6.0
        )
        return result.returncode == 0
    except Exception:
        return False

def parse_m3u_urls(filepath, max_channels=2):
    """从单个 m3u 文件中提取前 N 个频道的播放链接"""
    urls = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("http") or line.startswith("rtp"):
                    urls.append(line)
                    if len(urls) >= max_channels:
                        break
    except Exception:
        pass
    return urls

async def process_hotel_files():
    if not os.path.exists(HOTELS_DIR):
        print(f"❌ 目录不存在: {HOTELS_DIR}")
        return

    m3u_files = [f for f in os.listdir(HOTELS_DIR) if f.endswith(".m3u") and f != "ALL.m3u"]
    print(f"📂 扫描到 {len(m3u_files)} 个待检测的酒店 M3U 文件...", flush=True)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    
    removed_count = 0
    survived_channels = []

    async with httpx.AsyncClient(follow_redirects=True, verify=False, headers=headers) as client:
        for filename in m3u_files:
            filepath = os.path.join(HOTELS_DIR, filename)
            urls = parse_m3u_urls(filepath, max_channels=2)
            
            if not urls:
                print(f"🗑️ 文件空或无有效链接，清理: {filename}")
                os.remove(filepath)
                removed_count += 1
                continue

            is_alive = False

            # --- 阶段 1：HTTP 快速探测 ---
            for url in urls:
                if await check_url_http(client, url):
                    is_alive = True
                    break

            # --- 阶段 2：若 HTTP 没通过 200，启用 FFmpeg 深度探测 ---
            if not is_alive:
                for url in urls:
                    print(f"🔄 HTTP检测未通过，正在使用 FFmpeg 深度探测: {filename} -> {url}")
                    if check_url_ffmpeg(url):
                        is_alive = True
                        break

            # --- 结果判定 ---
            if is_alive:
                print(f"✅ 存活: {filename}")
                # 读取该存活文件的完整内容，准备合并入 ALL.m3u
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        # 去掉 #EXTM3U 头部，后面统一拼装
                        lines = [line for line in content.splitlines() if not line.startswith("#EXTM3U")]
                        if lines:
                            survived_channels.append("\n".join(lines))
                except Exception:
                    pass
            else:
                print(f"❌ 失效清理: {filename}")
                os.remove(filepath)
                removed_count += 1

    # --- 重新生成汇总 ALL.m3u ---
    all_m3u_path = os.path.join(HOTELS_DIR, "ALL.m3u")
    print(f"📝 正在重新生成汇总文件: {all_m3u_path}")
    with open(all_m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for block in survived_channels:
            f.write(block + "\n")

    print(f"🎉 检测完成！共清理失效文件 {removed_count} 个，剩余存活文件 {len(m3u_files) - removed_count} 个。")

if __name__ == "__main__":
    asyncio.run(process_hotel_files())
