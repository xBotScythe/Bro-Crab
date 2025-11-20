import os
from datetime import datetime

import discord

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0") or 0)
BOT_SELF_ROLE_ID = int(os.getenv("BOT_SELF_ROLE_ID", "0") or 0)


async def handle_member_join(bot: discord.Client, member: discord.Member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(WELCOME_CHANNEL_ID)
        except Exception:
            return

    status_text = "No custom status has been set."
    presence = member.activity
    if isinstance(presence, discord.CustomActivity) and presence.name:
        status_text = presence.name

    embed = discord.Embed(
        title=f"New Member in Dew Drinker Discord: {member.display_name}.",
        description=f"<@{member.id}> : {status_text}\nUser ID: {member.id}",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="Joined server at:",
        value=member.joined_at.strftime("%A, %B %d, %Y at %I:%M %p") if member.joined_at else "unknown",
        inline=False,
    )
    embed.add_field(
        name="Account created at:",
        value=member.created_at.strftime("%A, %B %d, %Y at %I:%M %p"),
        inline=False,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=datetime.utcnow().strftime("%m/%d/%y, %I:%M %p"))

    await channel.send(embed=embed)


# kick users who grab the "i am a bot" role
async def enforce_bot_flag(before: discord.Member, after: discord.Member):
    if not BOT_SELF_ROLE_ID:
        return
    before_roles = {role.id for role in before.roles}
    after_roles = {role.id for role in after.roles}
    if BOT_SELF_ROLE_ID in before_roles:
        return
    if BOT_SELF_ROLE_ID not in after_roles:
        return
    try:
        await after.kick(reason="Selected bot self-identify role")
    except discord.HTTPException:
        pass
