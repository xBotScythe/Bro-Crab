# cogs/hottakes.py

import discord
from discord import app_commands
from discord.ext import commands
import json, os, time

DATA_FILE = "data/server_data.json"
UP = "⬆️"
DOWN = "⬇️"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


class HotTakes(commands.Cog):
    """
    Cog for hot take commands
    """

    def __init__(self, bot):
        self.bot = bot


    # /hottake — submit a take
    @app_commands.command(name="hottake", description="Submit a hot take and let the server vote.")
    @app_commands.describe(take="Your hot take")
    async def hottake(self, interaction: discord.Interaction, take: str):

        guild_id = str(interaction.guild_id)
        user_id = interaction.user.id

        data = load_data()

        # ensure guild exists
        if guild_id not in data:
            data[guild_id] = {
                "boosters": [],
                "staff": [],
                "cooldowns": {},
                "takes": {}
            }

        # ensure "takes" key exists
        if "takes" not in data[guild_id]:
            data[guild_id]["takes"] = {}

        await interaction.response.defer(ephemeral=False)

        # send message
        msg = await interaction.followup.send(
            f"**Hot Take from {interaction.user.mention}:**\n{take}"
        )

        # add reactions
        await msg.add_reaction(UP)
        await msg.add_reaction(DOWN)

        # store take
        data[guild_id]["takes"][str(msg.id)] = {
            "author": user_id,
            "take": take,
            "up": 0,
            "down": 0,
            "score": 0,
            "timestamp": int(time.time())
        }

        save_data(data)



    # -----------------------------------
    # Reaction listener
    # -----------------------------------
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):

        if user.bot:
            return
        
        if reaction.message.guild is None:
            return

        guild_id = str(reaction.message.guild.id)
        msg_id = str(reaction.message.id)

        data = load_data()

        if guild_id not in data:
            return
        if "takes" not in data[guild_id]:
            return
        if msg_id not in data[guild_id]["takes"]:
            return
        
        if reaction.emoji not in (UP, DOWN):
            return

        # recount actual reactions
        up = 0
        down = 0

        for r in reaction.message.reactions:
            if r.emoji == UP:
                up = r.count - 1
            if r.emoji == DOWN:
                down = r.count - 1

        tk = data[guild_id]["takes"][msg_id]
        tk["up"] = up
        tk["down"] = down
        tk["score"] = up - down

        save_data(data)



    # /ranktakes — most controversial
    @app_commands.command(name="ranktakes", description="Show the server's most controversial hot takes.")
    async def ranktakes(self, interaction: discord.Interaction):

        guild_id = str(interaction.guild_id)
        data = load_data()

        if guild_id not in data or "takes" not in data[guild_id] or len(data[guild_id]["takes"]) == 0:
            return await interaction.response.send_message(
                "no hot takes found for this server.", ephemeral=True
            )

        takes = data[guild_id]["takes"]

        # sort lowest score first (most disagreed)
        ranked = sorted(
            takes.items(),
            key=lambda x: x[1]["score"]
        )

        lines = []
        for msg_id, info in ranked[:10]:
            lines.append(
                f"**{info['score']}** — {info['take']} *(by <@{info['author']}>)*\n↑ {info['up']}  ↓ {info['down']}"
            )

        output = "\n\n".join(lines)

        await interaction.response.send_message(
            f"**Top Controversial Takes**\n\n{output}",
            ephemeral=True
        )



async def setup(bot: commands.Bot):
    await bot.add_cog(HotTakes(bot))
