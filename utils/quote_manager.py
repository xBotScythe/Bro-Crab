import discord

from utils.json_manager import load_json_async, write_json_async

# saves a quote to quote list given Discord user ID, and Discord message object.
async def save_quote(user_id: str, message: discord.Message):
    message_exists = False
    cur_data = await load_json_async("data/user_data.json")
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
        await write_json_async(cur_data, "data/user_data.json")
    print("user_data quotes modified.")
           
async def load_quotes():
    return await load_json_async("data/user_data.json")
