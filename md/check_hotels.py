import os
import re
import asyncio
import httpx

# 优先读取私库路径，若无则取上级目录
WORKSPACE = os.environ.get("LIVE_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOTELS_DIR = os.path.join(WORKSPACE, "hotels")

async def check_url_status(client, url):
    """
    通过 httpx 快速检测 URL 状态码及内容特征：
    - 允许的有效状态码: 200, 301, 302
    - 附加校验：如果是文本/m3u8，确保内容不包含错误提示网页特征
    """
    try:
        # 使用 HEAD 或 GET（建议用 GET stream，部分服务器不支持 HEAD）
        async with client.stream("GET", url, timeout=6.0) as resp:
            if resp.status_code in [200, 301, 302]:
                # 进一步防范：如果返回的是 HTML 网页（比如运营商宽带欠费、404 提示页面），则认为失效
                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    return False
                
                # 如果是流媒体地址，状态码达标即可直接放行
                return True
    except Exception:
        pass
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

    # 提高并发控制，加快处理速度
    semaphore = asyncio.Semaphore(20)

    async with httpx.AsyncClient(follow_redirects=True, verify=False, headers=headers) as client:
        
        async def check_single_file(filename):
            nonlocal removed_count
            filepath = os.path.join(HOTELS_DIR, filename)
            urls = parse_m3u_urls(filepath, max_channels=2)
            
            if not urls:
                print(f"🗑️ 文件空或无有效链接，清理: {filename}")
                os.remove(filepath)
                removed_count += 1
                return

            is_alive = False
            async with semaphore:
                for url in urls:
                    if await check_url_status(client, url):
                        is_alive = True
                        break

            if is_alive:
                print(f"✅ 存活: {filename}")
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        lines = [line for line in content.splitlines() if not line.startswith("#EXTM3U")]
                        if lines:
                            return "\n".join(lines)
                except Exception:
                    pass
            else:
                print(f"❌ 失效清理: {filename}")
                os.remove(filepath)
                removed_count += 1
            return None

        # 并发执行所有文件的检测
        tasks = [check_single_file(filename) for filename in m3u_files]
        results = await asyncio.gather(*tasks)
        
        # 收集存活的内容块
        for res in results:
            if res:
                survived_channels.append(res)

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
