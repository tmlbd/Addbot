from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import asyncio

class Database:
    def __init__(self):
        # কানেকশনে ৫ সেকেন্ড টাইমআউট দেওয়া হয়েছে
        self.client = AsyncIOMotorClient(Config.MONGO_DB_URI, serverSelectionTimeoutMS=5000)
        self.db = self.client.StreamBotDB
        self.files = self.db.files

    async def insert_file(self, file_data):
        try:
            res = await self.files.insert_one(file_data)
            return str(res.inserted_id)
        except Exception as e:
            print(f"DB Insert Error: {e}")
            return None

    async def get_file(self, file_id):
        from bson import ObjectId
        try:
            return await self.files.find_one({"_id": ObjectId(file_id)})
        except Exception as e:
            print(f"DB Get Error: {e}")
            return None

db = Database()
