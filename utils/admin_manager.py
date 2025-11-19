import discord

from utils.json_manager import load_json_async

async def check_admin_status(bot, interaction: discord.Interaction):
    # check user to see if theyre allowed 
    override_users = []
    guild_id_str = str(interaction.guild_id)
    if(hasattr(bot, "booster_data") and guild_id_str in getattr(bot, "booster_data", {})):
        override_users = bot.booster_data[guild_id_str].get("staff", [])
    if(interaction.user.id in override_users):
        return True
    else:
        return False

async def get_flavor_roles(interaction: discord.Interaction):
    data = await load_json_async("data/server_data.json")
    guild_id = str(interaction.guild_id)
    return data.get(guild_id, {}).get("flavor_roles", {})

    
