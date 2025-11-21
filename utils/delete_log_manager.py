import json
import os

import aiohttp
import discord

DELETE_LOG_CHANNEL_ID = os.getenv("DELETE_LOG_CHANNEL_ID")
LLM_ENDPOINT = os.getenv("LLM_REVIEW_ENDPOINT", "http://100.66.147.4:1234/v1/chat/completions")

SERVER_RULES = """
Dew Drinker key rules:
- Treat everyone respectfully; harassment or personal attacks are not allowed.
- No spam, repeated nonsense, or intrusive/off-topic content that derails chats.
- Zero tolerance for bigotry or ignoring stated pronouns.
- Keep politics out of public spaces and stay within channel topics.
- Share accurate info; clearly label rumors or uncertain leaks.
"""

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
            ch = getattr(extra, "channel", None) if extra else None
            if ch and ch.id != message.channel.id:
                continue

            # only recent deletes
            if (discord.utils.utcnow() - entry.created_at).total_seconds() > 15:
                continue

            return entry.user
    except (discord.Forbidden, discord.HTTPException):
        return None

    return None


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


def _prepare_payload(message):
    return {
        "model": "local",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a moderator assistant for the DEW Drinker Discord. "
                    "Review the deleted message. Respond yes/no with a short explanation.\n"
                    f"Server rules:\n{SERVER_RULES}"
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
        "stream": False
    }


async def _review_with_llm(message: discord.Message):
    async with aiohttp.ClientSession() as session:
        try:
            payload = _prepare_payload(message)
            async with session.post(LLM_ENDPOINT, json=payload, timeout=60) as resp:
                resp.raise_for_status()
                data = await _parse_llm_response(resp)
        except Exception:
            return None

    if not data:
        return None

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError):
        return None

    lower = content.lower()
    recommend = "yes" if "yes" in lower else "no"
    explanation = content if recommend == "yes" else "no warning recommended"
    return {"recommend": recommend, "explanation": explanation}


async def _parse_llm_response(resp: aiohttp.ClientResponse):
    content_type = resp.headers.get("Content-Type", "")
    if "text/event-stream" in content_type:
        return await _parse_sse_response(resp)
    try:
        return await resp.json()
    except aiohttp.ContentTypeError:
        return None


async def _parse_sse_response(resp: aiohttp.ClientResponse):
    buffer = ""
    result_payload = None

    async for chunk in resp.content.iter_chunked(1024):
        try:
            buffer += chunk.decode("utf-8")
        except UnicodeDecodeError:
            buffer += chunk.decode("utf-8", errors="ignore")

        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            event_type = "message"
            data_lines = []

            for line in block.splitlines():
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())

            data = "\n".join(data_lines).strip()
            if not data:
                continue

            if event_type == "error":
                raise RuntimeError(data)

            if event_type in {"result", "message", "completion"}:
                try:
                    result_payload = json.loads(data)
                except json.JSONDecodeError:
                    continue

            if event_type in {"done", "end", "finish"}:
                return result_payload

    return result_payload
