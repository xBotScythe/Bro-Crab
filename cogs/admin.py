import os
from typing import Literal, List, Optional, Dict, Any
from datetime import datetime, timezone

ARCHIVE_CATEGORY_NAME = "Lightning Archives"
MAIN_CATEGORY_NAME = "Mountain Lightning"
NEW_CHANNEL_NAME = "lightning-general"

import discord
from discord import app_commands
from discord.ext import commands

from utils.admin_manager import check_admin_status
from utils.json_manager import load_json_async, write_json_async

USER_DATA_FILE = "data/user_data.json"
SERVER_DATA_FILE = "data/server_data.json"
DEFAULT_ARCHIVE_START = 168


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        boomer_role_id = os.getenv("BOOMER_ROLE_ID")
        self.boomer_role_id = int(boomer_role_id) if boomer_role_id and boomer_role_id.isdigit() else None
        warn_channel_id = os.getenv("WARN_LOG_CHANNEL_ID")
        self.warn_channel_id = int(warn_channel_id) if warn_channel_id and warn_channel_id.isdigit() else None

    async def _store_roles(self, guild_id: int, user_id: int, role_ids: List[int]):
        # track removed roles for future restore
        data = await load_json_async(USER_DATA_FILE)
        guild_entry = data.setdefault(str(guild_id), {})
        user_entry = guild_entry.setdefault(str(user_id), {})
        user_entry["boomer_roles"] = {
            "roles": role_ids,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await write_json_async(data, USER_DATA_FILE)

    async def _pop_stored_roles(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        data = await load_json_async(USER_DATA_FILE)
        guild_entry = data.get(str(guild_id), {})
        user_entry = guild_entry.get(str(user_id), {})
        stored = user_entry.pop("boomer_roles", None)
        if stored is None:
            return None
        if not user_entry:
            guild_entry.pop(str(user_id), None)
        if not guild_entry:
            data.pop(str(guild_id), None)
        await write_json_async(data, USER_DATA_FILE)
        return stored

    def _get_category(self, guild: discord.Guild, name: str) -> Optional[discord.CategoryChannel]:
        # find category regardless of case
        lowered = name.lower()
        for category in guild.categories:
            if category.name.lower() == lowered:
                return category
        return None

    async def _archive_current_channel(self, interaction: discord.Interaction):
        # rename, move to archive, and spawn fresh lightning-general
        channel = interaction.channel
        guild = interaction.guild
        if channel is None or guild is None:
            return
        server_data = await load_json_async(SERVER_DATA_FILE)
        guild_entry = server_data.setdefault(str(interaction.guild_id), {})
        archive_state = guild_entry.setdefault("lightning_archive", {})
        next_number = archive_state.get("next_number", DEFAULT_ARCHIVE_START)
        new_name = f"lightning-archive-{next_number}"

        try:
            if isinstance(channel, discord.Thread):
                await channel.edit(name=new_name, archived=True, locked=True)
            elif isinstance(channel, discord.TextChannel):
                await channel.edit(name=new_name, reason="boomer archive rotate")
        except discord.HTTPException as exc:
            await interaction.followup.send(f"Archive rename failed: {exc}", ephemeral=True)
            return

        if isinstance(channel, discord.TextChannel):
            archive_category = self._get_category(guild, ARCHIVE_CATEGORY_NAME)
            if archive_category:
                try:
                    await channel.edit(category=archive_category, reason="boomer archive relocate")
                except discord.HTTPException:
                    pass

        mountain_category = self._get_category(guild, MAIN_CATEGORY_NAME)
        existing_new = discord.utils.get(guild.text_channels, name=NEW_CHANNEL_NAME)
        if existing_new is None:
            kwargs = {"name": NEW_CHANNEL_NAME, "reason": "boomer archive restart"}
            if mountain_category:
                kwargs["category"] = mountain_category
            try:
                await guild.create_text_channel(**kwargs)
            except discord.HTTPException as exc:
                await interaction.followup.send(f"Could not create #{NEW_CHANNEL_NAME}: {exc}", ephemeral=True)
                return

        archive_state["next_number"] = next_number + 1
        guild_entry["lightning_archive"] = archive_state
        await write_json_async(server_data, SERVER_DATA_FILE)

    async def _get_warn_channel(self) -> Optional[discord.TextChannel]:
        # resolve cross-server warn log channel
        if not self.warn_channel_id:
            return None
        channel = self.bot.get_channel(self.warn_channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            return channel
        try:
            fetched = await self.bot.fetch_channel(self.warn_channel_id)
            return fetched if isinstance(fetched, discord.TextChannel) else None
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    @app_commands.command(name="boomer", description="Start or end the boomer workflow for a member.")
    @app_commands.describe(
        user="Member to act on.",
        action="Choose 'start' to strip roles, 'end' to restore them."
    )
    async def boomer(self, interaction: discord.Interaction, user: discord.Member, action: Literal["start", "end"]):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message(
                "Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?",
                ephemeral=True,
            )
            return
        if self.boomer_role_id is None:
            await interaction.response.send_message(
                "BOOMER_ROLE_ID is not configured on the bot. Please set it in the environment.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        if action == "start":
            await self._handle_boomer_start(interaction, user)
        else:
            await self._handle_boomer_end(interaction, user)

    async def _handle_boomer_start(self, interaction: discord.Interaction, member: discord.Member):
        guild = interaction.guild
        boomer_role = guild.get_role(self.boomer_role_id) if guild else None
        if not boomer_role:
            await interaction.followup.send("Boomer role not found in this guild.", ephemeral=True)
            return

        removable_roles = [
            role for role in member.roles
            if not role.is_default() and role < guild.me.top_role and role.id != boomer_role.id
        ]
        if removable_roles:
            try:
                await member.remove_roles(*removable_roles, reason=f"Boomer start triggered by {interaction.user}")
            except discord.HTTPException as exc:
                await interaction.followup.send(f"Failed to remove roles: {exc}", ephemeral=True)
                return

        try:
            await member.add_roles(boomer_role, reason="Boomer start role assignment")
        except discord.HTTPException as exc:
            await interaction.followup.send(f"Failed to assign boomer role: {exc}", ephemeral=True)
            return

        await self._store_roles(guild.id, member.id, [r.id for r in removable_roles])
        msg = f"Assigned {boomer_role.mention} to {member.mention}."
        if removable_roles:
            msg = f"Stored {len(removable_roles)} roles and " + msg
        await interaction.followup.send(msg, ephemeral=True)

    async def _handle_boomer_end(self, interaction: discord.Interaction, member: discord.Member):
        guild = interaction.guild
        boomer_role = guild.get_role(self.boomer_role_id) if guild else None

        stored_payload = await self._pop_stored_roles(guild.id, member.id)
        if stored_payload is None:
            await interaction.followup.send("No stored roles found for that member.", ephemeral=True)
            return
        stored_role_ids = stored_payload.get("roles", [])

        roles_to_add = []
        missing = []
        for role_id in stored_role_ids:
            role = guild.get_role(role_id)
            if role and role < guild.me.top_role:
                roles_to_add.append(role)
            else:
                missing.append(role_id)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason=f"Boomer end triggered by {interaction.user}")
            except discord.HTTPException as exc:
                await interaction.followup.send(f"Failed to restore roles: {exc}", ephemeral=True)
                return

        if boomer_role in member.roles:
            try:
                await member.remove_roles(boomer_role, reason="Boomer workflow complete")
            except discord.HTTPException:
                pass

        await self._archive_current_channel(interaction)
        summary = f"Restored {len(roles_to_add)} roles to {member.mention}."
        if missing:
            summary += f" {len(missing)} roles were missing or higher than me and could not be restored."
        await interaction.followup.send(summary, ephemeral=True)

    @app_commands.command(name="warn", description="Send a DM warning and log it.")
    @app_commands.describe(user="member to warn", reason="short explanation for the warning")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message(
                "Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)

        timestamp = datetime.now(timezone.utc)
        embed = discord.Embed(
            title="You have been warned",
            description=reason,
            color=discord.Color.orange(),
            timestamp=timestamp,
        )
        embed.add_field(name="Server", value=interaction.guild.name if interaction.guild else "Unknown", inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)

        dm_sent = True
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            dm_sent = False

        log_channel = await self._get_warn_channel()
        if log_channel:
            log_embed = discord.Embed(
                title="Warning Issued",
                color=discord.Color.orange(),
                timestamp=timestamp,
                description=f"{user.mention} warned by {interaction.user.mention}",
            )
            log_embed.add_field(name="Reason", value=reason, inline=False)
            if interaction.guild:
                log_embed.add_field(name="Origin Server", value=f"{interaction.guild.name} (`{interaction.guild.id}`)", inline=False)
            log_embed.add_field(name="DM Sent", value="yes" if dm_sent else "no", inline=False)
            try:
                await log_channel.send(embed=log_embed)
            except discord.HTTPException:
                pass

        feedback = f"Warned {user.mention}."
        if not dm_sent:
            feedback += " DM could not be delivered."
        await interaction.followup.send(feedback, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
