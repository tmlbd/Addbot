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

# বট ক্লায়েন্ট
bot = Client(
    "StreamBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.start()
    logger.info("🚀 BOT IS ONLINE NOW!")
    yield
    await bot.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def home():
    return HTMLResponse("<h1>Bot is Online!</h1>")

# ১. স্টার্ট কমান্ড টেস্ট (কোনো ডাটাবেস ছাড়া)
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    logger.info(f"📩 Start command received from {message.from_user.id}")
    await message.reply_text(f"হ্যালো {message.from_user.first_name}!\nবট সচল আছে। আমাকে ফাইল পাঠান।")

# ২. মিডিয়া হ্যান্ডলার (ভিডিও/অডিও/ফাইল)
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def media_handler(client, message: Message):
    logger.info("📩 Media file received!")
    
    # প্রসেসিং মেসেজ
    status_msg = await message.reply_text("প্রসেসিং হচ্ছে...", quote=True)

    try:
        # লগ চ্যানেলে ফরওয়ার্ড
        logger.info("Forwarding to log channel...")
        log_msg = await message.forward(Config.LOG_CHANNEL)
        
        file_obj = message.document or message.video or message.audio
        file_data = {
            "message_id": log_msg.id,
            "file_name": getattr(file_obj, 'file_name', 'file.mp4'),
            "file_size": getattr(file_obj, 'file_size', 0)
        }

        # ডাটাবেসে সেভ
        logger.info("Saving to database...")
        db_id = await db.insert_file(file_data)
        
        if not db_id:
            await status_msg.edit("❌ ডাটাবেসে কানেক্ট করা যাচ্ছে না। আপনার মঙ্গোডিবি ইউআরএল চেক করুন।")
            return

        # লিঙ্ক তৈরি
        stream_link = f"{Config.WEB_URL}/watch/{db_id}"
        download_link = f"{Config.WEB_URL}/download/{db_id}"

        await status_msg.edit(
            f"✅ **লিঙ্ক রেডি!**\n\n📂 `{file_data['file_name']}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📺 Stream Online", url=stream_link)],
                [InlineKeyboardButton("📥 Fast Download", url=download_link)]
            ])
        )
        logger.info("✅ Links sent successfully!")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit(f"❌ এরর হয়েছে: {str(e)}")

# ৩. স্ট্রিমিং ও ডাউনলোড লজিক
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
    headers = {"Content-Disposition": f"attachment; filename={file['file_name']}"}
    return StreamingResponse(media_generator(file['message_id']), headers=headers, media_type="application/octet-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
