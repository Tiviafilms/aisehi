from Config import Config
import requests
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.types import InputMediaPhoto, InputMediaVideo, ForceReply
from pyrogram.enums import ChatMemberStatus
from DB import FDB
import math
import time
from datetime import datetime
from better_profanity import profanity
from Logger import Logger
from Logger import Logger
import urllib.parse
import json
import os
import difflib
import yt_dlp
import logging # Added for logging errors safely
from linkvertise import LinkvertiseClient

class Process:
    def __init__(self, app):
        self.app = app
        self.dbh = FDB("process db ok", app)
        self.db = self.dbh.db
        self.log = Logger(app)

    def fetch_all_mixdrop_files(self):
        all_files = []
        page = 1
        print("Fetching all files from Mixdrop...")
        while True:
            try:
                url = f"https://api.mixdrop.ag/folderlist?email={Config.MIXDROP_EMAIL}&key={Config.MIXDROP_KEY}&page={page}"
                res = requests.get(url).json()
                if res.get('success'):
                    files = res.get('result', {}).get('files', [])
                    if not files:
                        break
                    all_files.extend(files)
                    print(f"Fetched page {page}, total files so far: {len(all_files)}")
                    page += 1
                else:
                    print(f"Mixdrop API error on page {page}: {res.get('result', {}).get('msg')}")
                    break
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break
        
        # Save to cache
        try:
            with open(Config.MIXDROP_CACHE_FILE, 'w') as f:
                json.dump(all_files, f)
            print(f"Cached {len(all_files)} files to {Config.MIXDROP_CACHE_FILE}")
        except Exception as e:
            print(f"Error saving cache: {e}")
        
        return all_files

    def get_cached_files(self, force_refresh=False):
        # Check if cache exists and is fresh (less than 1 hour old)
        if os.path.exists(Config.MIXDROP_CACHE_FILE):
            last_modified = os.path.getmtime(Config.MIXDROP_CACHE_FILE)
            if time.time() - last_modified > 3600:
                print("Cache expired (older than 1 hour), refreshing...")
                force_refresh = True

        if force_refresh or not os.path.exists(Config.MIXDROP_CACHE_FILE):
            print("Refreshing cache from Mixdrop...")
            return self.fetch_all_mixdrop_files()
        
        try:
            with open(Config.MIXDROP_CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return self.fetch_all_mixdrop_files()
            
    def format_duration(self, seconds):
        if not seconds:
            return "N/A"
        try:
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h:d}:{m:02d}:{s:02d}"
            else:
                return f"{m:02d}:{s:02d}"
        except:
            return "N/A"

    def search_mixdrop_internal(self, query):
        print("Searching for", query, "in cache...")
        files = self.get_cached_files()
        query_words = query.lower().split()
        
        def match(title):
            title_words = title.lower().split()
            # Check if any query word matches any title word exactly
            for q_word in query_words:
                if q_word in title_words:
                    return True
            return False

        results = [f for f in files if match(f.get('title', ''))]
        
        if not results:
            print("No results in cache, refreshing...")
            files = self.get_cached_files(force_refresh=True)
            results = [f for f in files if match(f.get('title', ''))]
            
        # Rank results by relevance (SequenceMatcher ratio)
        if results:
            results.sort(key=lambda f: difflib.SequenceMatcher(None, query.lower(), f.get('title', '').lower()).ratio(), reverse=True)
            
        return results

    def linkvertise_cover(self, url):
        try:
            client = LinkvertiseClient()
            return client.linkvertise(Config.LINKVERTISE_ID, url)
        except Exception as e:
            print(f"Linkvertise Error: {e}")
            return url
    
    
    def get_video_url(self, file_code):
        try:
            # mixdrop uses file_ref generally, or we can get info via fileinfo2
            # We need to construct the URL or fetch info to get the download link
            # Config.MIXDROP_EMAIL and KEY are needed
            
            # Note: The search result 'file_code' (fileref) acts as the ID.
            
            url = f"https://api.mixdrop.ag/fileinfo2?email={Config.MIXDROP_EMAIL}&key={Config.MIXDROP_KEY}&ref[]={file_code}"
            res = requests.get(url)
            
            if res.status_code == 200:
                json_data = res.json()
                if json_data.get("success"):
                    # fileinfo2 returns a dict where keys are filerefs
                    result = json_data["result"]
                    if file_code in result:
                        data = result[file_code]
                        # "url" is usually the download/stream page, "embedurl" is embed
                        # The user wants "Watch" and "Download". 
                        # Mixdrop 'url' serves as a download/watch page.
                        # 'embedurl' for embedding.
                        
                        movie_url = data.get('embedurl') # User asked for Watch 🔗
                        movie_url2 = data.get('url')     # User asked for Download 🔗
                        size = data.get('size')
                        
                        thumb = data.get('thumb') # Get real thumbnail
                        duration = data.get('duration') # Get duration
                        
                        # Linkvertise cover for the download link if desired, or just raw. 
                        # process.py logic used linkvertise_cover on url2. 
                        
                        return movie_url, self.linkvertise_cover(movie_url2), size, thumb, duration
                    else:
                        print(f"File code {file_code} not found in response")
                else:
                    print(f"Mixdrop API error: {json_data.get('result', {}).get('msg')}")

            print("Conn ERR")
            return None, None, None
        except Exception as e:
            print(f"Connection ERR: {e}")
            return None, None, None

    def shorten_url(self, long_url):
        try:
            # Use Bitly API to shorten the URL
            headers = {
                'Authorization': f'Bearer {Cred.BITLY_TOKEN}',
                'Content-Type': 'application/json',
            }
            data = {
                "long_url": long_url,
                "domain": "bit.ly"  # Optional, defaults to bit.ly
            }
            # Bitly v4 API endpoint
            response = requests.post('https://api-ssl.bitly.com/v4/shorten', headers=headers, json=data)
            
            if response.status_code in [200, 201]:
                return response.json().get('link')
            else:
                print(f"Bitly Error: {response.status_code} - {response.text}")
                return long_url # Return original if shortening fails
        except Exception as e:
            print(f"Shorten URL Exception: {e}")
            return long_url


    async def search_movie(self, message, search_text, load_count):
        processing_msg = None
        if load_count != 0:
            processing_msg = await message.edit_message_text("♻️ Processing...")
            message = message.message
        else:
            processing_msg = await self.app.send_message(message.chat.id, "♻️ Processing...")
            await self.dbh.add_last_searched(message.chat.id, message.text)
        try:
            data = self.search_mixdrop_internal(search_text)

            if self.dbh.get_safe(message.chat.id):
                data = self.filter_data(data)
            
            if len(data) > 0:
                if load_count == 0:
                     await self.app.send_message(message.chat.id, f"`Found {len(data)} results for '{search_text}'`")
                count = load_count * Config.MAX_LOAD_COUNT
                # for movie in data:
                for i in range(Config.MAX_LOAD_COUNT):
                    if count < len(data):
                        item = data[count]
                        file_code = item.get("fileref")
                        title = item.get("title")
                        
                        # Placeholders for missing data
                        splash_img = "https://dummyimage.com/600x400/000/fff&text=" + urllib.parse.quote(title)
                        single_img = splash_img
                        views = "N/A"
                        
                        print(count,"-",title)
                        length = "N/A"
                        size_bytes = item.get("size", 0)
                        size = self.humanbytes(int(size_bytes))

                        movie_url, movie_url2, detailed_size, thumb, duration = self.get_video_url(file_code)
                        # If fetch worked, we surely have links.
                        
                        if thumb:
                            splash_img = thumb
                            single_img = thumb
                        
                        if duration:
                            length = self.format_duration(duration)

                        if movie_url is not None:
                            await self.send_movie(message, file_code, splash_img, views, single_img, title, length, movie_url, size, movie_url2)
                    count += 1
                    time.sleep(2)
                    
                if len(data) > (load_count + 1) * Config.MAX_LOAD_COUNT:
                    await self.app.send_message(message.chat.id, "Press bellow to load more",reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Load more 🔄", callback_data=f"load_{load_count + 1}")]]))
            else:
                print("Not found any data")
                await self.app.send_message(message.chat.id, f"Sorry did not found the movie. May be turn off the safe search mod will find your content `{Config.SAFE_SEARCH_COMMAND} off`. Press the button to send a request to add last searched item.",reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Request to add movie", callback_data=f"req_add")]
            ]
        ))
                

        except Exception as e:
            print(e)
            return None
        finally:
            if processing_msg:
                try:
                    await processing_msg.delete()
                except:
                    pass
    
    async def multi_search_movie(self, message, search_text, load_count, word_index):
        data = {}
        count = 0
        processing_msg = None
        if load_count == 0 and word_index == 0:
            processing_msg = await self.app.send_message(message.chat.id, "♻️ Processing...")
            await self.dbh.add_last_searched(message.chat.id, message.text)
        else:
            processing_msg = await message.edit_message_text("♻️ Processing...")
            message = message.message
        try:
            key_word = search_text.split("&")[word_index].strip()
            # Mixdrop search internal handles the search
            data = self.search_mixdrop_internal(key_word)

            if self.dbh.get_safe(message.chat.id):
                data = self.filter_data(data)
            
            if len(data) > 0:
                if load_count == 0:
                    await self.app.send_message(message.chat.id, f"`Found {len(data)} results for '{key_word}'`")
                count = load_count * Config.MAX_LOAD_COUNT
                # for movie in data:
                for i in range(Config.MAX_LOAD_COUNT):
                    if count < len(data):
                        item = data[count]
                        file_code = item.get("fileref")
                        title = item.get("title")
                        
                        splash_img = "https://dummyimage.com/600x400/000/fff&text=" + urllib.parse.quote(title)
                        single_img = splash_img
                        views = "N/A"
                        
                        print(count,"-",title)
                        length = "N/A"
                        size_bytes = item.get("size", 0)
                        size = self.humanbytes(int(size_bytes))

                        movie_url, movie_url2, detailed_size, thumb, duration = self.get_video_url(file_code)
                        # If fetch worked...
                        
                        if thumb:
                            splash_img = thumb
                            single_img = thumb

                        if duration:
                            length = self.format_duration(duration)
                            
                        if movie_url is not None:
                             await self.send_movie(message, file_code, splash_img, views, single_img, title, length, movie_url, size, movie_url2)
                    count += 1
                    time.sleep(2)
                if len(data) > (load_count + 1) * Config.MAX_LOAD_COUNT:
                    await self.app.send_message(message.chat.id, "Press bellow to load more",reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Load more 🔄", callback_data=f"multi_{load_count + 1}-{word_index}")]]))
            else:
                print("Not found any data")
                await self.app.send_message(message.chat.id, f"Sorry did not found the movie. May be turn off the safe search mod will find your content `{Config.SAFE_SEARCH_COMMAND} off`. Press the button to send a request to add last searched item.",reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Request to add movie", callback_data=f"req_add")]
                ]))
                
                word_index += 1
                if len(search_text.split('&')) > word_index:
                    await self.app.send_message(message.chat.id, f"Press bellow to load next key-word: {search_text.split('&')[word_index].strip()}",reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Load more 🔄", callback_data=f"multi_0-{word_index}")]]))
                

        except IndexError:
            if len(search_text.split("&")) > word_index + 1:
                word_index += 1
                await self.app.send_message(message.chat.id, f"Press bellow to load next key-word: {search_text.split('&')[word_index].strip()}",reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Load more 🔄", callback_data=f"multi_0-{word_index}")]]))
            else:
                pass
        except Exception as e:
            print(e)
            return None
        finally:
            if processing_msg:
                try:
                    await processing_msg.delete()
                except:
                    pass
    
    
    async def delete_message_delayed(self, chat_id, message_id, delay):
        try:
            await asyncio.sleep(delay)
            await self.app.delete_messages(chat_id, message_id)
            # self.log.log(chat_id, f"Auto-deleted message {message_id}") # Optional logging
        except Exception as e:
            print(f"Error auto-deleting message: {e}")

    async def send_movie(self,message, file_code, splash_img, views, single_img, title, length, movie_url, size, movie_url2):
        # await self.app.send_message(message.chat.id, )
        buttons = [
                    [InlineKeyboardButton("Watch 🔗", url=movie_url + ("&autoplay=1" if "?" in movie_url else "?autoplay=1"))],
                    [InlineKeyboardButton("Download 🔗", url=movie_url2)],
                ]
        
        if message.chat.id in Config.ADMIN:
            buttons.append([InlineKeyboardButton("Forward to channels", callback_data="forward_to_channels")])

        sent_msg = await self.app.send_photo(
            message.chat.id,
            single_img, # DO not change this line
            caption=f"__Movie name:__ **{title}**\n \n__Length:__ **{length}**\n__Size:__ **{size}**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        # Schedule auto-deletion after 1 hour (3600 seconds)
        asyncio.create_task(self.delete_message_delayed(sent_msg.chat.id, sent_msg.id, 3600))


    async def handle_movie_req(self, query):
        searched = self.dbh.get_last_searched(query.message.chat.id)
        await query.edit_message_text(f'Your request has been sent to the admin. Thank you!\n \nRequest: {searched}')
        if searched == "N/A" or searched == None:
            self.app.send_message(query.message.chat.id, "Sorry! Try again...")
        else:
            username = "N/A"
            if query.message.chat.username:
                username = f"@{query.message.chat.username}"

            msg = f"User ID: {query.message.chat.id}\nUser first name: {query.message.chat.first_name}\nUsername: {username}\nDate: {query.message.date}\n \nRequest: {searched}"
            encoded_searched = urllib.parse.quote(searched)
            for admin in Config.ADMIN:
                await self.app.send_message(admin, msg, reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Send default message ✅", callback_data=f"dm_{query.message.chat.id}")],
                    [InlineKeyboardButton("Send custom message ⚠️", callback_data=f"cm_{query.message.chat.id}")]
                ]
            ))
            await self.log.log(query.message.chat.id, f"User requested a movie: {searched}")
        

    def start(self):
        _format = {
            "username": "0",
            "id": "0",
            "first_name": "0",
            "started": str(math.floor(time.time())),
            "last_searched": "0",
            "points": "0",
            "status": "bot",
            "blocked": "0",
            "safe": "0"
        }
        _format_group = {
            "username": "0",
            "id": f"{str(Config.GROUP_ID)}",
            "first_name": "0",
            "started": str(math.floor(time.time())),
            "last_searched": "0",
            "points": "0",
            "status": "group",
            "blocked": "0",
            "safe": "0"
        }
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(0)}").set(_format)
        self.db.child(f"{Config.BOT_DB_PATH}/users/{str(Config.GROUP_ID)}").set(_format_group)
        print("db created")
        Config.starting_point.append(time.time())

    
    async def handle_block(self, message):
        if Config.BLOCK_USER_COMMAND == message.text:
            await self.app.send_message(message.chat.id, f"Send this command like this:\n\n`{Config.BLOCK_USER_COMMAND} user_id`")
            return
        user = str(message.text).split(f"{Config.BLOCK_USER_COMMAND} ")[-1]

        if int(message.chat.id) in Config.ADMIN:
            if int(user) in Config.ADMIN:
                await self.app.send_message(message.chat.id, "Admins cannot block or unblock admins!")
                return
            ans = self.dbh.block_user(user)
            if ans == True:
                await self.app.send_message(message.chat.id, "User blocked")
                await self.log.log(f"{message.chat.id}", f"Admin blocked the user: {user}")
            elif ans == False:
                await self.app.send_message(message.chat.id, "User already blocked!")
            else:
                await self.app.send_message(message.chat.id, "Something went wrong! Try again...")
                
                


    async def handle_unblock(self, message):
        if Config.UNBLOCK_USER_COMMAND == message.text:
            await self.app.send_message(message.chat.id, f"Send this command like this:\n\n`{Config.UNBLOCK_USER_COMMAND} user_id`")
            return
        user = str(message.text).split(f"{Config.UNBLOCK_USER_COMMAND} ")[-1]
        
        if int(message.chat.id) in Config.ADMIN:
            if int(user) in Config.ADMIN:
                await self.app.send_message(message.chat.id, "Admins cannot block or unblock admins!")
                return
            ans = self.dbh.unblock_user(user)
            if ans == True:
                await self.app.send_message(message.chat.id, "User unblocked")
                await self.log.log(f"{message.chat.id}", f"Admin unblocked the user: {user}")
            elif ans == False:
                await self.app.send_message(message.chat.id, "User already unblocked!")
            else:
                await self.app.send_message(message.chat.id, "Something went wrong! Try again...")


        # Checking Runtime
    async def check_runtime(self, message):
        if int(message.chat.id) in Config.ADMIN:
            now = time.time()
            now = math.floor((now - Config.starting_point[0]) * 1000)
            now = self.timeFormatter(now)
            await self.app.send_message(
                message.chat.id, f"__Bot running time -__ **{now}**")
            await self.log.log(message.chat.id, f"Admin checked the runtime: **{now}**")
            
    # Time formatter
    def timeFormatter(self, milliseconds: int) -> str:
        seconds, milliseconds = divmod(int(milliseconds), 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        tmp = ((str(days) + "d, ") if days else "") + \
            ((str(hours) + "h, ") if hours else "") + \
            ((str(minutes) + "m, ") if minutes else "") + \
            ((str(seconds) + "s, ") if seconds else "") + \
            ((str(milliseconds) + "ms, ") if milliseconds else "")
        return tmp[:-2]

    async def send_broadcast(self, message):
        users_data = self.db.child(f"{Config.BOT_DB_PATH}/users").get().val()
        user_lst = []
        if users_data:
            if isinstance(users_data, dict):
                user_lst = [int(k) for k in users_data.keys()]
            elif isinstance(users_data, list):
                user_lst = [i for i, v in enumerate(users_data) if v is not None]
        msg = str(message.text).replace(Config.BROADCAST_SYMBOL, "")
        try:
            for user in user_lst:
                try:
                    if user != 0:
                        await self.app.send_message(user, msg)
                except:
                    pass
            await self.app.send_message(
                message.chat.id, "**Promo message sent to all other users**")
            await self.log.log(message.chat.id, f"Admin broadcasted a message\nMessage: {msg}")

        except:
            pass
            


    # Send promotion messages to all the users
    async def send_promo_message(self, message):
        users_data = self.db.child(f"{Config.BOT_DB_PATH}/users").get().val()
        print("fetched users list successfully!")
        
        user_lst = []
        if users_data:
            if isinstance(users_data, dict):
                user_lst = [int(k) for k in users_data.keys()]
            elif isinstance(users_data, list):
                # Filter out None values in case of sparse list
                user_lst = [i for i, v in enumerate(users_data) if v is not None]
        
        print(f"Broadcasting to {len(user_lst)} users...")
        print("now looping through user's list...")
        print("now looping through user's list...")

        try:
            reply = message.reply_to_message
            for user in user_lst:
                try:
                    if user != 0:
                        if reply.text:
                            await self.app.send_message(user, reply.text)
                        if reply.video:
                            await self.app.send_video(user, reply.video.file_id,
                                                caption=reply.caption)
                        if reply.photo:
                            await self.app.send_photo(user, reply.photo.file_id,
                                                caption=reply.caption)
                        if reply.sticker:
                            await self.app.send_sticker(user, reply.sticker.file_id)
                        if reply.document:
                            await self.app.send_document(user, reply.document.file_id,
                                                   caption=reply.caption)
                        if reply.audio:
                            await self.app.send_audio(user, reply.audio.file_id,
                                                caption=reply.caption)
                        if reply.animation:
                            await self.app.send_animation(user, reply.animation.file_id,
                                                    caption=reply.caption)
                except:
                    pass

            await self.app.send_message(
                message.chat.id, "**Promo message sent to all other users**")
            await self.log.log(message.chat.id, f"Admin broadcasted a message")
        except:
            await self.app.send_message(
                message.chat.id, "**Cannot send the promo message. Try repling to a massege\n Or some error occured**")
            
    
    async def get_id(self, message):
        username = "N/A"
        if message.chat.username:
            username = message.chat.username
        msg = f"Your details\n \nID: `{message.chat.id}`\nUsername: `{username}`\nFirst Name: {message.chat.first_name}\nPersonal link: {Config.BOT_LINK}?start={message.chat.id}"
        
        data = self.dbh.get_user_details(message.chat.id)
        if data:
            safe = "off"
            if data["safe"] == "1":
                safe = "on"
            msg += f"\nSafe mod: {safe}\nPoints: {data['points']}\nLast searched: {data['last_searched']}\n \n**If you shared the `Personal link` to other users and if someone starts the bot with your link you will get 1 point. Maybe you will become a winner!** 🥳"
        
        await self.app.send_message(message.chat.id, msg)
        await self.log.log(message.chat.id, f"User checked the id.\n**{msg}**")

    # Check the usage of the bot
    async def is_user_in_channel(self, message):
        try:
            cht_member = await self.app.get_chat_member(
                Config.SUBSCRIBE_CHANNEL, message.chat.id)
            if cht_member.status == ChatMemberStatus.MEMBER or cht_member.status == ChatMemberStatus.OWNER or cht_member.status == ChatMemberStatus.ADMINISTRATOR:
                return True

        except:

            text = f"__To use this bot you needs to subscribe <a href='{Config.SUBSCRIBE_CHANNEL_URL}'>this</a> Telegram channel.__\nAfter you join the channel, **You can search movies** ❤️\n \n \n__Developed by @upekshaip__"
            button = InlineKeyboardButton(
                "Join Channel", url=Config.SUBSCRIBE_CHANNEL_URL)
            keyboard = InlineKeyboardMarkup([[button]])
            # Use the send_message() method to send the message with the button
            await self.app.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=keyboard
            )
            return False
        
        
    def filter_data(self, data):
        modified = []
        for movie in data:
            if not self.check_censor(movie["title"]):
                modified.append(movie)
        return modified

    def check_censor(self, txt):
        dirty_text = ["deepfake","booty","Niksindian","Milf", "xnxx", "tits","notmygrandpa", "mom", "sister", "family","taboo" ,"Blackmail","daddy", "fck","Fked","DRCSSKMHD","Swap","suck","streamtape","incext","cuckold","bdsm","roleplay", "porn", "xvideos", "xhamster", "pornhub", "phub", "hardcore" , "softcore" ,"mommy",'4r5e', '5h1t', '5hit', 'a55', 'anal', 'anus', 'ar5e', 'arrse', 'arse', 'ass', 'ass-fucker', 'asses', 'assfucker', 'assfukka', 'asshole', 'assholes', 'asswhole', 'a_s_s', 'b!tch', 'b00bs', 'b17ch', 'b1tch', 'ballbag', 'balls', 'ballsack', 'bastard', 'beastial', 'beastiality', 'bellend', 'bestial', 'bestiality', 'bi+ch', 'biatch', 'bitch', 'bitcher', 'bitchers', 'bitches', 'bitchin', 'bitching', 'bloody', 'blow job', 'blowjob', 'blowjobs', 'boiolas', 'bollock', 'bollok', 'boner', 'boob', 'boobs', 'booobs', 'boooobs', 'booooobs', 'booooooobs', 'breasts', 'buceta', 'bugger', 'bum', 'bunny fucker', 'butt', 'butthole', 'buttmuch', 'buttplug', 'c0ck', 'c0cksucker', 'carpet muncher', 'cawk', 'chink', 'cipa', 'cl1t', 'clit', 'clitoris', 'clits', 'cnut', 'cock', 'cock-sucker', 'cockface', 'cockhead', 'cockmunch', 'cockmuncher', 'cocks', 'cocksuck ', 'cocksucked ', 'cocksucker', 'cocksucking', 'cocksucks ', 'cocksuka', 'cocksukka', 'cok', 'cokmuncher', 'coksucka', 'coon', 'cox', 'crap', 'cum', 'cummer', 'cumming', 'cums', 'cumshot', 'cunilingus', 'cunillingus', 'cunnilingus', 'cunt', 'cuntlick ', 'cuntlicker ', 'cuntlicking ', 'cunts', 'cyalis', 'cyberfuc', 'cyberfuck ', 'cyberfucked ', 'cyberfucker', 'cyberfuckers', 'cyberfucking ', 'd1ck', 'damn', 'dick', 'dickhead', 'dildo', 'dildos', 'dink', 'dinks', 'dirsa', 'dlck', 'dog-fucker', 'doggin', 'dogging', 'donkeyribber', 'doosh', 'duche', 'dyke', 'ejaculate', 'ejaculated', 'ejaculates ', 'ejaculating ', 'ejaculatings', 'ejaculation', 'ejakulate', 'f u c k', 'f u c k e r', 'f4nny', 'fag', 'fagging', 'faggitt', 'faggot', 'faggs', 'fagot', 'fagots', 'fags', 'fanny', 'fannyflaps', 'fannyfucker', 'fanyy', 'fatass', 'fcuk', 'fcuker', 'fcuking', 'feck', 'fecker', 'felching', 'fellate', 'fellatio', 'fingerfuck ', 'fingerfucked ', 'fingerfucker ', 'fingerfuckers', 'fingerfucking ', 'fingerfucks ', 'fistfuck', 'fistfucked ', 'fistfucker ', 'fistfuckers ', 'fistfucking ', 'fistfuckings ', 'fistfucks ', 'flange', 'fook', 'fooker', 'fuck', 'fucka', 'fucked', 'fucker', 'fuckers', 'fuckhead', 'fuckheads', 'fuckin', 'fucking', 'fuckings', 'fuckingshitmotherfucker', 'fuckme ', 'fucks', 'fuckwhit', 'fuckwit', 'fudge packer', 'fudgepacker', 'fuk', 'fuker', 'fukker', 'fukkin', 'fuks', 'fukwhit', 'fukwit', 'fux', 'fux0r', 'f_u_c_k', 'gangbang', 'gangbanged ', 'gangbangs ', 'gaylord', 'gaysex', 'goatse', 'God', 'god-dam', 'god-damned', 'goddamn', 'goddamned', 'hardcoresex ', 'hell', 'heshe', 'hoar', 'hoare', 'hoer', 'homo', 'hore', 'horniest', 'horny', 'hotsex', 'jack-off ', 'jackoff', 'jap', 'jerk-off ', 'jism', 'jiz ', 'jizm ', 'jizz', 'kawk', 'knob', 'knobead', 'knobed', 'knobend', 'knobhead', 'knobjocky', 'knobjokey', 'kock', 'kondum', 'kondums', 'kum', 'kummer', 'kumming', 'kums', 'kunilingus', 'l3i+ch', 'l3itch', 'labia', 'lmfao', 'lust', 'lusting', 'm0f0', 'm0fo', 'm45terbate', 'ma5terb8', 'ma5terbate', 'masochist', 'master-bate', 'masterb8', 'masterbat*', 'masterbat3', 'masterbate', 'masterbation', 'masterbations', 'masturbate', 'mo-fo', 'mof0', 'mofo', 'mothafuck', 'mothafucka', 'mothafuckas', 'mothafuckaz', 'mothafucked ', 'mothafucker', 'mothafuckers', 'mothafuckin', 'mothafucking ', 'mothafuckings', 'mothafucks', 'mother fucker', 'motherfuck', 'motherfucked', 'motherfucker', 'motherfuckers', 'motherfuckin', 'motherfucking', 'motherfuckings', 'motherfuckka', 'motherfucks', 'muff', 'mutha', 'muthafecker', 'muthafuckker', 'muther', 'mutherfucker', 'n1gga', 'n1gger', 'nazi', 'nigg3r', 'nigg4h', 'nigga', 'niggah', 'niggas', 'niggaz', 'nigger', 'niggers ', 'nob', 'nob jokey', 'nobhead', 'nobjocky', 'nobjokey', 'numbnuts', 'nutsack', 'orgasim ', 'orgasims ', 'orgasm', 'orgasms ', 'p0rn', 'pawn', 'pecker', 'penis', 'penisfucker', 'phonesex', 'phuck', 'phuk', 'phuked', 'phuking', 'phukked', 'phukking', 'phuks', 'phuq', 'pigfucker', 'pimpis', 'piss', 'pissed', 'pisser', 'pissers', 'pisses ', 'pissflaps', 'pissin ', 'pissing', 'pissoff ', 'poop', 'porn', 'porno', 'pornography', 'pornos', 'prick', 'pricks ', 'pron', 'pube', 'pusse', 'pussi', 'pussies', 'pussy', 'pussys ', 'rectum', 'retard', 'rimjaw', 'rimming', 's hit', 's.o.b.', 'sadist', 'schlong', 'screwing', 'scroat', 'scrote', 'scrotum', 'semen', 'sex', 'sh!+', 'sh!t', 'sh1t', 'shag', 'shagger', 'shaggin', 'shagging', 'shemale', 'shi+', 'shit', 'shitdick', 'shite', 'shited', 'shitey', 'shitfuck', 'shitfull', 'shithead', 'shiting', 'shitings', 'shits', 'shitted', 'shitter', 'shitters ', 'shitting', 'shittings', 'shitty ', 'skank', 'slut', 'sluts', 'smegma', 'smut', 'snatch', 'son-of-a-bitch', 'spac', 'spunk', 's_h_i_t', 't1tt1e5', 't1tties', 'teets', 'teez', 'testical', 'testicle', 'tit', 'titfuck', 'tits', 'titt', 'tittie5', 'tittiefucker', 'titties', 'tittyfuck', 'tittywank', 'titwank', 'tosser', 'turd', 'tw4t', 'twat', 'twathead', 'twatty', 'twunt', 'twunter', 'v14gra', 'v1gra', 'vagina', 'viagra', 'vulva', 'w00se', 'wang', 'wank', 'wanker', 'wanky', 'whoar', 'whore', 'willies', 'willy', 'xrated', 'xxx']
        dirty_text2 = []
        for key in dirty_text:
            dirty_text2.append(key.lower())
        words = str(txt).lower().split(" ")
        all_words = dirty_text2 + dirty_text
        for key in all_words:
            if key in str(txt).lower():
                return True

        if dirty_text in words:
            return True
        if dirty_text2 in words:
            return True
        
        profanity.load_censor_words(all_words)
        res = profanity.contains_profanity(txt)
        return res
    
    async def handle_safe_search(self, message):
        if message.text == Config.SAFE_SEARCH_COMMAND:
            await self.app.send_message(message.chat.id, f"You need to send the command like `{Config.SAFE_SEARCH_COMMAND} on` or `{Config.SAFE_SEARCH_COMMAND} off`")
            return
        on_or_off = str(message.text).split(f"{Config.SAFE_SEARCH_COMMAND} ")[-1]
        if on_or_off.lower() == "off":
            await self.dbh.add_safe(message.chat.id, "0")
            await self.app.send_message(message.chat.id, "Safe search mod turned off")
        elif on_or_off.lower() == "on":
            await self.dbh.add_safe(message.chat.id, "1")
            await self.app.send_message(message.chat.id, "Safe search mod turned on")

        else:
            await self.app.send_message(message.chat.id, f"You need to send the command like `{Config.SAFE_SEARCH_COMMAND} on` or `{Config.SAFE_SEARCH_COMMAND} off`")

    async def handle_always_listen_command(self, message):
        status = self.dbh.get_always_listen(message.chat.id)
        current_status = "Enabled" if status else "Disabled"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Enable {'✅' if status else ''}", callback_data="al_on"),
             InlineKeyboardButton(f"Disable {'✅' if not status else ''}", callback_data="al_off")],
             [InlineKeyboardButton("Cancel", callback_data="al_cancel")]
        ])
        
        await self.app.send_message(
            message.chat.id, 
            f"**Always Listen Mode**\n\nCurrent status: **{current_status}**\n\nWhen enabled, the bot will reply to every message in this group without being tagged.",
            reply_markup=keyboard
        )

    async def handle_always_listen_callback(self, query):
        if query.data == "al_on":
            await self.dbh.set_always_listen(query.message.chat.id, "1")
            await query.edit_message_text("✅ **Always Listen Mode Enabled**\n\nThe bot will now reply to all messages in this group.")
        elif query.data == "al_off":
            await self.dbh.set_always_listen(query.message.chat.id, "0")
            await query.edit_message_text("❌ **Always Listen Mode Disabled**\n\nThe bot will only reply when tagged.")
        elif query.data == "al_cancel":
            await query.message.delete()

    async def handle_start(self, message):
        if message.text == "/start":
            await self.app.send_message(message.chat.id, f"Hello {message.chat.first_name},\n{Config.START_MSG}")
            await self.log.log(message.chat.id, f"User started the bot")
        else:
            user = str(message.text).split("/start ")[-1]
            if self.dbh.user_exists(user) and not self.dbh.user_exists(message.chat.id):
                await self.dbh.add_user(message)
                self.dbh.add_points(user)
                await self.log.log(message.chat.id, f"New user (`{message.chat.id}`) started the bot. `{user}` get 1 point")

            await self.app.send_message(message.chat.id, f"Hello {message.chat.first_name},\n{Config.START_MSG}")


    async def talk_to_admin(self, message):
        if message.text == Config.TALK_TO_ADMIN_COMMAND:
            await self.app.send_message(message.chat.id, "To send your message to admin send message like this:\n \n`/admin [here is your message]`")
        else:
            msg = str(message.text).split(f"{Config.TALK_TO_ADMIN_COMMAND} ")[-1]
            for admin in Config.ADMIN:
                await self.app.send_message(admin, f"**User sends a message!**\n \nUser: `{message.chat.id}`\nMessage: {msg}")
            await self.log.log(message.chat.id, f"User sends a message to Admins.\nMessage: {msg}")
            await self.app.send_message(message.chat.id, f"Your message has been sent to the admins. Thank you!\n \nYour message: {msg}")
    
    async def handle_custom_message(self, message):
        if message.text == Config.CUSTOM_MSG_COMMAND:
            await self.app.send_message(message.chat.id, "With this command you can individualy contact with the users.\n \nex: `/user_123456` message\n \nThis command will automatically send you when user request a movie. You will understand!")
            return
        user = int(str(message.text).split(f" ")[0].split(f"{Config.CUSTOM_MSG_COMMAND}_")[-1])
        msg = str(message.text).split(f"{Config.CUSTOM_MSG_COMMAND}_{user} ")[-1]
        await self.app.send_message(user, msg)
        await self.app.send_message(message.chat.id, f"Message sent to the user (`{user}`)")
        await self.log.log(message.chat.id, f"Admin sent a custom message for user (`{user}`)\nMessage: {msg}")

    def humanbytes(self, size):
        if not size:
            return ""
        power = 2**10
        n = 0
        Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
        while size > power:
            size /= power
            n += 1
        return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'
    async def handle_upload_command(self, message):
        msg = "The file you want to upload must be a direct download link, media files and other files are not supported.\n\nPlease reply to this message with the direct download link."
        await self.app.send_message(
            message.chat.id, 
            msg, 
            reply_markup=ForceReply(selective=True)
        )

    async def handle_upload_response(self, message):
        url = message.text.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            await self.app.send_message(message.chat.id, "Invalid URL. Please provide a valid direct download link starting with http:// or https://.")
            return

        if "youtube.com" in url or "youtu.be" in url:
            asyncio.create_task(self.handle_youtube_download(message, url))
            return

        await self.app.send_message(message.chat.id, "♻️ Initiating remote upload to Mixdrop...")
        
        # Run in executor to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        success, result_msg = await loop.run_in_executor(None, self.remote_upload_to_mixdrop, url)
        
        await self.app.send_message(message.chat.id, result_msg)
        if success:
             await self.log.log(message.chat.id, f"User uploaded a file via link: {url}")

    def remote_upload_to_mixdrop(self, url):
        try:
            api_url = f"https://api.mixdrop.ag/remoteupload?email={Config.MIXDROP_EMAIL}&key={Config.MIXDROP_KEY}&url={urllib.parse.quote(url)}&folder=/"
            res = requests.get(api_url)
            
            # Debug logging
            print(f"Mixdrop Response Status: {res.status_code}")
            print(f"Mixdrop Response Content: {res.text[:500]}") # Print first 500 chars
            
            try:
                json_data = res.json()
            except json.JSONDecodeError:
                return False, f"❌ Error connecting to Mixdrop: Invalid JSON response. Status: {res.status_code}. Content: {res.text[:100]}..."

            if json_data.get('success'):
                result = json_data.get('result', {})
                file_ref = result.get('fileref') 
                return True, f"✅ Upload started successfully!\nYour video will be available to stream in a minute"
            else:
                return False, f"❌ Upload failed: {json_data.get('result', {}).get('msg', 'Unknown error')}"
        except Exception as e:
            return False, f"❌ Error connecting to Mixdrop: {e}"

    async def handle_youtube_download(self, message, url):
        status_msg = await self.app.send_message(message.chat.id, "⬇️ Downloading from YouTube to server...")
        file_path = None
        try:
            # Create downloads dir if not exists
            if not os.path.exists("downloads"):
                os.makedirs("downloads")
            
            # yt-dlp options
            timestamp = int(time.time())
            out_tmpl = f"downloads/{message.from_user.id}_{timestamp}_%(title)s.%(ext)s"
            
            ydl_opts = {
                'outtmpl': out_tmpl,
                'format': 'best',
                'noplaylist': True,
                'quiet': True,
            }
            
            # Download using yt-dlp in executor
            import asyncio
            loop = asyncio.get_event_loop()
            
            def download_yt():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return ydl.prepare_filename(info)
            
            file_path = await loop.run_in_executor(None, download_yt)
            
            await status_msg.edit_text(f"⬆️ Uploading to Mixdrop... 0%")
            
            # Shared Progress Object for Upload
            class UploadProgress:
                def __init__(self):
                    self.current = 0
                    self.total = os.path.getsize(file_path)
                    
            up_progress = UploadProgress()
            
            # Async Monitor for Upload
            async def monitor_upload():
                last_pct = -1
                while True:
                    await asyncio.sleep(4)
                    pct = (up_progress.current / up_progress.total) * 100
                    if pct >= 100: break
                    if int(pct) > last_pct: # Update if changed integer percent
                         try:
                             await status_msg.edit_text(f"⬆️ Uploading: {pct:.1f}% ({self.humanbytes(up_progress.current)})")
                             # print(f"UL: {pct:.1f}%", end='\r')
                             last_pct = int(pct)
                         except: pass
            
            # Start monitor
            monitor_task = asyncio.create_task(monitor_upload())
            
            success, result_msg = await loop.run_in_executor(None, self.upload_file_to_mixdrop, file_path, up_progress)
            
            monitor_task.cancel() # Stop monitor
            
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
            
            await status_msg.edit_text(result_msg)
            
            if success:
                # Extract title for logging if possible, or just use URL
                await self.log.log(message.chat.id, f"User uploaded a YouTube video: {url}")
                
        except Exception as e:
            print(f"YT Download Error: {e}")
            await status_msg.edit_text(f"❌ Error processing YouTube link: {e}")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    async def handle_file_upload(self, message):
        file = message.document or message.video or message.audio
        if not file:
             await self.app.send_message(message.chat.id, "❌ No valid file found in the message.")
             return

        if file.file_size > 2 * 1024 * 1024 * 1024: # 2GB
            await self.app.send_message(message.chat.id, "❌ File is too large. Internal upload limit is 2GB.")
            return

        status_msg = await self.app.send_message(message.chat.id, "⬇️ Downloading file to server...")
        file_path = None
        try:
            # Generate unique filename to avoid conflicts with concurrent uploads
            original_name = getattr(file, 'file_name', 'audio.mp3' if message.audio else 'video.mp4')
            if not original_name: original_name = 'unknown_file'
            
            # Sanitize and unique-ify
            unique_name = f"{message.from_user.id}_{message.id}_{int(time.time())}_{original_name}"
            # Pyrogram's download accepts file_name (path relative to download dir or absolute)
            # We'll use a specific subdir 'downloads' if we want, or just current.
            # unique_name is safer.
            
            # Define Progress Callback for Download
            async def progress(current, total):
                now = time.time()
                # Update every 5 seconds or on completion
                if not hasattr(progress, 'last_update'): progress.last_update = 0
                if now - progress.last_update > 5 or current == total:
                    pct = (current / total) * 100
                    try:
                        await status_msg.edit_text(f"⬇️ Downloading: {pct:.1f}% ({self.humanbytes(current)} / {self.humanbytes(total)})")
                        print(f"DL: {pct:.1f}%", end='\r')
                        progress.last_update = now
                    except: pass

            file_path = await message.download(file_name=unique_name, progress=progress)
            
            await status_msg.edit_text(f"⬆️ Uploading to Mixdrop... 0%")
            
            # Shared Progress Object for Upload
            class UploadProgress:
                def __init__(self):
                    self.current = 0
                    self.total = os.path.getsize(file_path)
                    
            up_progress = UploadProgress()
            
            # Async Monitor for Upload
            async def monitor_upload():
                last_pct = -1
                while True:
                    await asyncio.sleep(4)
                    pct = (up_progress.current / up_progress.total) * 100
                    if pct >= 100: break
                    if int(pct) > last_pct: # Update if changed integer percent
                         try:
                             await status_msg.edit_text(f"⬆️ Uploading: {pct:.1f}% ({self.humanbytes(up_progress.current)})")
                             print(f"UL: {pct:.1f}%", end='\r')
                             last_pct = int(pct)
                         except: pass
            
            # Start monitor
            monitor_task = asyncio.create_task(monitor_upload())
            
            # Run upload in executor
            import asyncio
            loop = asyncio.get_event_loop()
            success, result_msg = await loop.run_in_executor(None, self.upload_file_to_mixdrop, file_path, up_progress)
            
            monitor_task.cancel() # Stop monitor
            
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
                
            await status_msg.edit_text(result_msg)
            if success:
                await self.log.log(message.chat.id, f"User uploaded a file via messaging: {original_name}")

        except Exception as e:
            await status_msg.edit_text(f"❌ Error during processing: {e}")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    def upload_file_to_mixdrop(self, file_path, progress_obj=None):
        try:
            # 1. Get upload server
            ul_server_url = f"https://ul.mixdrop.ag/api?email={Config.MIXDROP_EMAIL}&key={Config.MIXDROP_KEY}"
            res = requests.get(ul_server_url).json()
            if not res.get('success'):
                return False, f"❌ Failed to get upload server: {res.get('result', {}).get('msg')}"
            
            upload_url = res['result']['url']
            
            # Custom File Reader for Progress
            class ProgressReader:
                def __init__(self, filename, progress):
                    self.f = open(filename, 'rb')
                    self.progress = progress
                def read(self, size=-1):
                    chunk = self.f.read(size)
                    if self.progress:
                        self.progress.current += len(chunk)
                    return chunk
                def __getattr__(self, name):
                    return getattr(self.f, name)
            
            # 2. Upload file
            with ProgressReader(file_path, progress_obj) as f:
                files = {'file': f}
                upload_res = requests.post(upload_url, files=files).json()
                
            if upload_res.get('success'):
                 return True, f"✅ File uploaded successfully!\nFile Reference: `{upload_res['result']['fileref']}`"
            else:
                 return False, f"❌ Mixdrop Upload failed: {upload_res.get('result', {}).get('msg')}"

        except Exception as e:
            return False, f"❌ Upload Exception: {e}"

    async def handle_forward_to_channels(self, query):
        try:
            channels = self.dbh.get_adult_channels()
            if not channels:
                await query.answer("No adult channels found!", show_alert=True)
                return

            await query.answer(f"Forwarding to {len(channels)} channels...", show_alert=False)
            
            count = 0
            # Extract links from the original buttons
            watch_url_base = None
            download_url_base = None
            
            try:
                if query.message.reply_markup and query.message.reply_markup.inline_keyboard:
                    for row in query.message.reply_markup.inline_keyboard:
                        for btn in row:
                            if "Watch" in btn.text:
                                watch_url_base = btn.url
                            elif "Download" in btn.text:
                                download_url_base = btn.url
            except Exception as e:
                print(f"Error parsing buttons: {e}")

            if not watch_url_base and not download_url_base:
                 await query.answer("Could not extract links to forward!", show_alert=True)
                 return
            
            # Helper to append query parameter
            def append_src(url, channel_id):
                if not url: return None
                separator = "&" if "?" in url else "?"
                return f"{url}{separator}src={channel_id}"

            report_data = [] # To store details for admin report

            # Iterate through all channels and send personalized message
            for chat_id in channels:
                try:
                    # Sanity check: ensure chat_id is valid
                    if not chat_id: continue
                    
                    # Generate unique links for this channel
                    w_link = append_src(watch_url_base, chat_id)
                    d_link = append_src(download_url_base, chat_id)
                    
                    # Shorten them
                    short_w_link = self.shorten_url(w_link) if w_link else None
                    short_d_link = self.shorten_url(d_link) if d_link else None

                    # Create buttons for this channel
                    buttons = []
                    if short_w_link:
                        buttons.append([InlineKeyboardButton("Watch 🔗", url=short_w_link)])
                    if short_d_link:
                        buttons.append([InlineKeyboardButton("Download 🔗", url=short_d_link)])
                    
                    if not buttons: continue

                    # Use copy_message instead of forward_messages to allow custom reply_markup
                    await self.app.copy_message(
                        chat_id=int(chat_id),
                        from_chat_id=query.message.chat.id,
                        message_id=query.message.id,
                        caption=query.message.caption, # Preserve caption
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                    
                    count += 1
                    report_data.append(f"Channel `{chat_id}`:\nW: {short_w_link}\nD: {short_d_link}")

                except Exception as e:
                    print(f"Failed to forward to {chat_id}: {e}")
            
            # Send report to Admin
            report_msg = f"**Forwarding Complete**\nSuccessfully sent to {count} channels.\n\n"
            
            # Split report if too long (Telegram limit ~4096 chars)
            chunk_size = 4000
            current_chunk = report_msg
            
            admin_id = query.from_user.id
            
            for line in report_data:
                if len(current_chunk) + len(line) + 2 > chunk_size:
                    await self.app.send_message(admin_id, current_chunk)
                    current_chunk = ""
                current_chunk += line + "\n\n"
            
            if current_chunk:
                await self.app.send_message(admin_id, current_chunk)

            await query.message.reply_text(f"Successfully processed {count} channels. Check your DM for details.")

        except Exception as e:
            print(f"Error in forward_to_channels: {e}")
            await query.answer("Error occurred", show_alert=True)

    async def handle_new_channel(self, update):
        try:
            # Check if it's a channel
            if update.chat.type != ChatMemberStatus.ADMINISTRATOR: 
               # Note: update.chat.type gives 'channel', 'supergroup' etc. 
               # But we want to check if the update is about the BOT being added.
               pass

            # Check if the new member is the bot itself
            new_member = update.new_chat_member
            if not new_member:
                return
            
            # Check if the user is the bot
            if new_member.user.id == self.app.me.id:
                 # Check if it is a join event (was not member/admin -> becomes member/admin)
                 # status: MESSENGER (member?), ADMINISTRATOR, OWNER, RESTRICTED, LEFT, BANNED
                 # If we are added, we are usually administrator immediately in channels if added by admin, or just member.
                 
                 print(f"Bot added to chat: {update.chat.title} ({update.chat.id})")
                 
                 keyboard = InlineKeyboardMarkup([
                     [InlineKeyboardButton("Movies 🎬", callback_data="cat_movie")],
                     [InlineKeyboardButton("Series 📺", callback_data="cat_series")],
                     [InlineKeyboardButton("Adult 🔞", callback_data="cat_adult")]
                 ])
                 
                 await self.app.send_message(
                     update.chat.id,
                     f"Hello! Thanks for adding me to **{update.chat.title}**.\n\nPlease select the category for this channel so I can configure updates properly:",
                     reply_markup=keyboard
                 )
                 
                 # Pre-register in DB as pending/channel
                 chat_username = update.chat.username
                 await self.dbh.add_channel(update.chat.id, update.chat.title, chat_username)

        except Exception as e:
            print(f"Error in handle_new_channel: {e}")

    async def handle_channel_category(self, query):
        try:
            category_map = {
                "cat_movie": "movie",
                "cat_series": "series",
                "cat_adult": "adult"
            }
            
            category_key = query.data
            category = category_map.get(category_key)
            
            if category:
                await self.dbh.update_category(query.message.chat.id, category)
                await query.edit_message_text(f"✅ Registration Complete!\n\nChannel Category: **{category.capitalize()}**")
                await self.log.log(query.message.chat.id, f"Channel registered as {category}")
            else:
                await query.answer("Invalid category", show_alert=True)
                
        except Exception as e:
            print(f"Error in handle_channel_category: {e}")
            await query.answer("Error processing request", show_alert=True)


