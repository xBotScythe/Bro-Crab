import discord
from discord.ext import commands
import random
from utils.automation_manager import load_auto_responses
from utils.json_manager import load_json_async

class AutoResponses(commands.Cog):
    """
    A cog for various bot automations not controlled by the util managers
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_reacts = load_auto_responses()
    

    # checks message content 
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        try:
            self.auto_reacts = load_auto_responses()
            for auto_react in self.auto_reacts[str(message.guild.id)]["auto_reacts"]:
                trigger = auto_react["content"].lower().strip()
                msg = message.content.lower().strip()

                if trigger in msg:
                    emoji_raw = auto_react["emoji"]

                    # custom emoji format: <:name:id>
                    if emoji_raw.startswith("<:") and emoji_raw.endswith(">"):
                        parts = emoji_raw.strip("<>").split(":")  # ["", "name", "id"]
                        emoji_id = int(parts[2])
                        emoji = discord.utils.get(message.guild.emojis, id=emoji_id)
                    else:
                        emoji = emoji_raw  # unicode emoji

                    if emoji:
                        await message.add_reaction(emoji)
                    else:
                        print(f"[AutoReact] Emoji not found: {emoji_raw}")

            # handle auto reply
            data = await load_json_async("data/autoresponses.json")
            quips = data.get("quips", {})
            
            for key in quips.keys():
                if msg in key:
                    message.reply(random.choice(quips[key]))
                    break

        except Exception as e:
            return

async def setup(bot):
    await bot.add_cog(AutoResponses(bot))
