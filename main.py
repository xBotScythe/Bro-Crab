# bot.py
import discord
from discord.ext import commands, tasks
import os, asyncio
from dotenv import load_dotenv    
from utils import booster_manager as boost_m
from contextmenu.context import make_save_quote_command 

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in .env file")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

class xBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=None  # optional; can set if you want
        )

    async def setup_hook(self):
        # Load all cogs
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded cog: {filename[:-3]}")

        # Context menu
        self.tree.add_command(make_save_quote_command(self))

        # Sync commands (safer method)
        await self.tree.sync()
        print("Slash commands synced (setup_hook).")


bot = xBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print("Guilds:", [g.name for g in bot.guilds])
    print("--")

    # Start booster task ONCE
    if not refresh_booster_data.is_running():
        refresh_booster_data.start()

    # Run initial sync AFTER ready
    asyncio.create_task(boost_m.load_users(bot))


@bot.event
async def on_interaction(interaction):
    print("Received interaction:", interaction.data.get("name"))


@bot.event
async def on_member_update(before, after):
    try:
        await boost_m.update_single_user(bot, after)
    except Exception as e:
        print(f"Error updating {after}: {e}")


@tasks.loop(hours=6)
async def refresh_booster_data():
    await boost_m.load_users(bot)


async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
