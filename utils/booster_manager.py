import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

from utils.json_manager import load_json_async, write_json_async

load_dotenv()

FILE_PATH = "data/server_data.json"
USER_FILE_PATH = "data/user_data.json"



async def update_single_user(bot, member: discord.Member):
    guild_id = str(member.guild.id)
    # ensure role IDs are loaded safely with defaults
    boost_role_id_str = os.getenv("BOOST_ROLE_ID")
    if not boost_role_id_str:
        print("BOOST_ROLE_ID is not set.")
        return
        
    booster_role = member.guild.get_role(int(boost_role_id_str))
    
    # Use the previous working list comprehension pattern
    staff_role_ids = [int(r) for r in os.getenv("ACCEPTABLE_CONFIG_ROLES", "").split(",") if r.strip().isdigit()]
    staff_roles = [member.guild.get_role(r) for r in staff_role_ids]
    
    if any(role is None for role in staff_roles):
        print(f"Warning: One or more staff role IDs in ACCEPTABLE_CONFIG_ROLES do not exist in guild '{member.guild.name}' (ID: {member.guild.id}).")

    # read the data safely
    data = await load_json_async(FILE_PATH)
    
    if guild_id not in data:
        data[guild_id] = {"boosters": [], "staff": []}

    # boosters logic
    boosters = data[guild_id]["boosters"]
    if booster_role in member.roles and member.id not in boosters:
        boosters.append(member.id)
    elif booster_role not in member.roles and member.id in boosters:
        boosters.remove(member.id)

    # staff logic
    staff = data[guild_id]["staff"]
    is_staff = any(role in member.roles for role in staff_roles if role)
    was_staff = member.id in staff
    if is_staff and not was_staff:
        staff.append(member.id)
    elif not is_staff and was_staff:
        staff.remove(member.id)

    # write the modified data safely
    await write_json_async(data, FILE_PATH)
    
    # update the bot instance's internal data store
    bot.booster_data = data
    if hasattr(bot, "set_booster_data") and callable(getattr(bot, "set_booster_data")):
        bot.set_booster_data(data)
        

async def load_users(bot: commands.Bot):
    # ensure data directory exists
    os.makedirs("data", exist_ok=True)

    # create files if they don't exist
    if not os.path.exists(FILE_PATH):
        await write_json_async({}, FILE_PATH)
        print("Created server_data.json file.")
    
    if not os.path.exists(USER_FILE_PATH):
        await write_json_async({}, USER_FILE_PATH)
        print("Created user_data.json file.")
    
    try:
        # read the data safely
        data = await load_json_async(FILE_PATH)

        guilds = bot.guilds
        for guild in guilds:
            # lad environment variables safely within the loop if needed
            override_roles = [int(role_id) for role_id in os.getenv("ACCEPTABLE_CONFIG_ROLES", "").strip().split(",") if role_id]
            boost_role_id_str = os.getenv("BOOST_ROLE_ID")

            if not boost_role_id_str:
                raise ValueError("BOOST_ROLE_ID environment variable is not set.")
            
            boost_role = discord.utils.get(guild.roles, id=int(boost_role_id_str))
            if not boost_role:
                print(f"Warning: BOOST_ROLE_ID {boost_role_id_str} not found in guild {guild.name}.")
                continue # skip this guild if config is bad

            if str(guild.id) not in data:
                data[str(guild.id)] = {"boosters": [], "staff": []}
            
            # use fetch_members for accuracy, clear lists before repopulating
            if str(guild.id) not in data:
                data[str(guild.id)] = {"boosters": [], "staff": []}

            guild_data = data[str(guild.id)]
            guild_data.setdefault("boosters", [])
            guild_data.setdefault("staff", [])

            async for user in guild.fetch_members(limit=None):
                # check staff roles
                for role_id in override_roles:
                    role = discord.utils.get(guild.roles, id=role_id)
                    if role in user.roles:
                        if user.id not in data[str(guild.id)]["staff"]:
                            data[str(guild.id)]["staff"].append(user.id)
                # Check boost role
                if boost_role in user.roles:
                    if user.id not in data[str(guild.id)]["boosters"]:
                        data[str(guild.id)]["boosters"].append(user.id)
            
            print(f"Synced guild {guild.name} with boosters and staff.")

        # write the entire updated dictionary back to the file safely
        await write_json_async(data, FILE_PATH)
        bot.booster_data = data
            
    except ValueError as e:
        print(f"Value error in load_users: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error in load_users: {e}")
        raise

    
async def check_boost_status(bot, interaction: discord.Interaction):
    boosters = []
    override_users = []
    guild_id_str = str(interaction.guild_id)
    if(hasattr(bot, "booster_data") and guild_id_str in getattr(bot, "booster_data", {})):
        boosters = bot.booster_data[guild_id_str].get("boosters", [])
        override_users = bot.booster_data[guild_id_str].get("staff", [])
    if(interaction.user.id in boosters or interaction.user.id in override_users):
        return True
    else:
        return False
