import discord
from discord.ext import commands
from discord import app_commands
import os, json
from utils.booster_manager import check_boost_status
from utils.quote_manager import save_quote
from utils.cooldown_manager import *

def make_save_quote_command(bot: commands.Bot):
    async def save_quote_command(interaction: discord.Interaction, message: discord.Message):
        await save_quote(str(interaction.user.id), message)
        print(f"Quote saved by user: {interaction.user.name}")
        await interaction.response.send_message("Quote saved!", ephemeral=True)
    return app_commands.ContextMenu(name="Save Quote", callback=save_quote_command)

