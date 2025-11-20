import discord
from discord import app_commands
from discord.ext import commands


HELP_PAGES = [
    (
        "fun",
        """
        **/blackjack** - play blackjack
        **/gamble** - gamble coins
        **/toast** - send toast :3
        **/checkbalance** - checks user balance
        **/roast** - roasts yourself!
        **/recall** - recall quotes by members saved by Bro Crab! right click a message, click apps, and click save quote to save a quote.
        **/controller** - brings up controls for DDD Plays Pokemon!
        **/sequence** - send a sequence of controls to DDD Plays Pokemon!
        **/leaderboard** - returns leaderboard of users with most button presses in DDD Plays Pokemon!
        **/hottakes** - give bro crab a hot take!
        **/ranktakes** - returns the most controversial takes in order
        """,
    ),
    (    
        "utility",
        """
        **/mwr** - returns member count with role provided
        **/mdw** - returns flavor information (if findable) from Dew Wiki!
        **/buildroleleaderboard** - returns a leaderboard embed with most used flavor roles!

        """,
    ),
    (
        "booster perks",
        """
        **/roast <member>** - roast a member!
        **/catchadew** - catch a DEW!
        **/dewluxe** make or edit custom booster role
        """,
    ),
    (
        "tierlists",
        """
        **/ratedew** - rate a dew flavor 1-10 for the personal tier list!
        **/vote** daily server-wide flavor vote
        **/flavorstats** show flavor stats
        **/buildusertierlist** build personal tier list
        """,
    ),
    (
                "admin",
        """
        **/addroast** - add a roast line
        **/addautoroast** - register auto reaction
        **/boomer** - boomer someone
        **/warn** - issue dm warning and log it
        **/setbalance** - sets user balance
        **/settierlistchannel** - sets tier list channel for the server tier list
        **/additemtovote** - adds item to voting list
        **/additemsfromlist** - adds items to voting list from comma separated list
        **/buildtierlist** - rebuild server tier list
        **/cleartierlistdata** - clears tier list data
        **/reload** - reloads all cogs (commands)
        **/remoteecho - sends a message to a specific channel
        **/addstatstoflavorlist** - adds random duel stats for comma separated list of flavors
        **/addflavorstodb** - adds flavor(s) from comma separated list to general server flavor database
        """,
    )
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
        title, body = self.pages[self.index]
        embed = discord.Embed(title=f"Help — {title}", description=body.strip(), color=discord.Color.green())
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

    @app_commands.command(name="help", description="Show paginated help embeds")
    async def help(self, interaction: discord.Interaction):
        view = HelpView(HELP_PAGES)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
