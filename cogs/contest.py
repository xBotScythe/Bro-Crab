import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import contest_manager as cm
from utils.admin_manager import check_admin_status

CONTEST_REVIEW_CHANNEL_ID = int(os.getenv("CONTEST_REVIEW_CHANNEL_ID", "0") or 0)
CONTEST_DESIGN_CHANNEL_ID = int(os.getenv("CONTEST_DESIGN_CHANNEL_ID", "0") or 0)
CONTEST_WIN_CHANNEL_ID = int(os.getenv("CONTEST_WIN_CHANNEL_ID", "0") or 0)
# contest cog: handles idea submissions, votes, and design releases


class IdeaReviewView(discord.ui.View):
    # small approval ui that insert mods click accept/deny
    def __init__(self, cog, guild_id, submitter_id, idea_name):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.submitter_id = submitter_id
        self.idea_name = idea_name

    async def interaction_check(self, interaction: discord.Interaction):
        # only admins can approve/deny contest ideas
        if not await check_admin_status(self.cog.bot, interaction):
            await interaction.response.send_message("You can't moderate contests.", ephemeral=True)
            return False
        return True

    async def _finalize(self, interaction, text):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=text, view=self)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, _button: discord.ui.Button):
        contest = await cm.load_contest(self.guild_id)
        try:
            await cm.add_idea(self.guild_id, self.idea_name, self.submitter_id, contest["active"])
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._finalize(interaction, f"Accepted idea '{self.idea_name}'.")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._finalize(interaction, f"Denied idea '{self.idea_name}'.")


class Contest(commands.Cog):
    # contest cog: lets users submit ideas, admins moderate, background archiving
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

    @app_commands.command(name="submitidea", description="Submit a flavor idea for the current contest.")
    async def submitidea(self, interaction: discord.Interaction, idea: str):
        # users submit an idea; mods review via buttons in review channel
        if interaction.guild is None:
            await interaction.response.send_message("Guild only command.", ephemeral=True)
            return
        review_channel = await self._get_channel(CONTEST_REVIEW_CHANNEL_ID)
        if review_channel is None:
            await interaction.response.send_message("Review channel not configured.", ephemeral=True)
            return

        contest = await cm.load_contest(interaction.guild_id)
        view = IdeaReviewView(self, interaction.guild_id, interaction.user.id, idea)
        embed = discord.Embed(title="Contest Idea", description=idea, color=discord.Color.yellow())
        embed.add_field(name="Submitted By", value=interaction.user.mention)
        embed.add_field(name="Contest Active", value="yes" if contest["active"] else "no")
        await review_channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            "idea submitted for review." + (" contests currently inactive, will be queued." if not contest["active"] else ""),
            ephemeral=True,
        )

    @app_commands.command(name="voteidea", description="Vote for a contest idea.")
    @app_commands.describe(idea="Choose from active ideas")
    async def voteidea(self, interaction: discord.Interaction, idea: str):
        # users vote for active ideas, scoped to contest state
        if interaction.guild is None:
            await interaction.response.send_message("Guild only command.", ephemeral=True)
            return
        try:
            result = await cm.vote_for_idea(interaction.guild_id, idea, interaction.user.id)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message(
            f"You voted for **{result['name']}**. ({result['votes']} total)",
            ephemeral=True,
        )

    @voteidea.autocomplete("idea")
    async def voteidea_autocomplete(self, interaction: discord.Interaction, current: str):
        if interaction.guild is None:
            return []
        ideas = await cm.list_active_ideas(interaction.guild_id)
        matches = [idea for idea in ideas if current.lower() in idea["name"].lower()]
        return [app_commands.Choice(name=idea["name"], value=idea["name"]) for idea in matches[:25]]

    @app_commands.command(name="dewsignsubmit", description="Submit a design for the current contest.")
    async def dewsignsubmit(self, interaction: discord.Interaction, image: discord.Attachment):
        # design submitter uploads an image; queued for release later
        if interaction.guild is None:
            await interaction.response.send_message("Guild only command.", ephemeral=True)
            return
        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message("Please upload an image file.", ephemeral=True)
            return
        try:
            await cm.add_design_submission(interaction.guild_id, interaction.user.id, image.url)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message("Design submitted!", ephemeral=True)

    @app_commands.command(name="startcontest", description="Start a contest with a message and end date.")
    @app_commands.describe(
        message="announcement / flavor concept",
        end_date="ISO timestamp (YYYY-MM-DD or full) — defaults to 4 days from now",
    )
    async def startcontest(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel, end_date: Optional[str] = None):
        # admin starts a contest window and moves queued ideas live
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
        await cm.move_queued_ideas(interaction.guild_id)
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
        design_channel = await self._get_channel(CONTEST_DESIGN_CHANNEL_ID)
        if design_channel is None:
            await interaction.response.send_message("Design showcase channel not configured.", ephemeral=True)
            return
        contest = await cm.load_contest(interaction.guild_id)
        queue = await cm.get_design_queue(interaction.guild_id)
        if not queue:
            await interaction.response.send_message("No designs to release.", ephemeral=True)
            return
        queue = await cm.clear_design_queue(interaction.guild_id)
        for entry in queue:
            author = interaction.guild.get_member(entry["author_id"])
            concept_title = contest.get("announcement_message") or "Contest Design"
            embed = discord.Embed(
                title=concept_title,
                description=f"Submitted by {author.mention if author else entry['author_id']}",
                color=discord.Color.blurple(),
            )
            embed.set_image(url=entry["url"])
            message = await design_channel.send(embed=embed)
            await message.add_reaction("\u2B06\uFE0F")
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
        top_idea = await cm.get_top_idea(interaction.guild_id)
        win_channel = await self._get_win_channel()
        contest_channel = await self._get_channel(contest.get("channel_id"))
        if top_idea and win_channel:
            winner_member = interaction.guild.get_member(top_idea["submitted_by"])
            win_embed = discord.Embed(
                title="Contest Winner",
                description=contest.get("announcement_message") or "Contest Results",
                color=discord.Color.gold(),
            )
            win_embed.add_field(name="Winning Idea", value=top_idea["name"], inline=False)
            win_embed.add_field(name="Votes", value=str(top_idea.get("votes", 0)))
            if winner_member:
                win_embed.add_field(name="Submitted By", value=winner_member.mention)
            await win_channel.send(embed=win_embed)
        grace_until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        await cm.mark_contest_finished(interaction.guild_id, grace_until)
        if contest_channel:
            await contest_channel.send("Contest ended. This channel will archive in ~24 hours.")
        await interaction.response.send_message("Contest ended and winner announced.", ephemeral=True)

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
            archive_category = guild.get_channel(cm.CONTEST_CATEGORY_ARCHIVE)
            new_name = f"contest-{contest.get('round', 1)}"
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    await channel.edit(name=new_name, category=archive_category)
                except discord.HTTPException:
                    pass
            await cm.end_contest(guild.id)

    @_archive_task.before_loop
    async def before_archive(self):
        # ensure bot ready before loop tries to touch guilds
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Contest(bot))
