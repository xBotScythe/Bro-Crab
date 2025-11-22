import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from utils.json_manager import load_json_async, write_json_async

SERVER_FILE = "data/server_data.json"
CONTEST_CATEGORY_ARCHIVE = 1312895271625031741
# contest manager: async helpers for contest state

_lock = asyncio.Lock()


async def _load_server_data():
    # shared read helper with async lock
    async with _lock:
        return await load_json_async(SERVER_FILE)


async def _write_server_data(data):
    # shared write helper with async lock
    async with _lock:
        await write_json_async(data, SERVER_FILE)


async def _get_contest_entry(server_data, guild_id):
    # ensures contest blob exists for given guild
    guild_entry = server_data.setdefault(str(guild_id), {})
    contest_entry = guild_entry.setdefault(
        "contest",
        {
            "active": False,
            "end_at": None,
            "channel_id": None,
            "announcement_message": "",
            "ideas": [],
            "idea_queue": [],
            "design_queue": [],
            "released_designs": [],
            "round": 1,
            "grace_until": None,
        },
    )
    return contest_entry


async def load_contest(guild_id):
    # load contest entry for guild
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    return contest


async def save_contest(guild_id, contest_entry):
    # write back a contest entry wholesale
    data = await _load_server_data()
    guild_entry = data.setdefault(str(guild_id), {})
    guild_entry["contest"] = contest_entry
    await _write_server_data(data)


async def add_idea(guild_id, idea_name, user_id, active):
    # add idea to active list or queue depending on contest state
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    target_list = contest["ideas"] if active else contest["idea_queue"]

    if any(idea["name"].lower() == idea_name.lower() for idea in target_list):
        raise ValueError("idea already exists")

    entry = {
        "name": idea_name,
        "submitted_by": user_id,
        "votes": 0,
        "voters": [],
        "status": "pending" if not active else "active",
    }

    target_list.append(entry)
    await _write_server_data(data)
    return entry


async def move_queued_ideas(guild_id):
    # promote queued ideas when contest goes live
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    for idea in contest["idea_queue"]:
        idea["status"] = "active"
        contest["ideas"].append(idea)
    contest["idea_queue"] = []
    await _write_server_data(data)


async def vote_for_idea(guild_id, idea_name, user_id):
    # increment vote count if user hasn't voted yet
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    for idea in contest["ideas"]:
        if idea["name"].lower() == idea_name.lower():
            if user_id in idea["voters"]:
                raise ValueError("already voted on this idea")
            idea["voters"].append(user_id)
            idea["votes"] += 1
            await _write_server_data(data)
            return idea
    raise ValueError("idea not found in active contest")


async def add_design_submission(guild_id, author_id, attachment_url):
    # enqueue a design submission for later release
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    if not contest["active"]:
        raise ValueError("contest is not active")
    if any(design["author_id"] == author_id for design in contest["design_queue"]):
        raise ValueError("you already submitted a design for this contest")

    entry = {"author_id": author_id, "url": attachment_url, "votes": 0}
    contest["design_queue"].append(entry)
    await _write_server_data(data)
    return entry


async def get_design_queue(guild_id):
    # view pending designs
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    return contest["design_queue"]


async def clear_design_queue(guild_id):
    # move pending designs to released bucket
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    queue = contest["design_queue"]
    contest["released_designs"].extend(queue)
    contest["design_queue"] = []
    await _write_server_data(data)
    return queue


async def start_contest(guild_id, announcement_message, end_at_iso, channel_id):
    # activate contest window with message + end time
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    contest["active"] = True
    contest["announcement_message"] = announcement_message
    contest["end_at"] = end_at_iso
    contest["channel_id"] = channel_id
    contest["grace_until"] = None
    await _write_server_data(data)


async def end_contest(guild_id):
    # cleanup after contest ends and bump round counter
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    contest["active"] = False
    contest["ideas"] = []
    contest["design_queue"] = []
    contest["end_at"] = None
    contest["channel_id"] = None
    contest["grace_until"] = None
    contest["round"] = contest.get("round", 1) + 1
    await _write_server_data(data)


async def mark_contest_finished(guild_id, grace_until_iso):
    # mark contest inactive but leave data until grace pass
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    contest["active"] = False
    contest["grace_until"] = grace_until_iso
    await _write_server_data(data)


async def get_top_idea(guild_id):
    # return idea with most votes (ties fall to earliest)
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    if not contest["ideas"]:
        return None
    return max(contest["ideas"], key=lambda idea: idea.get("votes", 0))


async def needs_archive(contest_entry):
    # true if contest is active and end time passed
    if contest_entry["active"]:
        if not contest_entry["end_at"]:
            return False
        try:
            end_time = datetime.fromisoformat(contest_entry["end_at"])
        except ValueError:
            return False
        return datetime.now(timezone.utc) >= end_time
    grace = contest_entry.get("grace_until")
    if grace:
        try:
            end_time = datetime.fromisoformat(grace)
        except ValueError:
            return True
        return datetime.now(timezone.utc) >= end_time
    return False


async def list_active_ideas(guild_id):
    # return copy of active ideas
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    return [idea for idea in contest["ideas"]]


async def contest_is_active(guild_id):
    # simple bool for slash commands
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    return contest["active"]
