import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.bingo_manager import create_board, get_board, render_board


class Bingo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _render_image(self, board: dict) -> discord.File:
        buffer = await asyncio.to_thread(render_board, board)
        return discord.File(buffer, filename="dew_bingo.png")

    async def _send_board(self, interaction: discord.Interaction, board: dict, notice: Optional[str] = None):
        file = await self._render_image(board)
        if notice:
            await interaction.followup.send(content=notice, file=file, ephemeral=True)
        else:
            await interaction.followup.send(file=file, ephemeral=True)

    @app_commands.command(name="bingocreate", description="Create a Mountain Dew bingo board.")
    @app_commands.describe(size="Pick a board size.")
    @app_commands.choices(
        size=[
            app_commands.Choice(name="5 x 5", value=5),
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
        await self._send_board(interaction, board, notice)

    @app_commands.command(name="viewbingoboard", description="View your current bingo board.")
    async def viewbingoboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not interaction.guild_id:
            await interaction.followup.send("This command only works inside a server.", ephemeral=True)
            return
        board = await get_board(interaction.guild_id, interaction.user.id)
        if not board:
            await interaction.followup.send("You don't have a board yet. Run /bingocreate first!", ephemeral=True)
            return
        await self._send_board(interaction, board)

async def setup(bot: commands.Bot):
    await bot.add_cog(Bingo(bot))
