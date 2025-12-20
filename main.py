import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import uvicorn
from config import Config

app = FastAPI()
bot = Client("StreamBot", api_id=Config.API_ID, api_hash=Config.API_HASH, bot_token=Config.BOT_TOKEN)

@bot.on_message(filters.document | filters.video | filters.audio)
async def handle_message(client, message: Message):
    # লগ চ্যানেলে ফাইল ফরওয়ার্ড করা (পার্মানেন্ট লিংকের জন্য)
    log_msg = await message.forward(Config.LOG_CHANNEL)
    
    # ডাউনলোড ও স্টিম লিংক জেনারেট করা
    file_id = log_msg.id
    stream_link = f"{Config.WEB_URL}/watch/{file_id}"
    download_link = f"{Config.WEB_URL}/download/{file_id}"
    
    await message.reply_text(
        f"✅ **File Ready!**\n\n"
        f"📺 **Stream:** {stream_link}\n"
        f"📥 **Download:** {download_link}",
        quote=True
    )

# ৪ জিবি ফাইল স্টিমিং লজিক
async def media_streamer(file_id):
    async with bot:
        message = await bot.get_messages(Config.LOG_CHANNEL, file_id)
        async for chunk in bot.stream_media(message):
            yield chunk

@app.get("/watch/{file_id}")
async def stream_file(file_id: int):
    return StreamingResponse(media_streamer(file_id), media_type="video/mp4")

@app.get("/download/{file_id}")
async def download_file(file_id: int):
    return StreamingResponse(media_streamer(file_id), headers={
        "Content-Disposition": f"attachment; filename=file.mp4"
    })

async def main():
    await bot.start()
    config = uvicorn.Config(app, host="0.0.0.0", port=8080)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
