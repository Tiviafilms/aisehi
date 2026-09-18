class Config(object):
    # DB data - it is okey you don't need to edit this BOT_NAME and BOT_DB_PATH
    BOT_NAME = "movie-bot"
    BOT_DB_PATH = f"bot/{BOT_NAME}/"

    # TG
    BOT_LINK = "https://t.me/tiviaFilms_bot"
    BOT_USERNAME = f"@{BOT_LINK.split('/')[-1]}"
    
    # Provide any number of admin list
    # -1002064599522
    ADMIN = [1915029649, -1002064599522, 1132088975, 6792359362]
    
    # Logging channel id
    LOGGER_CHANNEL_ID = -1002100859582
    
    # Group id that bot is going to add
    GROUP_ID = -844681865
    
    # Channe; that user must subscribe to search
    SUBSCRIBE_CHANNEL = -1002048712676
    SUBSCRIBE_CHANNEL_URL = "https://t.me/TiviaFilmsSupport"
    
    # Contact username
    CONTACT = "@owneroftivia"

    # MIXDROP
    MIXDROP_EMAIL = "tiviafilms@gmail.com"
    MIXDROP_KEY = "msansq3TZ2m3Cze4N9Y3"
    MIXDROP_CACHE_FILE = "mixdrop_cache.json"
    MAX_LOAD_COUNT = 3

    # LINKVERTISE
    LINKVERTISE_ID = 7825987


    # COMMANDS
    BROADCAST_COMMAND = "/broadcast"
    BLOCK_USER_COMMAND = "/block"
    UNBLOCK_USER_COMMAND = "/unblock"
    GET_USER_DETAILS_COMMAND = "/user"
    RUN_TIME = "/run_time"
    GET_ID_COMMAND = "/id"
    SAFE_SEARCH_COMMAND = "/safe_search"
    ALWAYS_LISTEN_COMMAND = "/always_listen"
    TALK_TO_ADMIN_COMMAND = "/admin"
    CUSTOM_MSG_COMMAND = "/user"
    BROADCAST_SYMBOL = "###"

    
    # MESSAGES
    START_MSG = f"🎬 Welcome! Please directly send the file you want to process.\n \nSend /help to see the instructions"
    HELP_MESSAGE = f"**All the user commands**\n \n/start - __Starts the bot.__\n/help - __Send help commands__\n{GET_ID_COMMAND} - __Get your information__\n{TALK_TO_ADMIN_COMMAND} - __Contact admin directly__\n{SAFE_SEARCH_COMMAND} - __Your safe search mod__\n \nFor help contact {CONTACT}"
    ADMIN_HELP_MESSAGE = f"**All the admin commands**\n \n/start - __Starts the bot.__\n/help - __Send help commands__\n{GET_ID_COMMAND} - __Get your information__\n{BLOCK_USER_COMMAND} - __Block user__\n{UNBLOCK_USER_COMMAND} - __Unblock user__\n{RUN_TIME} - Check bot's running time\n{SAFE_SEARCH_COMMAND} - __Your safe search mod__\n{CUSTOM_MSG_COMMAND} - __Contact any user__\n{BROADCAST_COMMAND} - __Reply any message to broadcast__\n`{BROADCAST_SYMBOL}` - __Send any message with `{BROADCAST_SYMBOL}` and it will broadcasted to all the users__"

    # DO NOT TOUCH THIS!
    starting_point = []
