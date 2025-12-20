import os
import asyncio
import mimetypes
import math
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
from bson.objectid import ObjectId
from datetime import datetime

# --- CONFIGURATION (Environment Variables) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_URI", "")
APP_URL = os.environ.get("APP_URL", "").rstrip('/')
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL_ID", "0"))

# হাই-স্পিড ও প্যারালাল স্ট্রিমিং কনফিগারেশন
bot = Client(
    "power_stream_pro", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    sleep_threshold=120,
    max_concurrent_transmissions=10, # প্যারালাল ট্রান্সফার (নতুন ভার্সন অনুযায়ী)
    workers=100
)

# Database Setup
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client['ultra_fast_stream_db']
video_collection = db['videos']

# --- PREMIUM PLAYER UI (Glassmorphism & High Quality) ---
PLAYER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Pro: {title}</title>
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ background: #050811; color: #fff; font-family: 'Outfit', sans-serif; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }}
        .container {{ width: 95%; max-width: 1000px; padding: 25px; background: #101625; border-radius: 30px; box-shadow: 0 30px 60px rgba(0,0,0,0.6); text-align: center; border: 1px solid rgba(255,255,255,0.05); }}
        .v-title {{ margin: 15px 0; font-size: 20px; color: #818cf8; font-weight: 600; }}
        .controls-info {{ font-size: 11px; color: #475569; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 1px; }}
        .btn-dl {{ background: linear-gradient(135deg, #10b981, #059669); color: #fff; text-decoration: none; padding: 14px 35px; border-radius: 12px; font-weight: 700; display: inline-block; transition: 0.3s; box-shadow: 0 10px 20px rgba(16, 185, 129, 0.2); }}
        .btn-dl:hover {{ transform: translateY(-3px); box-shadow: 0 15px 30px rgba(16, 185, 129, 0.4); }}
    </style>
</head>
<body>
    <div class="container">
        <video id="player" playsinline controls preload="auto">
            <source src="{stream_url}" type="video/mp4" />
        </video>
        <div class="v-title">{title}</div>
        <div class="controls-info">Fast Buffering | Parallel Stream Active</div>
        <a href="{stream_url}" class="btn-dl" download>📥 High Speed Download</a>
    </div>
    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>
        const player = new Plyr('#player', {{
            settings: ['quality', 'speed', 'loop'],
            speed: {{ selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] }},
            invertTime: false
        }});
    </script>
</body>
</html>
"""

# --- HIGH-SPEED CHUNK STREAMING ENGINE (Direct Pipe) ---

async def stream_handler(request):
    vid = request.match_info.get('vid')
    try:
        data = await video_collection.find_one({"_id": ObjectId(vid)})
    except:
        return web.Response(text="Invalid ID", status=400)
    
    if not data:
        return web.Response(text="File Not Found", status=404)

    file_id = data['file_id']
    file_size = data['file_size']
    file_name = data['title']
    
    range_header = request.headers.get("Range")
    start = 0
    end = file_size - 1

    if range_header:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0])
        if ranges[1]:
            end = int(ranges[1])

    response = web.StreamResponse(
        status=206 if range_header else 200,
        headers={
            "Content-Type": "video/mp4",
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(end - start + 1),
            "Cache-Control": "public, max-age=31536000",
        }
    )

    await response.prepare(request)

    # প্যারালাল স্ট্রিমিং ও বাফারিং
    try:
        async for chunk in bot.stream_media(file_id, offset=start, limit=end - start + 1):
            await response.write(chunk)
    except Exception as e:
        print(f"Streaming Error: {e}")
    
    return response

async def watch_page(request):
    vid = request.match_info.get('vid')
    data = await video_collection.find_one({"_id": ObjectId(vid)})
    if not data: return web.Response(text="Video Not Found", status=404)
    
    stream_url = f"{APP_URL}/dl/{vid}"
    return web.Response(text=PLAYER_HTML.format(title=data['title'], stream_url=stream_url), content_type='text/html')

# --- BOT LOGIC ---

@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    # ডাটাবেস চেক করে ইউজারের জন্য স্টার্ট মেসেজ
    await m.reply_text(
        f"👋 **হ্যালো {m.from_user.first_name}!**\n\n"
        f"আমাকে যেকোনো বড় মুভি বা ভিডিও (৪জিবি+) পাঠান। আমি সেটির সুপার ফাস্ট প্লে ও ডাউনলোড লিঙ্ক দেব।"
    )

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    media = m.video or m.document
    if m.document and "video" not in m.document.mime_type: return

    status = await m.reply_text("⏳ **প্রসেস হচ্ছে...**")
    
    try:
        # ফাইলটি লগ চ্যানেলে ফরওয়ার্ড করা (সার্ভার এক্সেস নিশ্চিত করতে)
        log_msg = await m.forward(LOG_CHANNEL)
    except:
        return await status.edit("❌ বটকে আপনার লগ চ্যানেলে এডমিন করুন এবং LOG_CHANNEL_ID চেক করুন।")

    # ডাটাবেসে সেভ
    res = await video_collection.insert_one({
        "title": media.file_name or "video.mp4",
        "file_id": media.file_id,
        "file_size": media.file_size,
        "msg_id": log_msg.id,
        "time": datetime.now()
    })
    
    video_id = str(res.inserted_id)
    watch_url = f"{APP_URL}/watch/{video_id}"
    
    await status.edit(
        f"✅ **ভিডিও রেডি!**\n\n🎬 **Watch Online:** {watch_url}\n🚀 এটি IDM/ADM হাই-স্পিড সাপোর্ট করে।",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 প্লে ও ডাউনলোড", url=watch_url)]])
    )

# --- STARTUP & HEALTH CHECK ---

async def main():
    await bot.start()
    app_server = web.Application()
    
    # রেন্ডার সার্ভার যেন সজাগ থাকে
    async def health_check(request):
        return web.Response(text="Power Stream Bot is Active!", status=200)

    app_server.router.add_get("/", health_check)
    app_server.router.add_get("/watch/{vid}", watch_page)
    app_server.router.add_get("/dl/{vid}", stream_handler)
    
    runner = web.AppRunner(app_server)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await site.start()
    print(f"🚀 Server running on port {port}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
