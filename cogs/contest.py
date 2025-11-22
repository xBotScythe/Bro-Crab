import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import contest_manager as cm
from utils.admin_manager import check_admin_status

CONTEST_DESIGN_CHANNEL_ID = int(os.getenv("CONTEST_DESIGN_CHANNEL_ID", "0") or 0)
CONTEST_WIN_CHANNEL_ID = int(os.getenv("CONTEST_WIN_CHANNEL_ID", "0") or 0)

class Contest(commands.Cog):
    # contest cog: lets users submit dewsign concepts, admins release + archive
    def __init__(self, bot):
        self.bot = bot
        self._archive_task.start()

    def cog_unload(self):
        self._archive_task.cancel()

    async def _get_channel(self, channel_id):
        # helper resolves channel/thread by id with fetch fallback
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            return channel
        try:
            fetched = await self.bot.fetch_channel(channel_id)
            if isinstance(fetched, discord.TextChannel):
                return fetched
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
        return None

    async def _get_win_channel(self):
        # resolves contest win announcement channel if configured
        return await self._get_channel(CONTEST_WIN_CHANNEL_ID)

    @app_commands.command(name="dewsignsubmit", description="Submit a dewsign flavor concept to the contest queue.")
    @app_commands.describe(flavor_name="name of your creation", image="image attachment of your design")
    async def dewsignsubmit(self, interaction: discord.Interaction, flavor_name: str, image: discord.Attachment):
        # design submitter uploads an image tied to a flavor name
        if interaction.guild is None:
            await interaction.response.send_message("Guild only command.", ephemeral=True)
            return
        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message("Please upload an image file.", ephemeral=True)
            return
        try:
            await cm.add_design_submission(interaction.guild_id, interaction.user.id, flavor_name, image.url)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message("dewsign submitted!", ephemeral=True)

    @app_commands.command(name="startcontest", description="Start a contest with a message and end date.")
    @app_commands.describe(
        message="announcement / flavor concept",
        end_date="ISO timestamp (YYYY-MM-DD or full) — defaults to 4 days from now",
    )
    async def startcontest(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel, end_date: Optional[str] = None):
        # admin starts a contest window for dewsign submissions
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Missing permissions.", ephemeral=True)
            return
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
            except ValueError:
                await interaction.response.send_message("Use ISO date format YYYY-MM-DD or full timestamp.", ephemeral=True)
                return
        else:
            end_dt = datetime.now() + timedelta(days=4)
        await cm.start_contest(interaction.guild_id, message, end_dt.isoformat(), channel.id)
        embed = discord.Embed(title="Contest Started", description=message, color=discord.Color.green())
        ts = int(end_dt.timestamp())
        embed.add_field(name="End Date", value=f"<t:{ts}:F> — <t:{ts}:R>")
        embed.add_field(name="Contest Channel", value=channel.mention)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="releasedewsigns", description="Publish queued designs to the showcase channel.")
    async def releasedewsigns(self, interaction: discord.Interaction):
        # admin drops queued designs into showcase channel
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Missing permissions.", ephemeral=True)
            return
        contest = await cm.load_contest(interaction.guild_id)
        contest_channel = await self._get_channel(contest.get("channel_id"))
        if contest_channel is None:
            await interaction.response.send_message("Contest channel not configured.", ephemeral=True)
            return
        queue = await cm.get_design_queue(interaction.guild_id)
        if not queue:
            await interaction.response.send_message("No designs to release.", ephemeral=True)
            return
        queue = await cm.clear_design_queue(interaction.guild_id)
        for entry in queue:
            author = interaction.guild.get_member(entry["author_id"])
            concept_title = entry["flavor_name"]
            embed = discord.Embed(
                title=concept_title,
                description=f"submitted by {author.mention if author else entry['author_id']}",
                color=discord.Color.blurple(),
            )
            embed.set_image(url=entry["url"])
            message = await contest_channel.send(embed=embed)
            await message.add_reaction("\u2B06\uFE0F")
            await cm.record_released_design(
                interaction.guild_id,
                {
                    "author_id": entry["author_id"],
                    "flavor_name": entry["flavor_name"],
                    "url": entry["url"],
                    "message_id": message.id,
                    "channel_id": contest_channel.id,
                },
            )
        await interaction.response.send_message("Designs released!", ephemeral=True)

    @app_commands.command(name="endcontest", description="End the current contest early and announce a winner.")
    async def endcontest(self, interaction: discord.Interaction):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Missing permissions.", ephemeral=True)
            return
        contest = await cm.load_contest(interaction.guild_id)
        if not contest["active"]:
            await interaction.response.send_message("No active contest to end.", ephemeral=True)
            return
        win_channel = await self._get_win_channel()
        contest_channel = await self._get_channel(contest.get("channel_id"))
        designs = await cm.get_released_designs(interaction.guild_id)
        if not designs:
            await interaction.response.send_message("No released designs to score.", ephemeral=True)
            return
        top_entry = None
        top_votes = -1
        for design in designs:
            if not design.get("message_id") or not design.get("channel_id"):
                continue
            votes = await self._count_design_votes(design)
            if votes > top_votes:
                top_entry = design
                top_votes = votes
        if top_entry is None:
            await interaction.response.send_message("No released designs have vote data yet.", ephemeral=True)
            return
        if top_entry:
            winner_member = interaction.guild.get_member(top_entry["author_id"])
            win_embed = discord.Embed(
                title=f"Contest Winner: {top_entry['flavor_name']}",
                description=contest.get("announcement_message") or "contest results",
                color=discord.Color.gold(),
            )
            win_embed.add_field(name="Votes", value=str(max(top_votes, 0)))
            if winner_member:
                win_embed.add_field(name="Submitted By", value=winner_member.mention)
            win_embed.set_image(url=top_entry["url"])
            destinations = []
            if win_channel:
                destinations.append(win_channel)
            if contest_channel and contest_channel not in destinations:
                destinations.append(contest_channel)
            if not destinations:
                await interaction.response.send_message(
                    "Could not announce winner: no destination channel configured.",
                    ephemeral=True,
                )
                return
            for channel in destinations:
                await channel.send(embed=win_embed)
        grace_until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        await cm.mark_contest_finished(interaction.guild_id, grace_until)
        if contest_channel:
            await contest_channel.send("Contest ended. This channel will archive in ~24 hours.")
        await interaction.response.send_message("Contest ended and winner announced.", ephemeral=True)

    @app_commands.command(name="contestarchive", description="Manually archive the current contest channel.")
    async def contestarchive(self, interaction: discord.Interaction):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Missing permissions.", ephemeral=True)
            return
        contest = await cm.load_contest(interaction.guild_id)
        channel = await self._get_channel(contest.get("channel_id"))
        if not channel:
            await interaction.response.send_message("Contest channel not configured.", ephemeral=True)
            return
        archived = await self._archive_channel(interaction.guild, channel, contest)
        await cm.end_contest(interaction.guild_id)
        if archived:
            await interaction.response.send_message("Contest channel archived.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to archive channel.", ephemeral=True)

    async def _count_design_votes(self, design_entry):
        # fetch arrow-up reactions for released design messages
        channel_id = design_entry.get("channel_id") or CONTEST_DESIGN_CHANNEL_ID
        message_id = design_entry.get("message_id")
        if not channel_id or not message_id:
            return 0
        channel = await self._get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return 0
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return 0
        for reaction in message.reactions:
            if str(reaction.emoji) == "\u2B06\uFE0F":
                return reaction.count
        return 0

    @tasks.loop(minutes=2)
    async def _archive_task(self):
        # background loop watches contest end dates and archives when expired
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            contest = await cm.load_contest(guild.id)
            if not await cm.needs_archive(contest):
                continue
            channel_id = contest.get("channel_id")
            channel = guild.get_channel(channel_id) if channel_id else None
            await self._archive_channel(guild, channel, contest)
            await cm.end_contest(guild.id)

    @_archive_task.before_loop
    async def before_archive(self):
        # ensure bot ready before loop tries to touch guilds
        await self.bot.wait_until_ready()

    async def _archive_channel(self, guild: discord.Guild, channel: Optional[discord.TextChannel], contest: dict):
        archive_category = guild.get_channel(cm.CONTEST_CATEGORY_ARCHIVE)
        new_name = f"contest-{contest.get('round', 1)}"
        if channel and isinstance(channel, discord.TextChannel):
            try:
                await channel.edit(name=new_name, category=archive_category)
                return True
            except discord.HTTPException:
                return False
        return False


async def setup(bot):
    await bot.add_cog(Contest(bot))
