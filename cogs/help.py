import discord
from discord import app_commands
from discord.ext import commands

HELP_PAGES = [
    (
        "Fun Commands",
        [
            ("/blackjack", "play blackjack with bro crab"),
            ("/gamble", "lets go gambling!"),
            ("/toast", "toast :)"),
            ("/checkbalance", "look at your balance"),
            ("/roast", "roast yourself (or a friend if youre cool)"),
            ("/recall", "pull quotes saved via save quote"),
            ("/controller", "open the DDD Plays Pokemon controller"),
            ("/sequence", "send a sequence of controls to the emulator"),
            ("/leaderboard", "see top button mashers"),
            ("/hottakes", "submit a hot take"),
            ("/ranktakes", "view the most controversial takes"),
        ],
    ),
    (
        "Utility Commands",
        [
            ("/mwr", "count how many members have a role"),
            ("/mdw", "pull a flavor write-up from Dew Wiki"),
            ("/buildroleleaderboard", "show the most common flavor roles"),
        ],
    ),
    (
        "Booster Perks",
        [
            ("/roast <member>", "boosters can roast others"),
            ("/catchadew", "catch a DEW!"),
            ("/dewluxe", "create or edit your custom role"),
        ],
    ),
    (
        "Tierlist Commands",
        [
            ("/ratedew", "rate a flavor and cross it off your bingo board"),
            ("/vote", "daily server-wide vote"),
            ("/flavorstats", "see stats for a flavor"),
            ("/buildusertierlist", "build your personal tier list"),
            ("/bingocreate", "create a new Mountain Dew bingo board"),
            ("/viewbingoboard", "view your current board image"),
        ],
    ),
    (
        "Admin Commands",
        [
            ("/addroast", "add a roast line"),
            ("/addautoroast", "register auto reaction"),
            ("/boomer", "start/end boomer process"),
            ("/warn", "dm warning + log entry"),
            ("/settierlistchannel", "set server tier channel"),
            ("/additemtovote", "add an item to the vote list"),
            ("/additemsfromlist", "bulk add vote items"),
            ("/addavailabledew", "add flavors to the bingo board pool"),
            ("/buildtierlist", "rebuild server tier list"),
            ("/cleartierlistdata", "wipe tier data"),
            ("/reload", "reload every cog"),
            ("/remoteecho", "relay a message through the bot"),
            ("/addstatstoflavorlist", "seed duel stats for flavors"),
            ("/addflavorstodb", "store flavors in db"),
        ],
    ),
]


class HelpView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=120)
        self.pages = pages
        self.index = 0
        self.message = None
        self.update_state()

    def update_state(self):
        self.previous.disabled = self.index == 0
        self.next.disabled = self.index == len(self.pages) - 1

    def build_embed(self):
        title, entries = self.pages[self.index]
        description = "\n".join(f"• **{cmd}** — {desc}" for cmd, desc in entries)
        embed = discord.Embed(title=f"Help — {title}", description=description, color=discord.Color.green())
        embed.set_footer(text=f"Page {self.index + 1}/{len(self.pages)}")
        return embed

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.gray)
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        self.update_state()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if self.index < len(self.pages) - 1:
            self.index += 1
        self.update_state()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Command list!")
    async def help(self, interaction: discord.Interaction):
        view = HelpView(HELP_PAGES)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
