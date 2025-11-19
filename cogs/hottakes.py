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

class RankTakesView(discord.ui.View):
    def __init__(self, pages, user):
        super().__init__(timeout=60)
        self.pages = pages
        self.user = user
        self.current_page = 0

    async def update(self, interaction):
        embed = self.pages[self.current_page]
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("not your menu.", ephemeral=True)

        if self.current_page > 0:
            self.current_page -= 1
            await self.update(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("not your menu.", ephemeral=True)

        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update(interaction)


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

        # sort by most controversial (lowest score)
        ranked = sorted(takes.items(), key=lambda x: x[1]["score"])

        # create pages of 5
        page_size = 5
        pages = []

        for i in range(0, len(ranked), page_size):
            chunk = ranked[i:i + page_size]

            embed = discord.Embed(
                title="🔥 Most Controversial Hot Takes",
                color=discord.Color.orange()
            )

            for msg_id, info in chunk:
                embed.add_field(
                    name=f"{info['score']} — {info['take']}",
                    value=f"by <@{info['author']}> — 👍 {info['up']} | 👎 {info['down']}",
                    inline=False
                )

            embed.set_footer(text=f"Page {len(pages) + 1}")
            pages.append(embed)

        # first page
        view = RankTakesView(pages, interaction.user)
        await interaction.response.send_message(
            embed=pages[0],
            view=view,
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(HotTakes(bot))
