import re

import discord
from discord import app_commands
from discord.ext import commands

from utils.booster_manager import check_boost_status
from utils.json_manager import load_json_async, write_json_async

SERVER_FILE = "data/server_data.json"

class Dewluxe(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _parse_color(self, raw: str) -> discord.Color:
        value = raw.strip()
        hex_match = re.fullmatch(r"#?(?P<hex>[0-9a-fA-F]{6})", value)
        if hex_match:
            return discord.Color(int(hex_match.group("hex"), 16))
        try:
            color_name = value.replace(" ", "_").lower()
            return getattr(discord.Color, color_name)()
        except (AttributeError, TypeError):
            raise ValueError("invalid color. use hex (#ff00ff) or a discord color name.")

    async def _store_role(self, guild_id: int, user_id: int, role: discord.Role, color_str: str):
        data = await load_json_async(SERVER_FILE)
        guild_entry = data.setdefault(str(guild_id), {})
        boost_roles = guild_entry.setdefault("boost_roles", [])
        boost_roles.append(
            {
                "role_id": role.id,
                "role_name": role.name,
                "color": color_str,
                "user_id": user_id,
            }
        )
        guild_entry["boost_roles"] = boost_roles
        await write_json_async(data, SERVER_FILE)

    @app_commands.command(name="dewluxe", description="Create a personal booster role with a custom name and color.")
    @app_commands.describe(role_name="Name for your role", color="Hex or Discord color name")
    async def dewluxe(self, interaction: discord.Interaction, role_name: str, color: str):
        if not await check_boost_status(self.bot, interaction):
            await interaction.response.send_message(
                "sorry bro, you're not cool enough to use this. have you tried boosting?",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            parsed_color = await self._parse_color(color)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        name = role_name.strip()
        if not name or len(name) > 100:
            await interaction.followup.send("role name must be between 1 and 100 characters.", ephemeral=True)
            return

        existing = discord.utils.get(interaction.guild.roles, name=name)
        if existing:
            await interaction.followup.send("a role with that name already exists.", ephemeral=True)
            return

        try:
            role = await interaction.guild.create_role(
                name=name,
                color=parsed_color,
                reason=f"dewluxe role for {interaction.user}",
                mentionable=True,
            )
            await interaction.user.add_roles(role, reason="dewluxe role assignment")
        except discord.HTTPException as exc:
            await interaction.followup.send(f"failed to create or assign role: {exc}", ephemeral=True)
            return

        await self._store_role(interaction.guild_id, interaction.user.id, role, color)
        await interaction.followup.send(f"created {role.mention} and assigned it to you!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Dewluxe(bot))
