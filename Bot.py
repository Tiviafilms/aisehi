import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from Config import Config
from Cred import Cred
from pyrogram import Client, filters, enums
from Process import Process
import asyncio
from Logger import Logger
import re
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

app = Client(
    Config.BOT_NAME,
    api_id=Cred.API_ID,
    api_hash=Cred.API_HASH,
    bot_token=Cred.BOT_TOKEN
)
process = Process(app)
log = Logger(app)

# Callback functions
@app.on_callback_query()
async def handle_callback(app, query):
    if "req_add" in query.data:
        await process.handle_movie_req(query)

    elif "forward_to_channels" == query.data:
        await process.handle_forward_to_channels(query)

    elif "cat_" in query.data:
        await process.handle_channel_category(query)

    elif "al_" in query.data:

        await process.handle_always_listen_callback(query)

    # default message query
    elif "dm_" in query.data:
        try:
            # Extract movie name using Regex for robustness
            # Matches "Request: <movie_name>" anywhere in the text
            match = re.search(r"Request:\s*(.*)", query.message.text)
            if match:
                movie_name = match.group(1).strip()
                msg = f"The movie you searched for **{movie_name}**, is uploaded to the bot. You can retry now."
            else:
                raise ValueError("Could not find 'Request:' pattern in message")
                
        except Exception as e:
            # Fallback if parsing fails
            print(f"Error parsing movie name: {e}")
            msg = "The movie has been successfully added to the database. You can now retry."
            
        user = int(str(query.data).split("dm_")[-1])
        await app.send_message(user, msg)
        await query.edit_message_text("Default message has been sent to the user")
        await log.log(user, "Default message has been sent to the user")


        
    # custom message query
    elif "cm_" in query.data:
        user = int(str(query.data).split("cm_")[-1])
        await query.edit_message_text(f"`{Config.CUSTOM_MSG_COMMAND}_{user}` Click to copy the command and write your message for this user.\n \nex: `{Config.CUSTOM_MSG_COMMAND}_{user} this is an example`")

    
    elif "load_" in query.data:
        print(query.data)
        load_count = int(str(query.data).split("load_")[-1])
        data = process.dbh.get_last_searched(query.message.chat.id)
        if data and data != "N/A":
            if Config.BOT_USERNAME in data:
                data = data.replace(f"{Config.BOT_USERNAME}", "").strip()
            await process.search_movie(query, data, load_count)
    
    elif "multi_" in query.data:
        print(query.data)
        load = str(query.data).split("multi_")[-1].split("-")
        load_count = int(load[0])
        word_index = int(load[1])

        data = process.dbh.get_last_searched(query.message.chat.id)
        if data and data != "N/A":
            if Config.BOT_USERNAME in data:
                data = data.replace(f"{Config.BOT_USERNAME}", "").strip()
            await process.multi_search_movie(query, data, load_count, word_index)



@app.on_message(filters.command(["start"]))
async def start_command(app, message):
    await process.handle_start(message)

@app.on_message(filters.channel)
async def admin_cmds_aprooval(app, message):
    if message.chat.id in Config.ADMIN and str(message.chat.id)[0] == "-":
        if f"{Config.CUSTOM_MSG_COMMAND}" in message.text:
            await process.handle_custom_message(message)


@app.on_message(filters.group)
async def group_command(app, message):
    if Config.ALWAYS_LISTEN_COMMAND in message.text:
        await process.handle_always_listen_command(message)
        return

    # Check if mentioned OR always listen is on
    should_process = bool(message.mentioned)
    if not should_process:
        should_process = process.dbh.get_always_listen(message.chat.id)

    if should_process and await process.dbh.check_user(message):
        user_id = message.from_user.id
        text = str(message.text).replace(f"{Config.BOT_USERNAME}", "").strip()
        await log.log(user_id, f"User searched inside the group.\nSearched: {text}")

        if "&" in message.text:
            await process.multi_search_movie(message, message.text, 0, 0)
        else:
            await process.search_movie(message, text, 0)
    
    if message.chat.id in Config.ADMIN and str(message.chat.id)[0] == "-":
        if f"{Config.CUSTOM_MSG_COMMAND}" in message.text:
            await process.handle_custom_message(message)

        

