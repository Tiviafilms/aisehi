
# Simulation of the bug

def test_parsing():
    # From Process.py line 353
    # msg = f"User ID: {query.message.chat.id}\nUser first name: {query.message.chat.first_name}\nUsername: {username}\nDate: {query.message.date}\n \nRequest: {searched}"
    
    # Mock data
    user_id = 123456789
    first_name = "TestUser"
    username = "@TestUser"
    date = "2024-01-01 12:00:00"
    searched = "Iron Man"
    
    msg = f"User ID: {user_id}\nUser first name: {first_name}\nUsername: {username}\nDate: {date}\n \nRequest: {searched}"
    
    print(f"Generated Message:\n---\n{msg}\n---\n")
    
    # Logic from Bot.py lines 31-32
    try:
        request_line = [line for line in msg.split('\n') if "Request: " in line][0]
        print(f"Found request line: '{request_line}'")
        movie_name = request_line.split("Request: ")[1].strip()
        print(f"Extracted movie name: '{movie_name}'")
        
        dm_msg = f"The movie you searched for **{movie_name}**, is uploaded to the bot. You can retry now."
        print(f"Response message: {dm_msg}")
        
    except Exception as e:
        print(f"Caught exception: {e}")

if __name__ == "__main__":
    test_parsing()
