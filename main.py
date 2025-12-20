import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn
from config import Config
from database import db

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
bot = Client(
    "StreamBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

@app.on_event("startup")
async def startup():
    if not bot.is_connected:
        await bot.start()
    logger.info("--- Bot is Online and Ready! ---")

@app.on_event("shutdown")
async def shutdown():
    if bot.is_connected:
        await bot.stop()

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h1>Bot is Running Successfully!</h1>"

# Start Command Handler
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    await message.reply_text(
        f"Hello {message.from_user.first_name}!\n\n"
        "আমি স্ট্রিমিং এবং ডাউনলোড লিংক বট। আমাকে যেকোনো ফাইল বা ভিডিও ফরওয়ার্ড করো, আমি তোমাকে ৪ জিবি+ সাপোর্ট সহ লিংক দিয়ে দিব।",
        quote=True
    )

# Media Handler (Forwards and Direct Uploads)
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_media(client, message: Message):
    try:
        msg = await message.reply_text("প্রসেসিং হচ্ছে, দয়া করে অপেক্ষা করুন...", quote=True)
        
        # Log চ্যানেলে ফাইল ফরওয়ার্ড করা
        # নিশ্চিত করুন বট লগ চ্যানেলে অ্যাডমিন এবং আইডি সঠিক (-100 সহ)
        try:
            log_msg = await message.forward(Config.LOG_CHANNEL)
        except Exception as e:
            await msg.edit(f"❌ এরর: লগ চ্যানেলে ফাইল পাঠানো যাচ্ছে না। নিশ্চিত করুন বট চ্যানেলে অ্যাডমিন।\nError: {e}")
            return

        file = message.document or message.video or message.audio
        file_data = {
            "message_id": log_msg.id,
            "file_name": getattr(file, 'file_name', 'video.mp4'),
            "file_size": getattr(file, 'file_size', 0)
        }
        
        db_id = await db.insert_file(file_data)
        
        stream_link = f"{Config.WEB_URL}/watch/{db_id}"
        download_link = f"{Config.WEB_URL}/download/{db_id}"

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 Stream Online", url=stream_link)],
            [InlineKeyboardButton("📥 Fast Download", url=download_link)]
        ])

        await msg.edit(
            f"✅ **ফাইল রেডি!**\n\n"
            f"📂 **নাম:** `{file_data['file_name']}`\n"
            f"⚖️ **সাইজ:** {round(file_data['file_size'] / (1024*1024), 2)} MB",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error handling media: {e}")
        await message.reply_text(f"দুঃখিত, কোনো একটি সমস্যা হয়েছে।\nError: {e}")

# 4GB+ Stream Logic (Session reuse fix)
async def media_generator(message_id):
    # এখানে আবার async with bot: দেওয়ার দরকার নেই কারণ বট অলরেডি রানিং
    try:
        msg = await bot.get_messages(Config.LOG_CHANNEL, message_id)
        async for chunk in bot.stream_media(msg):
            yield chunk
    except Exception as e:
        logger.error(f"Stream error: {e}")

@app.get("/watch/{file_id}")
async def watch_file(file_id: str):
    file_info = await db.get_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    return StreamingResponse(media_generator(file_info['message_id']), media_type="video/mp4")

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    file_info = await db.get_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    
    headers = {
        "Content-Disposition": f"attachment; filename=\"{file_info['file_name']}\"",
        "Content-Length": str(file_info['file_size'])
    }
    return StreamingResponse(media_generator(file_info['message_id']), headers=headers, media_type="application/octet-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
