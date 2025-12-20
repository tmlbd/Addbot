import os
import asyncio
import logging
from pyrogram import Client, filters, errors
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from contextlib import asynccontextmanager

# === কনফিগারেশন (Environment Variables) ===
API_ID = int(os.environ.get("API_ID", ""))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "")
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", ""))
WEB_URL = os.environ.get("WEB_URL", "").rstrip('/')

# === লগিং সেটআপ ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === ডাটাবেস সেটআপ ===
db_client = AsyncIOMotorClient(MONGO_DB_URI, serverSelectionTimeoutMS=5000)
db = db_client.StreamBotDB
files_col = db.files

# === বট ক্লায়েন্ট ===
bot = Client(
    "StreamBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=120
)

# === স্ট্রিমিং লজিক (৪ জিবি+ ফাইল সাপোর্ট) ===
async def media_generator(message_id):
    try:
        msg = await bot.get_messages(LOG_CHANNEL, message_id)
        # block=True নিশ্চিত করে যে ফাইলটি চাঙ্ক আকারে মেমোরিতে লোড হবে (RAM বাঁচায়)
        async for chunk in bot.stream_media(msg, block=True):
            yield chunk
    except Exception as e:
        logger.error(f"Streaming Error: {e}")

# === ফাইল প্রসেসিং ফাংশন ===
async def process_file_logic(message: Message):
    try:
        status_msg = await message.reply_text("⏳ প্রসেসিং হচ্ছে, দয়া করে অপেক্ষা করুন...", quote=True)
        
        # লগ চ্যানেলে ফরওয়ার্ড করা
        try:
            log_msg = await message.forward(LOG_CHANNEL)
        except Exception as e:
            return await status_msg.edit(f"❌ লগ চ্যানেলে ফাইল পাঠানো যায়নি। বটকে চ্যানেলে এডমিন করুন।\nError: {e}")

        file_obj = message.document or message.video or message.audio
        file_data = {
            "message_id": log_msg.id,
            "file_name": getattr(file_obj, 'file_name', 'video.mp4'),
            "file_size": getattr(file_obj, 'file_size', 0)
        }

        # ডাটাবেসে তথ্য জমা রাখা
        res = await files_col.insert_one(file_data)
        db_id = str(res.inserted_id)

        stream_link = f"{WEB_URL}/watch/{db_id}"
        download_link = f"{WEB_URL}/download/{db_id}"

        await status_msg.edit(
            f"✅ **লিঙ্ক জেনারেট সফল!**\n\n📂 **নাম:** `{file_data['file_name']}`\n⚖️ **সাইজ:** {round(file_data['file_size']/(1024*1024), 2)} MB",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📺 Online Stream", url=stream_link)],
                [InlineKeyboardButton("📥 Fast Download", url=download_link)]
            ])
        )
    except Exception as e:
        logger.error(f"Process Error: {e}")

# === বট কমান্ডস ===

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    await message.reply_text(
        f"হ্যালো {message.from_user.first_name}!\n\n"
        "আমি ৪ জিবি+ মুভি স্ট্রিমিং বট।\n"
        "১. কোনো ফাইল আমাকে সরাসরি পাঠাও।\n"
        "২. অথবা কোনো ফাইলের রিপ্লাই দিয়ে লিখো `/link`",
        quote=True
    )

@bot.on_message(filters.command("link") & filters.private)
async def link_command_handler(client, message):
    # যদি কোনো মেসেজের রিপ্লাই দিয়ে /link লিখে
    if message.reply_to_message and (message.reply_to_message.document or message.reply_to_message.video or message.reply_to_message.audio):
        await process_file_logic(message.reply_to_message)
    else:
        await message.reply_text("❌ এই কমান্ডটি ব্যবহার করতে কোনো ভিডিও বা ফাইলের রিপ্লাই দিয়ে `/link` লিখুন।")

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def direct_media_handler(client, message: Message):
    # সরাসরি ফাইল পাঠালে অটো লিংক দিবে
    await process_file_logic(message)

# === FastAPI সেটআপ ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ব্যাকগ্রাউন্ডে বট স্টার্ট হবে যাতে FloodWait থাকলেও ওয়েব সার্ভার সচল থাকে
    asyncio.create_task(bot.start())
    logger.info("✅ Bot background task started!")
    yield
    if bot.is_connected:
        await bot.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def home():
    status = "Online" if bot.is_connected else "Connecting/FloodWait"
    return f"<h1>Bot Status: {status}</h1><p>Send files to your bot to get links.</p>"

@app.head("/")
async def head_home():
    return {"status": "alive"}

@app.get("/watch/{file_id}")
async def watch_file(file_id: str):
    try:
        file_info = await files_col.find_one({"_id": ObjectId(file_id)})
        if not file_info: raise HTTPException(404, "File not found")
        return StreamingResponse(media_generator(file_info['message_id']), media_type="video/mp4")
    except:
        raise HTTPException(400, "Invalid ID")

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    try:
        file_info = await files_col.find_one({"_id": ObjectId(file_id)})
        if not file_info: raise HTTPException(404, "File not found")
        
        headers = {
            "Content-Disposition": f"attachment; filename=\"{file_info['file_name']}\"",
            "Content-Length": str(file_info['file_info'].get('file_size', 0)) if 'file_size' in file_info else None
        }
        return StreamingResponse(media_generator(file_info['message_id']), headers=headers, media_type="application/octet-stream")
    except:
        raise HTTPException(400, "Invalid ID")

if __name__ == "__main__":
    # Render এর জন্য ৮০৮০ পোর্ট ফিক্সড
    uvicorn.run(app, host="0.0.0.0", port=8080)
