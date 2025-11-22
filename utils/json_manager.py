import asyncio
import copy
import json
import os
from typing import Any, Optional

_FILE_LOCK = asyncio.Lock()


def _clone_default(default: Any) :
    if isinstance(default, (dict, list, set)):
        return copy.deepcopy(default)
    return default


def load_json(path: str, default: Optional[Any] = None) :
    fallback = {} if default is None else default
    if not os.path.exists(path):
        return _clone_default(fallback)
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return _clone_default(fallback)


def write_json(data: Any, path: str) :
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(temp_path, path)


async def load_json_async(path: str, default: Optional[Any] = None) :
    async with _FILE_LOCK:
        return load_json(path, default)


async def write_json_async(data: Any, path: str) :
    async with _FILE_LOCK:
        write_json(data, path)
