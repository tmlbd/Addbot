import os
import asyncio
import mimetypes
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

# সেশন কনফ্লিক্ট ও রেন্ডার পারমিশন ফিক্স
bot = Client(
    "power_stream_pro", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    sleep_threshold=120,
    max_concurrent_transmissions=10, 
    workers=100,
    in_memory=True # রেন্ডারের ফাইল সিস্টেম এরর এড়াতে এটি বাধ্যতামূলক
)

# Database Setup
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client['final_stream_db']
video_collection = db['videos']

# --- PREMIUM PLAYER UI ---
PLAYER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watching: {title}</title>
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ background: #050811; color: #fff; font-family: 'Outfit', sans-serif; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }}
        .container {{ width: 95%; max-width: 900px; padding: 25px; background: #101625; border-radius: 30px; border: 1px solid rgba(255,255,255,0.05); text-align: center; }}
        .v-title {{ margin: 15px 0; font-size: 18px; color: #818cf8; font-weight: 600; }}
        .btn-dl {{ background: linear-gradient(135deg, #10b981, #059669); color: #fff; text-decoration: none; padding: 14px 35px; border-radius: 12px; font-weight: 700; display: inline-block; }}
    </style>
</head>
<body>
    <div class="container">
        <video id="player" playsinline controls preload="auto">
            <source src="{stream_url}" type="video/mp4" />
        </video>
        <div class="v-title">{title}</div>
        <a href="{stream_url}" class="btn-dl" download>📥 High Speed Download</a>
    </div>
    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>const player = new Plyr('#player', {{ settings: ['speed'], invertTime: false }});</script>
</body>
</html>
"""

# --- HIGH-SPEED STREAMING LOGIC ---
async def stream_handler(request):
    vid = request.match_info.get('vid')
    try:
        data = await video_collection.find_one({"_id": ObjectId(vid)})
    except: return web.Response(text="Invalid ID", status=400)
    
    if not data: return web.Response(text="File Not Found", status=404)

    file_id = data['file_id']
    file_size = data['file_size']
    file_name = data['title']
    
    range_header = request.headers.get("Range")
    start = 0
    end = file_size - 1

    if range_header:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0])
        if ranges[1]: end = int(ranges[1])

    response = web.StreamResponse(
        status=206 if range_header else 200,
        headers={
            "Content-Type": "video/mp4",
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(end - start + 1),
        }
    )
    await response.prepare(request)

    try:
        # প্যারালাল স্ট্রিমিং (Parallel Buffering)
        async for chunk in bot.stream_media(file_id, offset=start, limit=end - start + 1):
            await response.write(chunk)
    except: pass
    return response

async def watch_page(request):
    vid = request.match_info.get('vid')
    data = await video_collection.find_one({"_id": ObjectId(vid)})
    if not data: return web.Response(text="Video Not Found", status=404)
    stream_url = f"{APP_URL}/dl/{vid}"
    return web.Response(text=PLAYER_HTML.format(title=data['title'], stream_url=stream_url), content_type='text/html')

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    await m.reply_text(f"👋 **হ্যালো {m.from_user.first_name}!**\n\nআমাকে ৪জিবি+ যেকোনো ভিডিও পাঠান। আমি আপনাকে সেটি অনলাইনে দেখার ও ডাউনলোড করার লিঙ্ক দেব।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    media = m.video or m.document
    if m.document and "video" not in m.document.mime_type: return

    msg = await m.reply_text("⏳ **লিঙ্ক তৈরি হচ্ছে...**")
    try:
        # লগ চ্যানেলে ফরওয়ার্ড করা (MTProto এক্সেসের জন্য জরুরি)
        log_msg = await m.forward(LOG_CHANNEL)
        
        # ডাটাবেসে সেভ
        res = await video_collection.insert_one({
            "title": media.file_name or "video.mp4",
            "file_id": media.file_id,
            "file_size": media.file_size,
            "time": datetime.now()
        })
        
        watch_url = f"{APP_URL}/watch/{res.inserted_id}"
        await msg.edit(
            f"✅ **লিঙ্ক সফলভাবে তৈরি হয়েছে!**\n\n🎬 **প্লে লিঙ্ক:** {watch_url}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Watch Online", url=watch_url)]])
        )
    except Exception as e:
        await msg.edit(f"❌ এরর: {e}\n\nনিশ্চিত করুন বট আপনার লগ চ্যানেলে এডমিন আছে।")

# --- STARTUP LOGIC (Fixed Loop) ---
async def main():
    print("🚀 Starting Bot...")
    await bot.start()
    print("✅ Bot Started!")

    app_server = web.Application()
    app_server.router.add_get("/", lambda r: web.Response(text="Bot is Online!", status=200))
    app_server.router.add_get("/watch/{vid}", watch_page)
    app_server.router.add_get("/dl/{vid}", stream_handler)
    
    runner = web.AppRunner(app_server)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await site.start()
    print(f"🚀 Web Server running on port {port}")
    
    # বট যেন বন্ধ না হয়
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
