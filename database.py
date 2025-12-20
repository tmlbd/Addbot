from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_DB_URI)
        self.db = self.client.StreamBotDB
        self.files = self.db.files

    async def insert_file(self, file_data):
        res = await self.files.insert_one(file_data)
        return str(res.inserted_id)

    async def get_file(self, file_id):
        from bson import ObjectId
        return await self.files.find_one({"_id": ObjectId(file_id)})

db = Database()
