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
        self.default_boomer_role = 650210167950147585

    async def _store_roles(self, guild_id: int, user_id: int, role_ids: List[int], channel_id: Optional[int] = None):
        # track removed roles for future restore
        data = await load_json_async(USER_DATA_FILE)
        guild_entry = data.setdefault(str(guild_id), {})
        user_entry = guild_entry.setdefault(str(user_id), {})
        user_entry["boomer_roles"] = {
            "roles": role_ids,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel_id": channel_id,
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

    async def _pop_stored_roles_by_channel(self, guild_id: int, channel_id: Optional[int], allow_any: bool = False):
        data = await load_json_async(USER_DATA_FILE)
        guild_entry = data.get(str(guild_id), {})
        candidates = []
        for user_id, info in list(guild_entry.items()):
            stored = info.get("boomer_roles")
            if not stored:
                continue
            entry_channel = stored.get("channel_id")
            if channel_id is not None and entry_channel == channel_id:
                info.pop("boomer_roles", None)
                if not info:
                    guild_entry.pop(user_id, None)
                if not guild_entry:
                    data.pop(str(guild_id), None)
                await write_json_async(data, USER_DATA_FILE)
                return stored, int(user_id)
            candidates.append((user_id, stored))
        if allow_any and candidates:
            user_id, stored = candidates[0]
            info = guild_entry.get(user_id, {})
            info.pop("boomer_roles", None)
            if not info:
                guild_entry.pop(user_id, None)
            if not guild_entry:
                data.pop(str(guild_id), None)
            await write_json_async(data, USER_DATA_FILE)
            return stored, int(user_id)
        return None, None

    def _get_category(self, guild: discord.Guild, name: str) -> Optional[discord.CategoryChannel]:
        # find category regardless of case
        lowered = name.lower()
        for category in guild.categories:
            if category.name.lower() == lowered:
                return category
        return None

    async def _archive_current_channel(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.channel:
            return
        success, message = await self._archive_channel_logic(interaction.guild, interaction.channel)
        if not success and message:
            await interaction.followup.send(message, ephemeral=True)

    async def _archive_channel_by_id(self, guild: discord.Guild, channel_id: Optional[int]):
        if guild is None:
            return
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel is None:
            channel = discord.utils.get(guild.text_channels, name=NEW_CHANNEL_NAME)
        await self._archive_channel_logic(guild, channel)

    async def _archive_channel_logic(self, guild: discord.Guild, channel: Optional[discord.abc.GuildChannel]):
        if guild is None or channel is None:
            return False, "Unable to archive channel: missing reference."
        server_data = await load_json_async(SERVER_DATA_FILE)
        guild_entry = server_data.setdefault(str(guild.id), {})
        archive_state = guild_entry.setdefault("lightning_archive", {})
        next_number = archive_state.get("next_number", DEFAULT_ARCHIVE_START)
        new_name = f"lightning-archive-{next_number}"

        try:
            if isinstance(channel, discord.Thread):
                await channel.edit(name=new_name, archived=True, locked=True)
            elif isinstance(channel, discord.TextChannel):
                await channel.edit(name=new_name, reason="boomer archive rotate")
        except discord.HTTPException as exc:
            return False, f"Archive rename failed: {exc}"

        if isinstance(channel, discord.TextChannel):
            archive_category = self._get_category(guild, ARCHIVE_CATEGORY_NAME)
            overwrites = channel.overwrites
            boomer_role_id = self.boomer_role_id or self.default_boomer_role
            boomer_role = guild.get_role(boomer_role_id)
            if boomer_role:
                overwrites = dict(overwrites)
                perms = overwrites.get(boomer_role, discord.PermissionOverwrite())
                perms.view_channel = False
                overwrites[boomer_role] = perms
            if archive_category:
                try:
                    await channel.edit(
                        category=archive_category,
                        overwrites=overwrites,
                        reason="boomer archive relocate",
                    )
                except discord.HTTPException:
                    pass
            else:
                try:
                    await channel.edit(overwrites=overwrites, reason="boomer archive lockout")
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
                return False, f"Could not create #{NEW_CHANNEL_NAME}: {exc}"

        archive_state["next_number"] = next_number + 1
        guild_entry["lightning_archive"] = archive_state
        await write_json_async(server_data, SERVER_DATA_FILE)
        return True, None

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

    @app_commands.command(name="boomer", description="Start or end the boomer process for a member.")
    @app_commands.describe(
        action="Choose 'start' to strip roles, 'end' to restore them.",
        user="Member to act on (optional when ending).",
        channel="Channel to archive if the member is gone."
    )
    async def boomer(
        self,
        interaction: discord.Interaction,
        action: Literal["start", "end"],
        user: Optional[discord.Member] = None,
        channel: Optional[discord.TextChannel] = None,
    ):
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
            await self._handle_boomer_end(interaction, user, channel)

    @app_commands.command(name="addautoboomer", description="Automatically boomer a member whenever they join.")
    async def addautoboomer(self, interaction: discord.Interaction, member: discord.Member):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message(
                "Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        data = await load_json_async(SERVER_DATA_FILE)
        guild_entry = data.setdefault(str(interaction.guild_id), {})
        auto_list = guild_entry.setdefault("auto_boomer_ids", [])
        if member.id in auto_list:
            await interaction.followup.send(f"{member.display_name} is already auto-boomered.", ephemeral=True)
            return
        auto_list.append(member.id)
        await write_json_async(data, SERVER_DATA_FILE)
        await interaction.followup.send(f"{member.mention} will now be automatically boomered on join.", ephemeral=True)

    async def _perform_boomer_start(
        self,
        guild: Optional[discord.Guild],
        member: Optional[discord.Member],
        actor: Optional[discord.abc.User],
        channel_id: Optional[int],
    ):
        if guild is None or member is None:
            return False, "Missing guild or member."
        bot_member = guild.me
        if bot_member is None:
            return False, "Bot member missing in guild."
        boomer_role_id = self.boomer_role_id or self.default_boomer_role
        boomer_role = guild.get_role(boomer_role_id)
        if not boomer_role:
            return False, "Boomer role not found in this guild."

        removable_roles = [
            role for role in member.roles
            if not role.is_default() and role < bot_member.top_role and role.id != boomer_role.id
        ]
        if removable_roles:
            try:
                await member.remove_roles(*removable_roles, reason=f"Boomer start triggered by {actor or guild.me}")
            except discord.HTTPException as exc:
                return False, f"Failed to remove roles: {exc}"

        try:
            await member.add_roles(boomer_role, reason="Boomer start role assignment")
        except discord.HTTPException as exc:
            return False, f"Failed to assign boomer role: {exc}"

        await self._store_roles(guild.id, member.id, [r.id for r in removable_roles], channel_id=channel_id)
        msg = f"Assigned {boomer_role.mention} to {member.mention}."
        if removable_roles:
            msg = f"Stored {len(removable_roles)} roles and " + msg
        return True, msg

    async def _handle_boomer_start(self, interaction: discord.Interaction, member: Optional[discord.Member]):
        if member is None:
            await interaction.followup.send("Provide a member to start the boomer process.", ephemeral=True)
            return
        success, message = await self._perform_boomer_start(
            interaction.guild, member, interaction.user, interaction.channel.id if interaction.channel else None
        )
        if not success:
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.followup.send(message, ephemeral=True)

    async def _handle_boomer_end(self, interaction: discord.Interaction, member: Optional[discord.Member], channel: Optional[discord.TextChannel] = None):
        guild = interaction.guild
        boomer_role_id = self.boomer_role_id or self.default_boomer_role
        boomer_role = guild.get_role(boomer_role_id) if guild else None

        member_id = member.id if member else None
        stored_payload = None
        resolved_user_id = member_id
        if guild is None:
            await interaction.followup.send("Unable to resolve guild for boomer end.", ephemeral=True)
            return

        if member_id is not None:
            stored_payload = await self._pop_stored_roles(guild.id, member_id)
        else:
            resolved_channel_id = channel.id if channel else (interaction.channel.id if interaction.channel else None)
            stored_payload, resolved_user_id = await self._pop_stored_roles_by_channel(
                guild.id, resolved_channel_id, allow_any=True
            )

        if stored_payload is None:
            guidance = "Provide a member or channel for the boomer session you're trying to end."
            await interaction.followup.send(f"No stored roles found for that member. {guidance}", ephemeral=True)
            return
        stored_role_ids = stored_payload.get("roles", [])
        channel_id = stored_payload.get("channel_id")

        if member:
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

            if boomer_role and boomer_role in member.roles:
                try:
                    await member.remove_roles(boomer_role, reason="Boomer workflow complete")
                except discord.HTTPException:
                    pass

            summary = f"Restored {len(roles_to_add)} roles to {member.mention}."
            if missing:
                summary += f" {len(missing)} roles were missing or higher than me and could not be restored."
        else:
            target = f"<@{resolved_user_id}>" if resolved_user_id else "the recorded member"
            summary = f"No member supplied; skipped role restoration for {target}."

        archive_target = channel_id or (channel.id if channel else None) or (interaction.channel.id if interaction.channel else None)
        await self._archive_channel_by_id(guild, archive_target)
        await interaction.followup.send(summary, ephemeral=True)

    async def _auto_end_boomer(self, guild: discord.Guild, user_id: int, reason: str):
        if guild is None:
            return
        stored_payload = await self._pop_stored_roles(guild.id, user_id)
        if stored_payload is None:
            return
        channel_id = stored_payload.get("channel_id")
        await self._archive_channel_by_id(guild, channel_id)
        warn_channel = await self._get_warn_channel()
        if warn_channel:
            await warn_channel.send(f"Boomer workflow auto-ended for <@{user_id}> ({reason}).")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._auto_end_boomer(member.guild, member.id, "member left the server")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        await self._auto_end_boomer(guild, user.id, "member was banned")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = await load_json_async(SERVER_DATA_FILE)
        guild_entry = data.get(str(member.guild.id), {})
        auto_ids = guild_entry.get("auto_boomer_ids", [])
        if member.id not in auto_ids:
            return
        success, message = await self._perform_boomer_start(member.guild, member, self.bot.user, None)
        if not success:
            warn_channel = await self._get_warn_channel()
            if warn_channel:
                await warn_channel.send(f"Failed auto-boomer for {member.mention}: {message}")

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
