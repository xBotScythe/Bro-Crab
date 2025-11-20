import utils.admin_manager as admin_m
import utils.automation_manager as auto_m
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os, json, asyncio, random
from utils.vote_manager import FILE_LOCK, generate_user_tierlist_text, SERVER_FILE, generate_tierlist_text, read_json, save_tierlist_reference, reset_votes, write_json, update_tierlist_message, load_votes

class Config(commands.Cog):
    """
    Cog for adjusting configurations
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def flavor_autocomplete(self, interaction: discord.Interaction, current: str):
        flavors = load_votes(interaction.guild_id)
        return [
            app_commands.Choice(name=flavor, value=flavor)
            for flavor in list(flavors.keys()) if current.lower() in flavor.lower()
        ][:25]  # Discord max 25 choices
    
    @app_commands.command(name="addroast", description="Add a roast to the list!")
    async def addroast(self, interaction: discord.Interaction, roast: str):
        if(await admin_m.check_admin_status(self.bot, interaction)):
            with open("data/roasts.json", "r+") as f:
                data = json.load(f)
                data["roasts"].append(roast)
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
            await interaction.response.send_message("Roast added!", ephemeral=True)
        else:
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
    
    @app_commands.command(name="addautoreact", description="Add an auto reaction from the bot to a certain phrase!")
    async def addautoroast(self, interaction: discord.Interaction, phrase: str, emoji: str):
        if(await admin_m.check_admin_status(self.bot, interaction)):
            response = "Auto reaction created!"
            with open("data/server_data.json", "r+") as f:
                data = json.load(f)
                # checks if auto_reacts exists, if not creates it 
                if "auto_reacts" not in data[str(interaction.guild_id)] or data[str(interaction.guild_id)]["auto_reacts"] is None:
                    data[str(interaction.guild_id)]["auto_reacts"] = []
                    response = "Auto Reacts data created and auto reaction created!"
                data[str(interaction.guild_id)]["auto_reacts"].append(  # appends dictionary of auto react details to auto_reacts list
                    {
                        "content": phrase,
                        "emoji": str(emoji),
                        "added_by": interaction.user.id
                    }
                )
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
                print("server_data auto reacts modified.")
                await interaction.response.send_message(response, ephemeral=True)
        else:
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)

    @app_commands.command(name="settieristchannel", description="Sets tierlist channel")
    async def settierlistchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if(not await admin_m.check_admin_status(self.bot, interaction)):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        
        with open("data/server_data.json", "r+") as f:
            data = json.load(f)
            if "tierlist_channel" not in data[str(interaction.guild_id)]:
                data[str(interaction.guild_id)]["tierlist_channel"] = {}
            data[str(interaction.guild_id)]["tierlist_channel"]["channel_id"] = channel.id
            data[str(interaction.guild_id)]["tierlist_channel"]["message_id"] = None

            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
            print(f"Tierlist channel changed to {channel.name}")
            await interaction.response.send_message(f"Tierlist channel changed to {channel.name}")



    @app_commands.command(name="additemtovote", description="adds an item to a vote")
    async def additemtovote(self, interaction: discord.Interaction, item_name : str):
        if(not await admin_m.check_admin_status(self.bot, interaction)):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return

        with open("data/server_data.json", "r+") as f:
            data = json.load(f)
            # checks if vote_items exists, if not, creates it
            guild_id = str(interaction.guild_id)
            if "vote_items" not in data[guild_id] or data[guild_id]["vote_items"] is None:
                data[guild_id]["vote_items"] = {}
            # adds item to dictionary with 0 votes
            data[guild_id]["vote_items"][item_name] = {
                "vote_num": 0,
                "total_score": 0,
                "score": None
            }
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
            print(f"server_data vote items modified: Added {item_name}")
        await interaction.response.send_message(f"{item_name} added to the vote list!")

    @app_commands.command(name="additemsfromlist", description="adds multiple items to vote from a comma-separated list")
    async def additemsfromlist(self, interaction: discord.Interaction, item_list : str):
        if(not await admin_m.check_admin_status(self.bot, interaction)):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        items = [item.strip() for item in item_list.split(",")]
        with open("data/server_data.json", "r+") as f:
            data = json.load(f)
            guild_id = str(interaction.guild_id)
            if "vote_items" not in data[guild_id] or data[guild_id]["vote_items"] is None:
                data[guild_id]["vote_items"] = {}
            for item_name in items:
                data[guild_id]["vote_items"][item_name] = {
                    "vote_num": 0,
                    "total_score": 0,
                    "score": None
                }
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
            print(f"server_data vote items modified: Added items from list")
        await interaction.response.send_message(f"Items added to the vote list!", ephemeral=True)
    
    @app_commands.command(name="buildusertierlist", description="Builds the user tier list message in the current channel")
    async def buildusertierlist(self, interaction: discord.Interaction):
        data = read_json("data/user_data.json")
        guild_id = str(interaction.guild_id)
        if guild_id not in data:
            await interaction.response.send_message("No user data found for this server.", ephemeral=True)
            return
        content = generate_user_tierlist_text(data[guild_id], interaction)
        await interaction.response.send_message(content)

    @app_commands.command(name="ratedew", description="Rate a dew flavor 1-10!")
    async def ratedew(self, interaction: discord.Interaction, flavor: str, score: app_commands.Range[int, 1, 10]):
        # saves vote data to server's user data
        with open("data/user_data.json", "r+") as f:
            data = json.load(f)
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            # save to user data
            if guild_id not in data:
                data[guild_id] = {}
            if user_id not in data[guild_id]:
                data[guild_id][user_id] = {}
            if "personal_votes" not in data[guild_id][user_id]:
                data[guild_id][user_id]["personal_votes"] = {}
            if flavor not in data[guild_id][user_id]["personal_votes"]:
                data[guild_id][user_id]["personal_votes"][flavor] = []
            # appends score and time to vote list
            data[guild_id][user_id]["personal_votes"][flavor].append({
                "score": score,
                "time_created": interaction.created_at.isoformat()
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        await update_tierlist_message(self.bot, interaction.guild_id)
        await interaction.response.send_message(f"You voted **{score}/10** for **{flavor}**!", ephemeral=True)

    @ratedew.autocomplete("flavor")
    async def ratedew_autocomplete(self, interaction: discord.Interaction, current: str):
        print(f"Autocomplete triggered: {current}")
        return await self.flavor_autocomplete(interaction, current)
    

    @app_commands.command(name="buildtierlist", description="Initialize or rebuild the flavor tier list.")
    async def buildtierlist(self, interaction: discord.Interaction):
        if(not await admin_m.check_admin_status(self.bot, interaction)):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        try:
            guild_id = interaction.guild_id
            async with FILE_LOCK:
                data = await asyncio.to_thread(read_json)

            #  delete old tierlist message if exists 
            old_channel_id = data.get(str(guild_id), {}).get("tierlist_channel", {}).get("channel_id")
            old_msg_id = data.get(str(guild_id), {}).get("tierlist_channel", {}).get("message_id")

            if old_channel_id and old_msg_id:
                old_channel = self.bot.get_channel(old_channel_id)
                if old_channel:
                    try:
                        old_msg = await old_channel.fetch_message(old_msg_id)
                        await old_msg.delete()
                    except Exception:
                        pass  # fail silently

            #  Generate new tierlist (pure, no I/O) 
            content = generate_tierlist_text(data, guild_id)

            #  Send new message 
            channel = interaction.channel
            new_msg = await channel.send(content)

            #  Save updated message info back to JSON safely 
            async with FILE_LOCK:
                data.setdefault(str(guild_id), {}).setdefault("tierlist_channel", {})
                data[str(guild_id)]["tierlist_channel"]["channel_id"] = channel.id
                data[str(guild_id)]["tierlist_channel"]["message_id"] = new_msg.id
                await asyncio.to_thread(write_json, data)

            #  Respond to the user immediately 
            await interaction.response.send_message(
                "Tier list has been built (or rebuilt)!", ephemeral=True
            )

        except Exception as e:
            print("Error in buildtierlist command:", e)
            try:
                await interaction.response.send_message(
                    f"Error building tier list: {e}", ephemeral=True
                )
            except Exception:
                pass
    @app_commands.command(name="cleartierlistdata", description="Clears all tierlist data in the server data and user data for this server.")
    async def clear_tierlist_data(self, interaction: discord.Interaction):
        if(not await admin_m.check_admin_status(self.bot, interaction)):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe? (although why do you wanna reload the bot)", ephemeral=True)
            return
        reset_votes(interaction.guild_id)
        print("Votes reset!")
        await interaction.response.send_message("Tier list votes reset!")
        

    @app_commands.command(name="reload", description="reloads all commands")
    async def reload(self, interaction: discord.Interaction):
        if(not await admin_m.check_admin_status(self.bot, interaction)):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe? (although why do you wanna reload the bot)", ephemeral=True)
            return

        failed = []
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                ext = f"cogs.{filename[:-3]}"
                try:
                    await self.bot.reload_extension(ext)
                except Exception as e:
                    failed.append(f"{ext} ({type(e).__name__}: {e})")

        if failed:
            await interaction.response.send_message(f"Some commands failed to reload:\n" + "\n".join(failed), ephemeral=True)
        else:
            await interaction.response.send_message("All commands reloaded successfully.", ephemeral=True)

    @app_commands.command(name="remoteecho", description="Make the bot send a message to a specified channel")
    async def remoteecho(self, interaction: discord.Interaction, channel: discord.TextChannel, *, message: str):
        if(not await admin_m.check_admin_status(self.bot, interaction)):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        try:
            await channel.send(message)
            await interaction.response.send_message(f"Message sent to {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to send messages in that channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error sending message: {e}", ephemeral=True)

    @app_commands.command(name="toast", description="toast :3")
    async def toast(self, interaction: discord.Interaction):
        await interaction.response.send_message("🍞 :)")

    @app_commands.command(name="checkbalance", description="check your balance")
    async def checkbalance(self, interaction: discord.Interaction):
        if hasattr(self.bot, "economy_manager"):
            economy = self.bot.economy_manager
        else:
            economy = None

        if economy is None:
            await interaction.response.send_message("Economy system is not available.", ephemeral=True)
            return

        balance = economy.get_balance(interaction.user.id)
        await interaction.response.send_message(f"Your balance is {balance} coins.", ephemeral=True)
        
    @app_commands.command(name="addstatstoflavorslist", description="admin: add/update atk/def stats to flavor roles from a list")
    async def addstatstoflavorslist(self, interaction: discord.Interaction, item_list: str):
        if not await admin_m.check_admin_status(self.bot, interaction):
            await interaction.response.send_message(
                "Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", 
                ephemeral=True
            )
            return

        items = [item.strip() for item in item_list.split(",")]

        with open("data/server_data.json", "r+") as f:
            data = json.load(f)
            guild_id = str(interaction.guild_id)

            # ensure guild exists
            if guild_id not in data:
                data[guild_id] = {}

            if "flavor_roles" not in data[guild_id]:
                data[guild_id]["flavor_roles"] = {}

            for item_name in items:
                total = random.randint(16, 20)

                # give slight bias: atk or def can vary +-2 from half
                half = total // 2
                atk = half + random.randint(-2, 2)
                atk = max(1, min(atk, total - 1))  # clamp atk between 1 and total-1
                deff = total - atk

                # create or update the item
                data[guild_id]["flavor_roles"][item_name] = {
                    "duel_stats": {
                        "atk": atk,
                        "def": deff
                    }
                }
                print(f"Set duel stats for {item_name}: atk={atk}, def={deff} (total={total})")

            # write changes
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()

        print("server_data updated successfully.")
        await interaction.response.send_message("Duel stats added/updated for items in the list!", ephemeral=True)

    
    @app_commands.command(name="mwr", description="Returns member count with role provided.")
    async def mwr(self, interaction: discord.Interaction, role: discord.Role):
        count = sum(1 for member in interaction.guild.members if role in member.roles)
        await interaction.response.send_message(f"{role.name} has {count} members.", ephemeral=True)

    @app_commands.command(name="addflavorstodb", description="Add flavors to database")
    async def addflavorstodb(self, interaction: discord.Interaction, flavors: str):
        flavor_list = flavors.strip().split(",")
        with open("data/server_data.json", "r+") as f:
            data = json.load(f)
            guild_id = str(interaction.guild_id)

            # ensure guild exists
            if guild_id not in data:
                data[guild_id] = {}

            if "flavor_roles" not in data[guild_id]:
                data[guild_id]["flavor_roles"] = {}
            
            for flavor in flavor_list:
                print(flavor.strip())
                data[guild_id]["flavor_roles"][flavor] = {}

            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
  
        await interaction.response.send_message("Added flavor(s)!")

async def setup(bot):
    await bot.add_cog(Config(bot))    @app_commands.command(name="convertrole", description="Convert users from the old role to the new role")
    async def convertrole(self, interaction: discord.Interaction):
        if not await admin_m.check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only command.", ephemeral=True)
            return

        old_role_id = 1109541791054696460
        new_role_id = 462854714682376192
        old_role = guild.get_role(old_role_id)
        new_role = guild.get_role(new_role_id)
        if not old_role or not new_role:
            await interaction.response.send_message("Unable to locate one of the roles.", ephemeral=True)
            return

        converted = 0
        for member in old_role.members:
            try:
                await member.remove_roles(old_role, reason="Role conversion")
                await member.add_roles(new_role, reason="Role conversion")
                converted += 1
            except discord.HTTPException:
                continue

        await interaction.response.send_message(f"Converted {converted} members to the new role.", ephemeral=True)
