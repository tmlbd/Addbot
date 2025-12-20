import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn
from config import Config
from database import db
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Client(
    "StreamBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=None # প্লাগইন সিস্টেম অফ রাখলাম সুবিধার জন্য
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.start()
    logger.info("✅ BOT STARTED SUCCESSFULLY!")
    yield
    await bot.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def home():
    return HTMLResponse("<h1>Bot is Live!</h1>")

# Start Command
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    logger.info(f"Start command received from {message.from_user.id}")
    await message.reply_text(f"হ্যালো {message.from_user.first_name}! আমি সচল আছি। আমাকে কোনো ফাইল পাঠান।")

# Media Handler
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_media(client, message: Message):
    logger.info("Media message received!")
    try:
        # ১. ফাইল ফরওয়ার্ড করা
        try:
            log_msg = await message.forward(Config.LOG_CHANNEL)
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return await message.reply_text("❌ লগ চ্যানেলে ফাইল পাঠানো যাচ্ছে না। বটকে চ্যানেলে এডমিন করুন।")

        # ২. ডাটাবেসে সেভ করা
        file_obj = message.document or message.video or message.audio
        file_data = {
            "message_id": log_msg.id,
            "file_name": getattr(file_obj, 'file_name', 'video.mp4'),
            "file_size": getattr(file_obj, 'file_size', 0)
        }
        
        try:
            db_id = await db.insert_file(file_data)
        except Exception as e:
            logger.error(f"Database error: {e}")
            return await message.reply_text("❌ ডাটাবেসে সমস্যা হচ্ছে। আপনার MongoDB URI চেক করুন।")

        # ৩. লিংক জেনারেট করা
        stream_link = f"{Config.WEB_URL}/watch/{db_id}"
        download_link = f"{Config.WEB_URL}/download/{db_id}"

        await message.reply_text(
            f"✅ **ফাইল রেডি!**\n\n📂 `{file_data['file_name']}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📺 Stream", url=stream_link),
                 InlineKeyboardButton("📥 Download", url=download_link)]
            ])
        )
    except Exception as e:
        logger.error(f"General error: {e}")

# স্ট্রিমিং লজিক
async def media_generator(message_id):
    msg = await bot.get_messages(Config.LOG_CHANNEL, message_id)
    async for chunk in bot.stream_media(msg):
        yield chunk

@app.get("/watch/{file_id}")
async def watch(file_id: str):
    file = await db.get_file(file_id)
    if not file: raise HTTPException(404)
    return StreamingResponse(media_generator(file['message_id']), media_type="video/mp4")

@app.get("/download/{file_id}")
async def download(file_id: str):
    file = await db.get_file(file_id)
    if not file: raise HTTPException(404)
    return StreamingResponse(media_generator(file['message_id']), headers={
        "Content-Disposition": f"attachment; filename={file['file_name']}"
    }, media_type="application/octet-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
