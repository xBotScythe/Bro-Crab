# bot.py
import discord
from discord.ext import commands, tasks
import os, json, asyncio
from dotenv import load_dotenv    
from utils import booster_manager as boost_m
from contextmenu.context import make_save_quote_command 
from utils.delete_log_manager import log_deleted_message

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in .env file, did you provide one?")

#  Intents 
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

#  Bot class 
class xBot(commands.Bot):
    def __init__(self, command_prefix="!", **kwargs):
        super().__init__(command_prefix=command_prefix, **kwargs)

    async def setup_hook(self):
        #  Load all cogs 
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded cog: {filename[:-3]}")

        #  Context menu commands 
        self.tree.add_command(make_save_quote_command(self))

        #  Sync slash commands 
        await self.sync_commands()

        #  Start background tasks 
        refresh_booster_data.start()
        print("Booster data task started.")

        #  Load booster data at startup 
        await boost_m.load_users(self)
        print("Initial booster data loaded.")

    async def sync_commands(self):
        """Try to sync slash commands to a dev guild first, fallback to global."""
        DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")  # optional for dev testing
        try:
            if DEV_GUILD_ID:
                guild = discord.Object(id=int(DEV_GUILD_ID))
                await asyncio.wait_for(self.tree.sync(guild=guild), timeout=15)
                print(f"Slash commands synced to dev guild ({DEV_GUILD_ID}).")
            else:
                await asyncio.wait_for(self.tree.sync(), timeout=15)
                print("Global slash commands synced.")
        except asyncio.TimeoutError:
            print("Slash command sync timed out — you can retry later.")
        except Exception as e:
            print(f"Error syncing commands: {e}")

#  Bot instance 
bot = xBot(command_prefix="!", intents=intents)

#  Events 
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print("--")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    try:
        await boost_m.update_single_user(bot, after)
    except Exception as e:
        print(f"Error updating {after}: {e}")

@bot.event
async def on_message_delete(message):
    if message.author == bot.user:
        return
    try:
        await log_deleted_message(bot, message)
    except Exception as e:
        print(f"delete log failed for {message.id}: {e}")

#  Background tasks 
@tasks.loop(hours=6)
async def refresh_booster_data():
    await boost_m.load_users(bot)

#  Run bot 
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
