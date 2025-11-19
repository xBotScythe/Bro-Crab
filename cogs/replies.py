import os
from io import BytesIO
from urllib.parse import urlparse

import aiohttp
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
    # optional image input
    image_url = discord.ui.TextInput(
        label="Image URL (optional)",
        placeholder="https://example.com/image.png",
        style=discord.TextStyle.short,
        required=False,
        max_length=400,
    )

    def __init__(self, target_message: discord.Message):
        super().__init__()
        self.target_message = target_message

    async def _download_image(self, url: str) -> discord.File:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise ValueError("Couldn't download that image (bad status).")
                    content_type = resp.headers.get("Content-Type", "") or ""
                    if "image" not in content_type.lower():
                        raise ValueError("That link doesn't point to an image.")
                    data = await resp.read()
            except aiohttp.ClientError:
                raise ValueError("Failed to download image. Check the link and try again.")

        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        base, ext = os.path.splitext(filename)
        if not ext:
            ext = ".png"
        if not base:
            base = "image"
        return discord.File(BytesIO(data), filename=f"{base}{ext}")

    async def on_submit(self, interaction: discord.Interaction):
        file = None
        image_link = self.image_url.value.strip()
        if image_link:
            try:
                file = await self._download_image(image_link)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        await self.target_message.reply(self.reply_text.value, file=file)
        if file:
            file.close()
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

    @app_commands.context_menu(name="Reply as Bro Crab")
    async def reply_ctx(self, interaction: discord.Interaction, message: discord.Message):

        # permission check
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message(
                "Sorry bro, you're not cool enough to use this.",
                ephemeral=True
            )
            return

        modal = ReplyModal(message)
        await interaction.response.send_modal(modal)


# Setup
async def setup(bot: commands.Bot):
    await bot.add_cog(Replies(bot))