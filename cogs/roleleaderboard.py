import discord
from discord.ext import commands
from discord import app_commands
from utils.admin_manager import get_flavor_roles

class RoleLeaderboardView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.current_page = 0

        # Disable "Prev" on first page
        self.prev_button.disabled = True
        # Disable "Next" if only one page
        if len(pages) == 1:
            self.next_button.disabled = True

    async def update(self, interaction: discord.Interaction):
        """Helper to update embed on page switch."""
        embed = self.pages[self.current_page]

        # Update disabled state
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page == len(self.pages) - 1)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        await self.update(interaction)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        await self.update(interaction)


class RoleLeaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="buildroleleaderboard",
        description="Shows all roles sorted by number of members, paginated"
    )
    async def buildroleleaderboard(self, interaction: discord.Interaction):

        roles = interaction.guild.roles
        await interaction.response.defer(ephemeral=True)
        valid_roles = await get_flavor_roles(interaction)
        # Build list of (role, member count)
        role_counts = []
        for role in roles:
            if role.name == "@everyone":
                continue
            if role.name not in valid_roles:
                continue
            count = sum(1 for member in interaction.guild.members if role in member.roles)
            role_counts.append((role, count))

        # Sort largest → smallest
        role_counts.sort(key=lambda r: r[1], reverse=True)
        # Build embeds (10 roles per page)
        pages = []
        per_page = 10
        total_pages = (len(role_counts) + per_page - 1) // per_page

        for i in range(total_pages):
            start = i * per_page
            end = start + per_page
            chunk = role_counts[start:end]

            embed = discord.Embed(
                title=f"Role Leaderboard (Page {i+1}/{total_pages})",
                color=discord.Color.blurple()
            )

            for role, count in chunk:
                embed.add_field(
                    name=f"{role.name}",
                    value=f"{count} member{'s' if count != 1 else ''}",
                    inline=False
                )

            pages.append(embed)

        # Send first page with pagination buttons
        view = RoleLeaderboardView(pages)
        await interaction.followup.send(embed=pages[0], view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleLeaderboard(bot))
