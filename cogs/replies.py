import discord
from discord.ext import commands
from discord import app_commands
from utils.admin_manager import check_admin_status


# Modal for Bro Crab reply
class ReplyModal(discord.ui.Modal, title="Reply as Bro Crab"):
    reply_text = discord.ui.TextInput(
        label="Your reply",
        placeholder="Type your message...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    def __init__(self, target_message: discord.Message):
        super().__init__()
        self.target_message = target_message

    async def on_submit(self, interaction: discord.Interaction):
        await self.target_message.reply(self.reply_text.value)
        await interaction.response.send_message("Reply sent!", ephemeral=True)


# return callback with bot included
def make_reply_callback(bot):
    async def reply_as_bro_crab(interaction: discord.Interaction, message: discord.Message):

        # now call admin check 
        if not await check_admin_status(bot, interaction):
            await interaction.response.send_message(
                "Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?",
                ephemeral=True
            )
            return

        modal = ReplyModal(message)
        await interaction.response.send_modal(modal)

    return reply_as_bro_crab  # closure with bot captured


# Cog (empty)
class Replies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


# Setup
async def setup(bot: commands.Bot):
    await bot.add_cog(Replies(bot))

    # register context menu using the factory
    bot.tree.add_command(
        app_commands.ContextMenu(
            name="Reply as Bro Crab",
            callback=make_reply_callback(bot)  # bot is now passed correctly
        )
    )
