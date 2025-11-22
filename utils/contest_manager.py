import asyncio
from datetime import datetime, timezone
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


async def add_design_submission(guild_id, author_id, flavor_name, attachment_url):
    # enqueue a design submission for later release
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    if not contest["active"]:
        raise ValueError("contest is not active")
    if any(design["author_id"] == author_id for design in contest["design_queue"]):
        raise ValueError("you already submitted a design for this contest")

    entry = {
        "author_id": author_id,
        "flavor_name": flavor_name,
        "url": attachment_url,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    contest["design_queue"].append(entry)
    await _write_server_data(data)
    return entry


async def get_design_queue(guild_id):
    # view pending designs
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    return contest["design_queue"]


async def clear_design_queue(guild_id):
    # pop pending designs for release
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    queue = list(contest["design_queue"])
    contest["design_queue"] = []
    await _write_server_data(data)
    return queue


async def record_released_design(guild_id, entry):
    # store released design metadata for later winner calc
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    contest["released_designs"].append(entry)
    await _write_server_data(data)


async def get_released_designs(guild_id):
    # return released designs metadata
    data = await _load_server_data()
    contest = await _get_contest_entry(data, guild_id)
    return contest["released_designs"]


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
    contest["design_queue"] = []
    contest["released_designs"] = []
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

