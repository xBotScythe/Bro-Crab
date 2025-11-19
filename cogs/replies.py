import asyncio
import os
from io import BytesIO
from urllib.parse import urlparse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.admin_manager import check_admin_status


class ReplyModal(discord.ui.Modal, title="Reply as Bro Crab"):
    reply_text = discord.ui.TextInput(
        label="your reply",
        placeholder="type your message...",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )
    image_input = discord.ui.TextInput(
        label="image url or type 'upload' (optional)",
        placeholder="https://example.com/image.png or upload",
        style=discord.TextStyle.short,
        required=False,
        max_length=400,
    )

    def __init__(self, bot: commands.Bot, target_message: discord.Message):
        super().__init__()
        self.bot = bot
        self.target_message = target_message

    async def _download_image(self, url: str) -> discord.File:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise ValueError("couldn't download that image (bad status).")
                    content_type = (resp.headers.get("Content-Type") or "").lower()
                    if "image" not in content_type:
                        raise ValueError("that link doesn't point to an image.")
                    data = await resp.read()
            except aiohttp.ClientError:
                raise ValueError("failed to download image. check the link and try again.")

        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        base, ext = os.path.splitext(filename)
        if not ext:
            ext = ".png"
        if not base:
            base = "image"
        return discord.File(BytesIO(data), filename=f"{base}{ext}")

    def _attachment_is_image(self, attachment: discord.Attachment) -> bool:
        if attachment.content_type:
            return "image" in attachment.content_type.lower()
        _, ext = os.path.splitext(attachment.filename or "")
        return ext.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    async def _collect_uploaded_file(self, interaction: discord.Interaction) -> discord.File:
        await interaction.followup.send(
            "upload the image in this channel within 60 seconds. i'll grab the first attachment.",
            ephemeral=True,
        )

        def check(msg: discord.Message):
            return (
                msg.author.id == interaction.user.id
                and msg.channel == self.target_message.channel
                and msg.attachments
            )

        try:
            upload_msg = await self.bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            raise ValueError("no attachment received in time.")

        attachment = next(
            (att for att in upload_msg.attachments if self._attachment_is_image(att)),
            None,
        )
        if not attachment:
            raise ValueError("please upload at least one image file.")

        data = await attachment.read()
        file = discord.File(BytesIO(data), filename=attachment.filename or "image.png")

        try:
            await upload_msg.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass
        return file

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        file = None
        image_value = self.image_input.value.strip()

        try:
            if image_value and image_value.lower() == "upload":
                file = await self._collect_uploaded_file(interaction)
            elif image_value:
                file = await self._download_image(image_value)

            await self.target_message.reply(self.reply_text.value, file=file)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        finally:
            if file:
                file.close()

        await interaction.followup.send("reply sent!", ephemeral=True)


def make_reply_callback(bot: commands.Bot):
    async def reply_as_bro_crab(interaction: discord.Interaction, message: discord.Message):
        if not await check_admin_status(bot, interaction):
            await interaction.response.send_message(
                "sorry bro, you're not cool enough to use this. ask a mod politely maybe?",
                ephemeral=True,
            )
            return

        modal = ReplyModal(bot, message)
        await interaction.response.send_modal(modal)

    return reply_as_bro_crab


class Replies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    await bot.add_cog(Replies(bot))

    bot.tree.add_command(
        app_commands.ContextMenu(
            name="Reply as Bro Crab",
            callback=make_reply_callback(bot),
        )
    )
