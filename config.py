import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.environ.get("API_ID", ""))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "")
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", ""))
    WEB_URL = os.environ.get("WEB_URL", "") # Render এর URL (যেমন: https://your-app.onrender.com)
