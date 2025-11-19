import discord
import json, os

# saves a quote to quote list given Discord user ID, and Discord message object.
async def save_quote(user_id: str, message: discord.Message):
    if(not os.path.exists("data/user_data.json")):
        with open("data/user_data.json", "w") as temp_f:
            json.dump({}, temp_f, indent=4)
            print("Created user_data.json file.")

    with open("data/user_data.json", "r+") as f:
        message_exists = False
        cur_data = json.load(f)
        guild_id_str = str(message.guild.id)
        if guild_id_str not in cur_data:
            cur_data[guild_id_str] = {}
        if user_id not in cur_data[guild_id_str]:
            cur_data[guild_id_str][user_id] = {}
        if "recalls" not in cur_data[guild_id_str][user_id]:
            cur_data[guild_id_str][user_id]["recalls"] = []
        for recall in cur_data[guild_id_str][user_id]["recalls"]:
            if(recall["message_id"] == message.id):
                message_exists = True
                break
        if(message_exists == False):
            # append the message content as a quote
            cur_data[guild_id_str][user_id]["recalls"].append({
                "user_id": user_id,
                "msg_author_id": str(message.author.id),
                "content": message.content,
                "message_id": str(message.id),
                "timestamp": message.created_at.isoformat()
            })
            f.seek(0)
            json.dump(cur_data, f, indent=4)
            f.truncate()
    print("user_data quotes modified.")
           
async def load_quotes():
    try:
        with open("data/user_data.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("File not found!")
        return {}