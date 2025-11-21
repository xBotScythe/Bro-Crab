import asyncio
from typing import Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils.bingo_manager import (
    create_board,
    format_board_rows,
    get_board,
    render_board,
)


class Bingo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _render_embed(self, board: dict, title: str) -> Tuple[discord.Embed, discord.File]:
        buffer = await asyncio.to_thread(render_board, board)
        file = discord.File(buffer, filename="dew_bingo.png")
        description = "\n".join(format_board_rows(board))
        embed = discord.Embed(title=title, description=description, color=discord.Color.green())
        embed.set_image(url="attachment://dew_bingo.png")
        return embed, file

    async def _send_board(self, interaction: discord.Interaction, board: dict, title: str, notice: Optional[str] = None):
        embed, file = await self._render_embed(board, title)
        content = notice or ""
        await interaction.followup.send(content=content, embed=embed, file=file, ephemeral=True)

    @app_commands.command(name="bingocreate", description="Create a Mountain Dew bingo board.")
    @app_commands.describe(size="Pick a board size.")
    @app_commands.choices(
        size=[
            app_commands.Choice(name="3 × 3", value=3),
            app_commands.Choice(name="4 × 4", value=4),
            app_commands.Choice(name="5 × 5", value=5),
        ]
    )
    async def bingocreate(self, interaction: discord.Interaction, size: app_commands.Choice[int]):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not interaction.guild_id:
            await interaction.followup.send("This command only works inside a server.", ephemeral=True)
            return
        board_size = size.value
        previous_board = await get_board(interaction.guild_id, interaction.user.id)
        try:
            board = await create_board(interaction.guild_id, interaction.user.id, board_size)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if previous_board:
            notice = f"Board replaced with a fresh {board_size}×{board_size} layout."
        else:
            notice = f"New {board_size}×{board_size} board ready. Free space is already covered, go find those Dew flavors!"
        display_name = interaction.user.display_name if isinstance(interaction.user, discord.Member) else interaction.user.name
        await self._send_board(
            interaction,
            board,
            f"{display_name}'s Bingo Board",
            notice,
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Bingo(bot))
