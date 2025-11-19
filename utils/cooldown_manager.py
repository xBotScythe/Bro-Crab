import discord
from datetime import datetime, timedelta, timezone

from utils.json_manager import load_json_async, write_json_async

DATA_PATH = "data/server_data.json"

async def check_cooldown(interaction: discord.Interaction, seconds: int):
    # checks if user is on cooldown for a command in this guild
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    command = interaction.command.name
    now = datetime.now(timezone.utc)

    data = await load_json_async(DATA_PATH)
    guild_data = data.get(guild_id, {})
    cooldowns = guild_data.get("cooldowns", {})
    user_data = cooldowns.get(user_id, {})
    timestamp = user_data.get(command)

    if not timestamp:
        return False  # no cooldown found, user can use command
        
    last_used = datetime.fromisoformat(timestamp)
    return (now - last_used).total_seconds() < seconds  # returns True if still on cooldown

async def set_cooldown(interaction):
    # sets cooldown for user for this command in this guild
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    command = interaction.command.name
    now = datetime.now(timezone.utc).isoformat()

    data = await load_json_async(DATA_PATH)
    data[guild_id] = data.get(guild_id, {})
    data[guild_id]["cooldowns"] = data[guild_id].get("cooldowns", {})
    if not isinstance(data[guild_id]["cooldowns"], dict):
        data[guild_id]["cooldowns"] = {}
    data[guild_id]["cooldowns"][user_id] = data[guild_id]["cooldowns"].get(user_id, {})

    data[guild_id]["cooldowns"][user_id][command] = now  # save current time as last used
    await write_json_async(data, DATA_PATH)

async def get_remaining_cooldown(interaction, seconds):
    # returns string of time left on cooldown, or None if not on cooldown
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    command = interaction.command.name
    now = datetime.now(timezone.utc)

    data = await load_json_async(DATA_PATH)
    guild_data = data.get(guild_id, {})
    cooldowns = guild_data.get("cooldowns", {})
    user_data = cooldowns.get(user_id, {})
    timestamp = user_data.get(command)

    if not timestamp:
        return None  # no cooldown found

    last_used = datetime.fromisoformat(timestamp)
    expires_at = last_used + timedelta(seconds=seconds)
    remaining = expires_at - now
    if remaining.total_seconds() <= 0:
        return None  # cooldown expired

    mins, secs = divmod(int(remaining.total_seconds()), 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {secs}s"
    elif mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"
