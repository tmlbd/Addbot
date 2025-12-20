import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.environ.get("API_ID", "12345"))
    API_HASH = os.environ.get("API_HASH", "your_api_hash")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
    MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "your_mongodb_uri")
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-100123456789"))
    WEB_URL = os.environ.get("WEB_URL", "https://your-app-name.onrender.com")
