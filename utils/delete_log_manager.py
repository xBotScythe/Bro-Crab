import os

import aiohttp
import discord

DELETE_LOG_CHANNEL_ID = os.getenv("DELETE_LOG_CHANNEL_ID")
LLM_ENDPOINT = os.getenv("LLM_REVIEW_ENDPOINT", "http://100.66.147.4:1234/v1/chat/completions")

SERVER_RULES = """
General Rules
(1/3)
1) Don't Be an Ass. Generally, this should be self-explanatory: treat others and their opinions with basic respect at a minimum, and if an argument arises, please be reasonable and respectful to one another. Gratuitously confrontational and vilifying attacks are particularly prone to administrative action.

2) Spam and Unacceptable Content. Spam and similarly vexing content are not tolerated. Such content includes, but is not limited to: unintelligible messages, GIF spam, repetition, and excessively annoying behavior. Please refer to the Spam Rules below for more information regarding our spam and unacceptable content guidelines.
(2/3)
3) Bigotry is Not Tolerated. Racist, sexist, homophobic, or otherwise bigoted and hateful content is strictly not allowed in this server. Slurs, or the encouraged usage thereof, under any context at all whatsoever, will result in a permanent ban. Blatant references to a slur or hate speech are also actionable.

Additionally, intentionally disregarding other users' pronouns or gender identity is unacceptable: we have specially colored pronoun roles available for a reason. To avoid being called out for, as an example, referring to a woman as a man, please take the time to check someone's roles to make sure they're a he, she, or they. If a user's pronouns are not expressed, anything is fair game.
(3/3)
4) Don't Get Too Political. Controversial political statements and discussions are not allowed on this server. Such content is not allowed on profiles at all here: a moderator may ask you to edit certain parts of your profile accordingly if you are found to be in violation of this rule. The Mountain Dew server is not the place for politics, it's for Mountain Dew. Enforcement of this rule is at the sole discretion of staff.

5) Don't Spread Misinformation. This server prides itself on being a source of early and accurate MTN DEW leaks. Implying blatantly false information and rumors as fact can and will result in administrative action. If you're citing a rumor or anything that is not documented in dew-news or otherwise widely known, please make the unsteady nature of the information clear.
Spam Rules
(1/2)
Spam can take several forms, and each one serves as another distraction to our members. We ask of you to not be a nuisance to the server or its users, as it should be open for everyone to converse within the bounds of the rules, channel topics, and basic respect for others. These guidelines will help give you a general idea of actions and mannerisms to avoid.

A) Repetition: If you're saying the same thing over and over and people are clearly annoyed with it, please cut it out. If there's minimal new content being added each time you repeat yourself for the sole purpose of annoying people, administrative action can and will be taken. Do not repeat yourself in a way that's annoying to others and contributes nothing of substance.
(2/2)
B) Intruding on a Conversation: When people are actively having a conversation, don't interrupt them -- for example, by bringing up a completely different topic or posting an off-topic image while people are still typing. That's straight-up rude. Do not post content that is not contextual to a conversation or channel. Discord conversations work in strange ways -- we know it well -- but please use proper discretion and be considerate of others. For more information, check out the Channel Misuse guideline below.

C) General Spam: "Spam" includes stuff like copypastas, incoherent babble, sending excessive images/links/GIFs in a short period of time, reacting to messages excessively and with no context, and what we describe as "intrusive content." Intrusive content most often manifests in the form of multiple instances of annoying, meaningless junk sent with the express intent to shitpost where it is not appropriate. Intrusive content may be removed and actioned at the discretion of staff.
Miscellaneous Guidelines
Welcome to Dew Drinker Discord!
Once you have introduced yourself, you will be granted access to the rest of the server and assigned a flavor role based on the flavor you named in your introduction. You may select additional roles or change your flavor role in change-your-flavor. For the latest and greatest MTN DEW leaks, upcoming releases, and more DEW-related information, check out our Dew Resources category! We have a wide variety of discussion channels here relating to Dew and Not Dew, be sure to check them out and contribute if you'd like!
Contact the Staff Team
If you'd like to submit a report, suggestion, or question to our team, please DM @unknown-role at the top of the right sidebar to activate Crabmail, which will let you forward your concerns to the right people on our staff team. We will discuss the situation with you and handle the situation as best we can.
"""


async def log_deleted_message(bot, message):
    # always log right away so we don't block
    if message.guild is None or message.author.bot:
        return
    channel = await _resolve_log_channel(bot)
    if channel is None:
        return

    embed = discord.Embed(
        title="Message Deleted",
        color=discord.Color.red(),
        description=message.content or "*no content*",
    )
    embed.add_field(name="Author", value=f"{message.author} (`{message.author.id}`)", inline=False)
    embed.add_field(name="Channel", value=f"{message.channel.mention} (`{message.channel.id}`)", inline=False)
    embed.add_field(name="Message ID", value=str(message.id), inline=False)
    if message.attachments:
        attachment_lines = "\n".join(att.url for att in message.attachments)
        embed.add_field(name="Attachments", value=attachment_lines[:1024], inline=False)

    sent_message = await channel.send(embed=embed)

    deleter = await _infer_deleter(message)
    if not deleter or deleter.id == message.author.id:
        return

    warn_result = await _review_with_llm(message)
    if not warn_result:
        return

    embed.add_field(
        name="Warn Recommendation",
        value=f"{warn_result['recommend'].upper()}: {warn_result['explanation']}",
        inline=False,
    )
    try:
        await sent_message.edit(embed=embed)
    except discord.HTTPException:
        pass


async def _resolve_log_channel(bot):
    if not DELETE_LOG_CHANNEL_ID:
        return None
    try:
        channel_id = int(DELETE_LOG_CHANNEL_ID)
    except ValueError:
        return None

    channel = bot.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel
    try:
        fetched = await bot.fetch_channel(channel_id)
        return fetched if isinstance(fetched, discord.TextChannel) else None
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def _infer_deleter(message):
    guild = message.guild
    if guild is None:
        return None
    me = guild.me
    if not (me and me.guild_permissions.view_audit_log):
        return None
    try:
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete):
            target = getattr(entry, "target", None)
            if not target or target.id != message.author.id:
                continue
            extra = getattr(entry, "extra", None)
            extra_channel = getattr(extra, "channel", None) if extra else None
            if extra_channel and extra_channel.id != message.channel.id:
                continue
            if (discord.utils.utcnow() - entry.created_at).total_seconds() > 15:
                continue
            return entry.user
    except (discord.Forbidden, discord.HTTPException):
        return None
    return None


def _prepare_payload(message: discord.Message):
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a moderator assistant for the DEW Drinker Discord. "
                    "Review the deleted message against the provided server rules. "
                    "Respond with 'yes' if a warning is recommended or 'no' if not. "
                    "If yes, explain briefly why."
                    f"\nServer rules:\n{SERVER_RULES}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Deleted message details:\n"
                    f"Author: {message.author} (ID {message.author.id})\n"
                    f"Channel: {message.channel} (ID {message.channel.id})\n"
                    f"Content: {message.content or '[no content]'}"
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 256,
        "stream": False,
    }


async def _review_with_llm(message: discord.Message):
    async with aiohttp.ClientSession() as session:
        try:
            payload = _prepare_payload(message)
            async with session.post(LLM_ENDPOINT, json=payload, timeout=20) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception:
            return None

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError):
        return None

    lower = content.lower()
    recommend = "yes" if "yes" in lower else "no"
    explanation = content if recommend == "yes" else "no warning recommended"
    return {"recommend": recommend, "explanation": explanation}
