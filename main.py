import os
import asyncio
import mimetypes
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
from bson.objectid import ObjectId
from datetime import datetime

# লগিং সেটিংস (রেন্ডার লগে সব ডিটেইলস দেখতে পাবেন)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- কনফিগারেশন (রেন্ডার এনভায়রনমেন্ট ভেরিয়েবল থেকে আসবে) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_URI", "")
APP_URL = os.environ.get("APP_URL", "").rstrip('/')
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL_ID", "0"))

# হাই-স্পিড ও রেন্ডার অপ্টিমাইজড বট ক্লায়েন্ট
bot = Client(
    "ultra_fast_stream_v3",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=120,
    max_concurrent_transmissions=10, # প্যারালাল স্ট্রিমিং সাপোর্ট
    workers=100,
    in_memory=True # রেন্ডারের ফাইল রাইটিং এরর এড়াতে
)

# ডাটাবেস কানেকশন
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client['mega_streaming_pro_final']
video_collection = db['videos']

# --- প্রিমিয়াম প্লেয়ার ডিজাইন (Ultra HD & Fast) ---
PLAYER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Streaming: {title}</title>
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ background: #050811; color: #fff; font-family: 'Outfit', sans-serif; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
        .container {{ width: 95%; max-width: 950px; padding: 30px; background: #101625; border-radius: 30px; box-shadow: 0 30px 60px rgba(0,0,0,0.6); text-align: center; border: 1px solid rgba(255,255,255,0.05); }}
        .v-title {{ margin: 15px 0; font-size: 20px; color: #818cf8; font-weight: 600; }}
        .btn-dl {{ background: linear-gradient(135deg, #10b981, #059669); color: #fff; text-decoration: none; padding: 15px 35px; border-radius: 12px; font-weight: 700; display: inline-block; transition: 0.3s; box-shadow: 0 10px 20px rgba(16, 185, 129, 0.2); }}
        .btn-dl:hover {{ transform: translateY(-3px); }}
    </style>
</head>
<body>
    <div class="container">
        <video id="player" playsinline controls preload="auto">
            <source src="{stream_url}" type="video/mp4" />
        </video>
        <div class="v-title">{title}</div>
        <p style="font-size:11px; color:#475569; text-transform: uppercase;">Direct Telegram Pipe | High-Speed Buffering</p>
        <a href="{stream_url}" class="btn-dl" download>📥 High Speed Download</a>
    </div>
    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>const player = new Plyr('#player', {{ settings: ['speed'], invertTime: false }});</script>
</body>
</html>
"""

# --- ৪জিবি+ প্যারালাল স্ট্রিমিং ইঞ্জিন ---
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
        # সরাসরি টেলিগ্রাম থেকে ডাটা চ্যাঙ্ক ব্রাউজারে পাঠানো
        async for chunk in bot.stream_media(file_id, offset=start, limit=end - start + 1):
            await response.write(chunk)
    except Exception as e:
        logger.error(f"Streaming Error: {e}")
    
    return response

async def watch_page(request):
    vid = request.match_info.get('vid')
    try:
        data = await video_collection.find_one({"_id": ObjectId(vid)})
    except: return web.Response(text="Invalid Link", status=400)
    
    if not data: return web.Response(text="Video Not Found", status=404)
    
    stream_url = f"{APP_URL}/dl/{vid}"
    return web.Response(text=PLAYER_HTML.format(title=data['title'], stream_url=stream_url), content_type='text/html')

# --- টেলিগ্রাম বট হ্যান্ডলার ---

@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    await m.reply_text(
        f"👋 **হ্যালো {m.from_user.first_name}!**\n\n"
        f"আমাকে যেকোনো বড় ভিডিও (৪জিবি+) পাঠান। আমি সেটির সুপার ফাস্ট প্লে ও ডাউনলোড লিঙ্ক দেব।"
    )

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    media = m.video or m.document
    if m.document and "video" not in m.document.mime_type: return

    status = await m.reply_text("⏳ **প্রসেস হচ্ছে, দয়া করে অপেক্ষা করুন...**")
    
    try:
        # ১. লগ চ্যানেলে ফরওয়ার্ড করা (সার্ভার এক্সেস নিশ্চিত করতে)
        try:
            log_msg = await m.forward(LOG_CHANNEL)
        except Exception as e:
            return await status.edit(f"❌ **Error:** বট লগ চ্যানেলে ফাইল পাঠাতে পারছে না। বটকে চ্যানেলে অ্যাডমিন করুন।\n`Error: {e}`")

        # ২. ডাটাবেসে সেভ
        res = await video_collection.insert_one({
            "title": media.file_name or "video.mp4",
            "file_id": media.file_id,
            "file_size": media.file_size,
            "time": datetime.now()
        })
        
        watch_url = f"{APP_URL}/watch/{res.inserted_id}"
        
        await status.edit(
            f"✅ **লিঙ্ক সফলভাবে তৈরি হয়েছে!**\n\n🎬 **প্লে লিঙ্ক:** {watch_url}\n🚀 এটি IDM/ADM হাই-স্পিড সাপোর্ট করে।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Watch / Download", url=watch_url)]])
        )
    except Exception as e:
        await status.edit(f"❌ **ভুল হয়েছে:** {e}")

# --- সার্ভার ও স্টার্টআপ ---

async def main():
    try:
        await bot.start()
        logger.info("✅ Bot Started Successfully!")
    except Exception as e:
        logger.error(f"❌ Bot Failed: {e}")
        return

    app_server = web.Application()
    
    # রেন্ডারের হেলথ চেক পেজ
    async def health_check(request):
        return web.Response(text="Bot is Running Perfectly!", status=200)

    app_server.router.add_get("/", health_check)
    app_server.router.add_get("/watch/{vid}", watch_page)
    app_server.router.add_get("/dl/{vid}", stream_handler)
    
    runner = web.AppRunner(app_server)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await site.start()
    logger.info(f"🚀 Server running on port {port}")
    
    # ইনফিনিটি লুপ
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