@app.on_message(filters.command(["help"]))
async def start_command(app, message):
    if int(message.chat.id) in Config.ADMIN:
        await app.send_message(
            message.chat.id, Config.ADMIN_HELP_MESSAGE)
        
    await app.send_message(
        message.chat.id, Config.HELP_MESSAGE)



@app.on_chat_member_updated()
async def handle_chat_member_update(app, update):
    await process.handle_new_channel(update)


@app.on_message((filters.text | filters.document | filters.video | filters.audio) & filters.private)

async def cmd_parser(app, message):
    try:
        # 1. Media Upload (Implicit) - Beta
        # Handle files sent directly (forwarded or new) in background
        if message.document or message.video or message.audio:
            asyncio.create_task(process.handle_file_upload(message))
            return

        # 2. Upload Link Response
        # Check for upload response
        if message.reply_to_message and "Please reply to this message with the direct download link" in message.reply_to_message.text:
             await process.handle_upload_response(message)
             return

        # Admin commands

        if (int(message.chat.id) in Config.ADMIN) and await process.dbh.check_user(message):
            # /broadcast
            if message.reply_to_message and message.text == Config.BROADCAST_COMMAND:
                await process.send_promo_message(message)
            
            elif message.text in Config.BROADCAST_COMMAND:
                await app.send_message(message.chat.id, f"Reply to any message with `{Config.BROADCAST_COMMAND}` and it will broadcast for all users.\n \n**If you need to broadcast a simple message, then just add `###` symbols (3 hashes) to any text message**")
            
            elif Config.BROADCAST_SYMBOL in message.text:
                await process.send_broadcast(message)

            # /block_user [user_id]
            elif Config.BLOCK_USER_COMMAND in message.text:
                await process.handle_block(message)

            # /unblock_user [user_id]
            elif Config.UNBLOCK_USER_COMMAND in message.text:
                await process.handle_unblock(message)

            # /run_time
            elif Config.RUN_TIME in message.text:
                await process.check_runtime(message)

            # /id
            elif Config.GET_ID_COMMAND in message.text:
                await process.get_id(message)

            # /safe_search
            elif Config.SAFE_SEARCH_COMMAND in message.text:
                await process.handle_safe_search(message)
            
            # /user_123456
            elif f"{Config.CUSTOM_MSG_COMMAND}" in message.text:
                await process.handle_custom_message(message)

            elif Config.TALK_TO_ADMIN_COMMAND in message.text:
                await app.send_message(message.chat.id, "Only working for users, Not for admins.")
            
            elif message.text == "/upload":
                await process.handle_upload_command(message)

            else:

                if "&" in message.text:
                    await process.multi_search_movie(message, message.text, 0, 0)
                else:
                    await process.search_movie(message, message.text, 0)
        


        # User commands
        else:
            if await process.dbh.check_user(message):
                if await process.is_user_in_channel(message):

                    # /id
                    if Config.GET_ID_COMMAND in message.text:
                        await process.get_id(message)
                        
                    # /safe_search
                    elif Config.SAFE_SEARCH_COMMAND in message.text:
                        await process.handle_safe_search(message)

                    elif Config.TALK_TO_ADMIN_COMMAND in message.text:
                        await process.talk_to_admin(message)

                    elif message.text == "/upload":
                        await process.handle_upload_command(message)

                    else:

                        if "&" in message.text:
                            await process.multi_search_movie(message, message.text, 0, 0)
                        else:
                            await process.search_movie(message, message.text, 0)
            
            else:
                await app.send_message(message.chat.id, "Sorry you are blocked!")


    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        await app.send_message(message.chat.id, "Some error occurred 😕")
        await app.send_message(message.chat.id, f"ERROR: {e}")
        await log.log(message.chat.id, f"ERROR: {e}")
    else:
        print("No exceptions were raised.")























process.start()
print("Bot started")
app.run()
