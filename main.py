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

app = FastAPI()
bot = Client(
    "StreamBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

@app.on_event("startup")
async def startup():
    await bot.start()
    logging.info("Bot is online!")

@app.on_event("shutdown")
async def shutdown():
    await bot.stop()

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h1>Bot is Running Successfully!</h1>"

# Telegram Media Handler
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_media(client, message: Message):
    try:
        # Forward to Log Channel
        log_msg = await message.forward(Config.LOG_CHANNEL)
        
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

        await message.reply_text(
            f"✅ **File Ready to Stream!**\n\n"
            f"📂 **Name:** `{file_data['file_name']}`\n"
            f"⚖️ **Size:** {round(file_data['file_size'] / (1024*1024), 2)} MB",
            reply_markup=reply_markup,
            quote=True
        )
    except Exception as e:
        logging.error(e)
        await message.reply_text("An error occurred.")

# 4GB+ Stream Logic
async def media_generator(message_id):
    async with bot:
        msg = await bot.get_messages(Config.LOG_CHANNEL, message_id)
        async for chunk in bot.stream_media(msg):
            yield chunk

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
        "Content-Disposition": f"attachment; filename={file_info['file_name']}",
        "Content-Length": str(file_info['file_size'])
    }
    return StreamingResponse(media_generator(file_info['message_id']), headers=headers, media_type="application/octet-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
