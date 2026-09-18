import csv
import pyrebase
from Cred import Cred
from Config import Config
import time
import math
from Logger import Logger

class FDB:

    def __init__(self, status, app):
        firebase = pyrebase.initialize_app(Cred.FIREBASE_CONF)
        self.db = firebase.database()
        print(f"DB connect ok: {status}")
        self.log = Logger(app)
    
    async def add_user(self, message):
        username = "N/A"
        if message.chat.username:
            username = message.chat.username
        data = {
            "username": username,
            "id": str(message.chat.id),
            "first_name": message.chat.first_name,
            "started": str(math.floor(time.time())),
            "last_searched": "N/A",
            "points": "0",
            "status": "user",
            "blocked": "0",
            "safe": "0"
        }
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(message.chat.id)}").set(data)
        await self.log.log(message.chat.id, "User added to the database")
        print(f"{message.chat.id} - User added to the database")
    
    async def check_user(self, message):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(message.chat.id)}").get().val()
        # user in db
        if data:
            # blocked user
            if int(data["blocked"]) == 1:
                return False

            # normal user
            elif int(data["blocked"]) == 0:
                return True
        # user not in db. need to add
        else:
            await self.add_user(message)
            return True
    
    async def add_last_searched(self, user,searched_txt):
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/last_searched").set(searched_txt)
        await self.log.log(user, f"User searched: {searched_txt}")

    def get_last_searched(self, user):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/last_searched").get().val()
        if data:
            return data
        else:
            return None
        
    async def add_safe(self, user, on_or_off):
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/safe").set(on_or_off)
        mod = "off"
        if int(on_or_off) == 1:
            mod = "on"
        await self.log.log(user, f"User changed search mod: {mod}")

    def get_safe(self, user):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/safe").get().val()
        # off
        if data == "0":
            return False
        # on
        elif data == "1":
            return True
        
        else:
            return None
        
    async def set_always_listen(self, user, status):
        # status: "0" for off, "1" for on
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/always_listen").set(status)
        mode = "on" if str(status) == "1" else "off"
        await self.log.log(user, f"Group changed always listen mode: {mode}")

    def get_always_listen(self, user):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/always_listen").get().val()
        if data == "1":
            return True
        return False

    def block_user(self, user):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/blocked").get().val()
        if data == "1":
            return False
        elif data == "0":
            self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/blocked").set("1")
            return True
        else:
            return None

    def unblock_user(self, user):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/blocked").get().val()
        if data == "1":
            self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/blocked").set("0")
            return True
        elif data == "0":
            return False
        else:
            return None

    def add_points(self, user):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/points").get().val()      
        if data:
            points = int(data) + 1
            self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}/points").set(str(points))


    def user_exists(self, user):
        data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}").get().val()
        if data:
            return True
        else:
            return False
        

    def get_user_details(self, user):
        try:
            data = self.db.child(f"{Config.BOT_DB_PATH}/users/{str(user)}").get().val()
            print("data collected successfully!")
            if data:
                print("went to if looop successfully!")
                return data
                print("data returned successfully!")
                print(data)
            else:
                return None
        except Exception as e:
            print("following error occured", e)

    async def add_channel(self, chat_id, chat_name, username):
        data = {
            "username": username if username else "N/A",
            "id": str(chat_id),
            "first_name": chat_name,
            "started": str(math.floor(time.time())),
            "last_searched": "N/A",
            "points": "0",
            "status": "channel", # Distinct status
            "blocked": "0",
            "safe": "0",
            "category": "N/A" # Default category
        }
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(chat_id)}").set(data)
        print(f"{chat_id} - Channel added to the database")

    async def update_category(self, chat_id, category):
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(chat_id)}/category").set(category)
        print(f"{chat_id} - Category updated to {category}")

    def get_adult_channels(self):
        try:
            users = self.db.child(f"{Config.BOT_DB_PATH}/users").get().val()
            adult_channels = []
            if users:
                if isinstance(users, dict):
                    # Iterate over dictionary values
                    for uid, data in users.items():
                        if isinstance(data, dict) and data.get("category") == "adult":
                            adult_channels.append(uid)
                elif isinstance(users, list):
                     # Iterate over list items (skipping None)
                    for data in users:
                        if data and isinstance(data, dict) and data.get("category") == "adult":
                            # Assuming 'id' is in the data if it's a list
                            if "id" in data:
                                adult_channels.append(data["id"])
            return adult_channels
        except Exception as e:
            print(f"Error fetching adult channels: {e}")
            return []

