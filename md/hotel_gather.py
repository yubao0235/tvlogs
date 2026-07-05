import os
import re
import asyncio
import httpx
import shutil

# --- 配置区 ---
SOURCES = [
    "https://oer.us.ci/get/jilin.m3u", 
    "https://yuxx.de5.net/edcab778.m3u",	
    "https://yuxx.de5.net/33fc12a0.m3u",	
    "https://yuxx.de5.net/3c1f32b7.m3u",	
    "https://yuxx.de5.net/97d6e00d.m3u",	
    "https://yuxx.de5.net/cd8781ee.m3u",
    "https://yuxx.de5.net/a4093b67.m3u"
]
SAVE_DIR = "hotel"
IP_API = "http://ip-api.com/json/{}?fields=status,regionName,city,query&lang=zh-CN"

async def get_location(client, ip):
    """查询归属地，增加缓存避免重复请求"""
    try:
        resp = await client.get(IP_API.format(ip), timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                region = data.get("regionName", "")
                city = data.get("city", "")
                return region if region == city else f"{region}{city}"
    except: pass
    return "未知"

async def process_sources():
    if os.path.exists(SAVE_DIR):
        shutil.rmtree(SAVE_DIR)
    os.makedirs(SAVE_DIR, exist_ok=True)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    
    # 存储格式: { "IP_Port": {"loc": "xxx", "channels": [ {"info": "...", "url": "..."}, ... ] } }
    hotel_data = {}
    location_cache = {}

    async with httpx.AsyncClient(follow_redirects=True, verify=False, headers=headers) as client:
        # 1. 下载并解析每一个源
        for src in SOURCES:
            try:
                print(f"📡 下载源: {src}", flush=True)
                r = await client.get(src)
                lines = r.text.splitlines()
                
                current_info = ""
                for line in lines:
                    line = line.strip()
                    if line.startswith("#EXTINF"):
                        current_info = line
                    elif line.startswith("http") or line.startswith("rtp"):
                        url = line
                        # 提取 IP 和 端口
                        match = re.search(r'//([0-9\.]+):(\d+)', url)
                        if match and current_info:
                            ip, port = match.groups()
                            host = f"{ip}_{port}"
                            
                            if host not in hotel_data:
                                hotel_data[host] = {"ip": ip, "channels": []}
                            
                            # 避免同一个 IP 出现重复的频道 URL
                            if not any(c['url'] == url for c in hotel_data[host]["channels"]):
                                hotel_data[host]["channels"].append({
                                    "info": current_info,
                                    "url": url
                                })
                        current_info = "" # 处理完一对，清空
            except Exception as e:
                print(f"❌ 无法处理 {src}: {e}", flush=True)

        print(f"📊 提取到 {len(hotel_data)} 个独立酒店 IP，开始查询归属地并生成文件...", flush=True)

        # 2. 并发查询归属地并写入文件
        # 为了防止被 API 封禁，这里依然使用批处理
        hosts = list(hotel_data.keys())
        batch_size = 5
        for i in range(0, len(hosts), batch_size):
            batch_hosts = hosts[i:i+batch_size]
            
            async def handle_host(h):
                ip = hotel_data[h]["ip"]
                if ip not in location_cache:
                    location_cache[ip] = await get_location(client, ip)
                
                loc = location_cache[ip]
                loc_clean = re.sub(r'[^\u4e00-\u9fa5]+', '', loc) or "未知"
                
                filename = f"{loc_clean}_{h}.m3u"
                filepath = os.path.join(SAVE_DIR, filename)
                
                # 写入完整 M3U 格式
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for ch in hotel_data[h]["channels"]:
                        f.write(f"{ch['info']}\n")
                        f.write(f"{ch['url']}\n")
            
            await asyncio.gather(*(handle_host(h) for h in batch_hosts))
            print(f"🚀 进度: {min(i+batch_size, len(hosts))}/{len(hosts)}", flush=True)
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(process_sources())
