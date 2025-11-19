import json
import discord
import os, asyncio
from discord.ext import commands

SERVER_FILE = "data/server_data.json"
USER_FILE = "data/user_data.json"
FILE_LOCK = asyncio.Lock()

#  sync JSON helpers 
def read_json(path=SERVER_FILE):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def write_json(data, path=SERVER_FILE):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(temp_path, path)  # atomic replacement


#  Ensure user_data file exists 
def check_user_data():
    if not os.path.exists(USER_FILE):
        write_json({}, USER_FILE)
        print("Created user_data.json file.")


#  Load votes 
def load_votes(guild_id: int):
    data = read_json(SERVER_FILE)
    return data.get(str(guild_id), {}).get("vote_items", {})


def load_user_data_votes(guild_id: int, user_id: int):
    data = read_json(USER_FILE)
    return data.get(str(guild_id), {}).get(str(user_id), {}).get("votes", {})


#  Reset votes 
def reset_votes(guild_id: int):
    # clear server vote data
    data = read_json(SERVER_FILE)
    if str(guild_id) in data:
        data[str(guild_id)]["vote_items"] = {}
    write_json(data, SERVER_FILE)

    # clear user_data votes
    u_data = read_json(USER_FILE)
    guild_users = u_data.get(str(guild_id), {})
    for user_id in guild_users:
        guild_users[user_id]["votes"] = {}
    u_data[str(guild_id)] = guild_users
    write_json(u_data, USER_FILE)


#  Aggregate votes from user_data 
def get_votes_from_user_data(guild_id: int):
    data = read_json(USER_FILE)
    s_data = data.get(str(guild_id), {})
    vote_data = {}

    for user_id, user_info in s_data.items():
        for item_name, votes in user_info.get("votes", {}).items():
            if item_name not in vote_data:
                vote_data[item_name] = []
            for vote in votes:
                vote_data[item_name].append({
                    "score": vote["score"],
                    "time_created": vote["time_created"],
                    "voter": user_id
                })
    return vote_data

#  Tierlist generation 
def generate_tierlist_text(data: dict, guild_id: int):
    guild_id_str = str(guild_id)
    if guild_id_str not in data or "vote_items" not in data[guild_id_str]:
        return "**No vote items yet!**"

    flavors = data[guild_id_str]["vote_items"]
    tiers = {"S": [], "A": [], "B": [], "C": [], "D": [], "F": []}

    for name, info in flavors.items():
        score = info.get("score")
        if score is None:  # skip items with no score
            continue
        entry = (name, score)
        if score >= 9: tiers["S"].append(entry)
        elif score >= 7.5: tiers["A"].append(entry)
        elif score >= 6: tiers["B"].append(entry)
        elif score >= 4.5: tiers["C"].append(entry)
        elif score >= 2.5: tiers["D"].append(entry)
        else: tiers["F"].append(entry)

    icons = ["🟣", "🔵", "🟢", "🟡", "🟠", "🔴"]
    output = "**DDD Flavor Tier List**\n"
    for idx, (tier, entries) in enumerate(tiers.items()):
        entries.sort(key=lambda item: item[1], reverse=True)
        icon = icons[idx]
        output += f"\n**━═━═━═━┤{icon} {tier} Tier├━═━═━═━**\n"
        output += ", ".join(name for name, _ in entries) if entries else "_(empty)_"
    return output

def generate_user_tierlist_text(vote_data: dict, interaction: discord.Interaction):
    if not vote_data:
        return "**No votes recorded yet!**"

    user_votes = vote_data.get(str(interaction.user.id))
    if not user_votes or "personal_votes" not in user_votes:
        return "**No votes recorded yet!**"

    tiers = {"S": [], "A": [], "B": [], "C": [], "D": [], "F": []}

    for flavor, votes_list in user_votes["personal_votes"].items():
        if not votes_list:
            continue

        # calculate average score for this flavor
        avg_score = sum(vote["score"] for vote in votes_list) / len(votes_list)
        entry = (flavor, avg_score)

        # assign to tier
        if avg_score >= 9:
            tiers["S"].append(entry)
        elif avg_score >= 7.5:
            tiers["A"].append(entry)
        elif avg_score >= 6:
            tiers["B"].append(entry)
        elif avg_score >= 4.5:
            tiers["C"].append(entry)
        elif avg_score >= 2.5:
            tiers["D"].append(entry)
        else:
            tiers["F"].append(entry)

    icons = ["🟣", "🔵", "🟢", "🟡", "🟠", "🔴"]
    output = f"**{interaction.user.name}'s Flavor Tier List**\n"

    for idx, (tier, entries) in enumerate(tiers.items()):
        entries.sort(key=lambda item: item[1], reverse=True)
        icon = icons[idx]
        output += f"\n**━═━═━═━┤{icon} {tier} Tier├━═━═━═━**\n"
        if entries:
            output += ", ".join(f"{name}" for name, score in entries)
        else:
            output += "_(empty)_"

    return output



#  Tierlist message reference 
def save_tierlist_reference(guild_id: int, msg_id: int):
    data = read_json(SERVER_FILE)
    data.setdefault(str(guild_id), {}).setdefault("tierlist_channel", {})
    data[str(guild_id)]["tierlist_channel"]["message_id"] = msg_id
    write_json(data, SERVER_FILE)
    print("Tierlist message ID saved to server_data.json")


def get_tierlist_reference(guild_id: int):
    data = read_json(SERVER_FILE)
    return data.get(str(guild_id), {}).get("tierlist_channel")


#  Update tierlist message in Discord 
async def update_tierlist_message(bot: commands.Bot, guild_id: int):
    ref = get_tierlist_reference(guild_id)
    if not ref:
        print("Tierlist message not found.")
        return

    channel = bot.get_channel(ref.get("channel_id"))
    if not channel:
        print("Channel not found or bot can't access it.")
        return

    try:
        message = await channel.fetch_message(ref.get("message_id"))
    except discord.NotFound:
        print("Tierlist message no longer exists.")
        return

    data = read_json(SERVER_FILE)
    new_content = generate_tierlist_text(data, guild_id)
    # if content exceeds 2000 chars, send as file
    if len(new_content) > 2000:
        from io import StringIO
        file = StringIO(new_content)
        await channel.send(file=discord.File(file, filename="tierlist.txt"))
    else:
        await message.edit(content=new_content)
