# sets balance admin command

import discord
from discord import app_commands
from discord.ext import commands
from utils.economy_manager import EconomyManager
from utils.admin_manager import check_admin_status

class Balance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # prefer a shared EconomyManager attached to the bot to avoid multiple in-memory copies
        if hasattr(bot, "economy_manager"):
            self.economy = bot.economy_manager
        else:
            self.economy = EconomyManager(bot)
            bot.economy_manager = self.economy

    @app_commands.command(name="setbalance", description="Set a user's balance (admin only)")
    @app_commands.describe(user="The user to set the balance for", amount="The amount to set the balance to")
    async def set_balance(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        if amount < 0:
            await interaction.response.send_message("Balance cannot be negative.", ephemeral=True)
            return

        self.economy.set_balance(user.id, amount)
        await interaction.response.send_message(f"Set {user.mention}'s balance to {amount} coins.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Balance(bot))