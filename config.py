import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.environ.get("API_ID", "0"))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "")
    # এখানে int() ব্যবহার করা নিশ্চিত করুন
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0"))
    WEB_URL = os.environ.get("WEB_URL", "").rstrip('/')
