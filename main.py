import os
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
from bson.objectid import ObjectId

# --- CONFIGURATION (Environment Variables) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_URI", "")
APP_URL = os.environ.get("APP_URL", "").rstrip('/')
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL_ID", "0"))

# Initialize Pyrogram Bot
bot = Client("ultra_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Database
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client['ultra_stream_db']
videos = db['videos']

# --- WEB PLAYER UI (Premium Look) ---
PLAYER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watching: {title}</title>
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body {{ background: #050811; color: #fff; font-family: 'Outfit', sans-serif; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
        .player-card {{ width: 95%; max-width: 1000px; background: #101625; padding: 25px; border-radius: 30px; box-shadow: 0 30px 60px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.05); text-align: center; }}
        .v-title {{ margin: 20px 0; font-size: 22px; color: #6366f1; font-weight: 600; }}
        .dl-btn {{ background: linear-gradient(135deg, #10b981, #059669); color: #fff; text-decoration: none; padding: 15px 35px; border-radius: 15px; font-weight: 700; display: inline-block; transition: 0.3s; box-shadow: 0 10px 20px rgba(16, 185, 129, 0.2); }}
        .dl-btn:hover {{ transform: translateY(-3px); box-shadow: 0 15px 30px rgba(16, 185, 129, 0.4); }}
    </style>
</head>
<body>
    <div class="player-card">
        <video id="player" playsinline controls>
            <source src="{stream_url}" type="video/mp4" />
        </video>
        <div class="v-title">{title}</div>
        <a href="{stream_url}" class="dl-btn" download>📥 Download High Speed</a>
    </div>
    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>const player = new Plyr('#player', {{ ratio: '16:9' }});</script>
</body>
</html>
"""

# --- DIRECT STREAMING LOGIC ---

async def stream_handler(request):
    vid = request.match_info.get('vid')
    try:
        data = await videos.find_one({"_id": ObjectId(vid)})
    except:
        return web.Response(text="Invalid ID", status=400)

    if not data:
        return web.Response(text="File Not Found", status=404)

    file_id = data['file_id']
    file_size = data['file_size']
    file_name = data['title']

    # Range request handling (Seeking support)
    range_header = request.headers.get("Range")
    start = 0
    if range_header:
        start = int(range_header.replace("bytes=", "").split("-")[0])

    # Headers for Browser
    headers = {
        "Content-Type": "video/mp4",
        "Content-Disposition": f'attachment; filename="{file_name}"',
        "Accept-Ranges": "bytes",
    }

    if range_header:
        headers["Content-Range"] = f"bytes {start}-{file_size-1}/{file_size}"
        status = 206
    else:
        status = 200

    response = web.StreamResponse(status=status, headers=headers)
    response.content_length = file_size - start
    await response.prepare(request)

    # Chunk-by-chunk streaming from Telegram
    try:
        async for chunk in bot.stream_media(file_id, offset=start):
            await response.write(chunk)
    except Exception as e:
        print(f"Streaming Error: {e}")
    
    return response

async def watch_page(request):
    vid = request.match_info.get('vid')
    data = await videos.find_one({"_id": ObjectId(vid)})
    if not data: return web.Response(text="Not Found", status=404)
    
    stream_url = f"{APP_URL}/dl/{vid}"
    return web.Response(text=PLAYER_HTML.format(title=data['title'], stream_url=stream_url), content_type='text/html')

# --- BOT LOGIC ---

@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text(f"👋 **হ্যালো {m.from_user.first_name}!**\n\nআমাকে ৪জিবি, ৫জিবি বা তার বেশি বড় যেকোনো ভিডিও ফাইল পাঠান। আমি সেটির অনলাইন প্লে লিঙ্ক দেব।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_media(c, m):
    media = m.video or m.document
    if m.document and "video" not in m.document.mime_type:
        return # শুধু ভিডিও ফাইল গ্রহণ করবে

    status = await m.reply_text("⏳ **লিঙ্ক তৈরি হচ্ছে...**")
    
    # ভিডিওটি লগ চ্যানেলে ফরওয়ার্ড করা (যাতে ফাইল সেভ থাকে)
    try:
        log_msg = await m.forward(LOG_CHANNEL)
    except Exception:
        return await status.edit("❌ বটকে আপনার লগ চ্যানেলে এডমিন করুন!")

    # ডাটাবেসে তথ্য জমা রাখা
    res = await videos.insert_one({
        "title": media.file_name or "Untitled Video",
        "file_id": media.file_id,
        "file_size": media.file_size,
        "user_id": m.from_user.id,
        "msg_id": log_msg.id
    })
    
    video_id = str(res.inserted_id)
    watch_link = f"{APP_URL}/watch/{video_id}"
    
    await status.edit(
        f"✅ **ভিডিও সফলভাবে প্রসেস হয়েছে!**\n\n🎬 **Online Player:** {watch_link}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Watch / Download", url=watch_link)]])
    )

# --- START SERVER ---

async def main():
    await bot.start()
    server = web.Application()
    server.router.add_get("/", lambda r: web.Response(text="Streaming Bot Active!"))
    server.router.add_get("/watch/{vid}", watch_page)
    server.router.add_get("/dl/{vid}", stream_handler) # ডাউনলোড ও স্ট্রিম হ্যান্ডলার
    
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()
    
    print("🚀 Bot & Stream Server Started!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
