"""
Gambling commands for xBot
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
from utils.cooldown_manager import *
from utils.economy_manager import EconomyManager

class Gamble(commands.Cog):
    """
    Cog for gambling commands
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if hasattr(bot, "economy_manager"):
            self.economy = bot.economy_manager
        else:
            self.economy = EconomyManager(bot)
            bot.economy_manager = self.economy

    @app_commands.command(name="gamble", description="lets go gambling!")
    @app_commands.describe(amount="Amount to gamble")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        user_id = interaction.user.id
        balance = self.economy.get_balance(user_id)

        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return

        if amount > balance:
            await interaction.response.send_message("You don't have enough balance to gamble that amount.", ephemeral=True)
            return
        
        await self.play_slots(interaction, amount)



    async def play_slots(self, interaction: discord.Interaction, amount: int):
        symbols = ["<:happydewyear:629161277536731157>", "<:mauican:661085431252647947>", "<:dewcan:653121636551098379>", "<:zsvoltage:979868792823889970>", "<:dew25:1293718618546110607>", "<:brogun:836719959308107796>"]
        result = [random.choice(symbols) for _ in range(3)]

        if result[0] == result[1] == result[2]:
            winnings = amount * 5
            self.economy.update_balance(interaction.user.id, winnings)
            await interaction.response.send_message(f"🎰 {' | '.join(result)} 🎰\nJackpot! You won {winnings} coins!", ephemeral=True)
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            winnings = amount * 2
            self.economy.update_balance(interaction.user.id, winnings)
            await interaction.response.send_message(f"🎰 {' | '.join(result)} 🎰\nYou won {winnings} coins!", ephemeral=True)
        else:
            self.economy.update_balance(interaction.user.id, -amount)
            await interaction.response.send_message(f"🎰 {' | '.join(result)} 🎰\nYou lost {amount} coins.", ephemeral=True)
        

async def setup(bot: commands.Bot):
    await bot.add_cog(Gamble(bot))
