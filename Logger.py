from Config import Config
import time
from datetime import datetime
import math
class Logger:
    def __init__(self, app):
        self.app = app

    async def log(self, user, msg):
        now = datetime.fromtimestamp(math.floor(time.time()))

        msg = f"__{now}__\n**{msg}**\n \n\n__Task done by:__ `{user}`"
        try:
            await self.app.send_message(Config.LOGGER_CHANNEL_ID, f"{msg}")
        except Exception as e:
            print(f"Logger Error (Channel ID: {Config.LOGGER_CHANNEL_ID}): {e}")