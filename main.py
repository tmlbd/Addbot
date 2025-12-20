import os
import threading
from flask import Flask, render_template_string, request, Response
import telebot
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import requests

# --- CONFIGURATION (Render Environment Variables-এ এগুলো সেট করবেন) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
# রেন্ডার সাইটের সম্পূর্ণ ইউআরএল (যেমন: https://your-app.onrender.com)
APP_URL = os.environ.get("APP_URL", "").rstrip('/') 
# মনিট্যাগ জোন আইডি (যদি এড দেখাতে চান)
ZONE_ID = os.environ.get("ZONE_ID", "10351894")

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# Database Setup
client = MongoClient(MONGO_URI)
db = client['video_master_db']
video_collection = db['videos']

# --- PREMIUM PLAYER UI (HTML/CSS) ---
PLAYER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watching: {{ title }}</title>
    <!-- Plyr CSS for Premium Look -->
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { background: #0b0f1a; color: #fff; font-family: 'Outfit', sans-serif; margin: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .player-wrapper { width: 100%; max-width: 900px; padding: 10px; box-sizing: border-box; }
        .info { margin-top: 20px; text-align: center; }
        h1 { font-size: 22px; color: #6366f1; margin: 0; }
        .download-btn { margin-top: 15px; display: inline-block; padding: 12px 25px; background: #10b981; color: white; text-decoration: none; border-radius: 12px; font-weight: 600; transition: 0.3s; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3); }
        .download-btn:hover { background: #059669; transform: scale(1.05); }
        /* Monetag Script */
    </style>
    <!-- Monetag SDK -->
    <script src='//libtl.com/sdk.js' data-zone='{{ zone_id }}' data-sdk='show_{{ zone_id }}'></script>
</head>
<body>
    <div class="player-wrapper">
        <video id="player" playsinline controls data-poster="">
            <source src="{{ video_url }}" type="video/mp4" />
        </video>
        <div class="info">
            <h1>{{ title }}</h1>
            <p style="color: #94a3b8; font-size: 14px;">Streamed via Master Bot</p>
            <!-- ডিরেক্ট ডাউনলোড বাটন -->
            <a href="{{ video_url }}" download class="download-btn">📥 Download Video</a>
        </div>
    </div>

    <!-- Plyr JS -->
    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <script>
        const player = new Plyr('#player', {
            controls: ['play-large', 'play', 'progress', 'current-time', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'download', 'fullscreen'],
            download: { enabled: true }
        });
        // অটো এড ট্রিগার (ঐচ্ছিক)
        if(typeof window['show_{{ zone_id }}'] === 'function') {
            setTimeout(() => { window['show_{{ zone_id }}'](); }, 5000);
        }
    </script>
</body>
</html>
"""

# --- TELEGRAM BOT LOGIC ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 **স্বাগতম!**\n\nআমাকে যেকোনো ভিডিও ফাইল পাঠান অথবা ভিডিওর ডাইরেক্ট MP4 লিঙ্ক দিন।\nআমি আপনাকে সেটি অনলাইনে দেখার এবং ডাউনলোড করার লিঙ্ক দিয়ে দেব।")

# ভিডিও ফাইল হ্যান্ডেল করা
@bot.message_handler(content_types=['video', 'document'])
def handle_video_file(message):
    try:
        file_id = ""
        file_name = "Untitled Video"
        
        if message.content_type == 'video':
            file_id = message.video.file_id
            file_name = message.video.file_name or "Video_File"
        else:
            if "video" in message.document.mime_type:
                file_id = message.document.file_id
                file_name = message.document.file_name
            else:
                return bot.reply_to(message, "❌ এটি কোনো ভিডিও ফাইল নয়!")

        # ডাটাবেসে সেভ করা
        data = {
            "title": file_name,
            "type": "telegram",
            "file_id": file_id,
            "date": datetime.now()
        }
        res = video_collection.insert_one(data)
        video_id = str(res.inserted_id)

        watch_url = f"{APP_URL}/watch/{video_id}"
        bot.reply_to(message, f"✅ **ভিডিও সফলভাবে সেভ হয়েছে!**\n\n🎬 **দেখতে বা ডাউনলোড করতে ক্লিক করুন:**\n{watch_url}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# ডাইরেক্ট লিঙ্ক হ্যান্ডেল করা
@bot.message_handler(func=lambda m: True)
def handle_direct_link(message):
    if message.text.startswith("http"):
        link = message.text.strip()
        data = {
            "title": "Online Stream",
            "type": "link",
            "url": link,
            "date": datetime.now()
        }
        res = video_collection.insert_one(data)
        video_id = str(res.inserted_id)

        watch_url = f"{APP_URL}/watch/{video_id}"
        bot.reply_to(message, f"✅ **লিঙ্ক সেভ হয়েছে!**\n\n🎬 **অনলাইনে দেখুন ও ডাউনলোড করুন:**\n{watch_url}", parse_mode="Markdown")

# --- WEB ROUTES ---

@app.route('/')
def index():
    return "Video Streaming & Downloader Bot is Running!"

@app.route('/watch/<vid>')
def watch_video(vid):
    video_data = video_collection.find_one({"_id": ObjectId(vid)})
    if not video_data:
        return "Video Not Found!", 404
    
    if video_data['type'] == 'link':
        v_url = video_data['url']
    else:
        # টেলিগ্রাম ফাইল সরাসরি স্ট্রিমিং করার লিঙ্ক জেনারেট
        file_info = bot.get_file(video_data['file_id'])
        v_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    return render_template_string(PLAYER_HTML, video_url=v_url, title=video_data['title'], zone_id=ZONE_ID)

# বটের পোলিং ফাংশন
def run_polling():
    bot.infinity_polling()

if __name__ == "__main__":
    # বটকে আলাদা থ্রেডে চালানো
    threading.Thread(target=run_polling, daemon=True).start()
    # ফ্ল্যাস্ক ওয়েব সার্ভার শুরু
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
