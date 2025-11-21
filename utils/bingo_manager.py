import random
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from utils.json_manager import load_json_async, write_json_async

USER_DATA_FILE = "data/user_data.json"
SERVER_DATA_FILE = "data/server_data.json"
FREE_SPACE_LABEL = "Free Space"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


async def _load_server_data():
    return await load_json_async(SERVER_DATA_FILE, {})


async def _load_user_data():
    return await load_json_async(USER_DATA_FILE, {})


async def _write_user_data(data: Dict):
    await write_json_async(data, USER_DATA_FILE)


async def get_flavor_pool(guild_id: int):
    data = await _load_server_data()
    guild_entry = data.get(str(guild_id), {})
    flavor_roles = guild_entry.get("flavor_roles", {})
    return list(flavor_roles.keys())


def _build_cells_from_pool(pool: List[str], size: int):
    total_cells = size * size
    needed = total_cells - 1  # center slot always free
    chosen = random.sample(pool, needed)
    center_index = total_cells // 2
    cells = []
    flavor_iter = iter(chosen)
    for idx in range(total_cells):
        if idx == center_index:
            cells.append({"label": FREE_SPACE_LABEL, "marked": True})
        else:
            cells.append({"label": next(flavor_iter), "marked": False})
    return cells


async def create_board(guild_id: int, user_id: int, size: int):
    pool = await get_flavor_pool(guild_id)
    total_cells = size * size
    needed = total_cells - 1
    if len(pool) < needed:
        raise ValueError(f"need at least {needed} unique flavors to build a {size}x{size} board.")
    board = {
        "size": size,
        "cells": _build_cells_from_pool(pool, size),
        "updated_at": _now_iso(),
    }
    await save_board(guild_id, user_id, board)
    return board


async def save_board(guild_id: int, user_id: int, board: Dict):
    data = await _load_user_data()
    guild_entry = data.setdefault(str(guild_id), {})
    user_entry = guild_entry.setdefault(str(user_id), {})
    user_entry["bingo"] = board
    await _write_user_data(data)


async def get_board(guild_id: int, user_id: int):
    data = await _load_user_data()
    return data.get(str(guild_id), {}).get(str(user_id), {}).get("bingo")


async def mark_flavor(guild_id: int, user_id: int, flavor_name: str):
    board = await get_board(guild_id, user_id)
    if not board:
        return False, None
    normalized = flavor_name.strip().casefold()
    changed = False
    for cell in board.get("cells", []):
        if cell["label"].casefold() == normalized and not cell.get("marked"):
            cell["marked"] = True
            board["updated_at"] = _now_iso()
            changed = True
            break
    if changed:
        await save_board(guild_id, user_id, board)
    return changed, board


def _wrap_text(label: str, font: ImageFont.ImageFont, max_width: int):
    words = label.split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        test = f"{current} {word}"
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _load_font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
    except OSError:
        try:
            return ImageFont.truetype("Arial.ttf", size=size)
        except OSError:
            return ImageFont.load_default()


def render_board(board: Dict):
    size = board.get("size", 5)
    cells = board.get("cells", [])
    margin = 80
    gap = 16
    base_cell = 320
    cell_size = max(220, base_cell - (size - 3) * 40)
    width = margin * 2 + size * cell_size + (size - 1) * gap
    height = width + 180

    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = _load_font(80)
    subtitle_font = _load_font(40)
    cell_font_size = max(48, int(cell_size * 0.22))
    cell_font = _load_font(cell_font_size)

    title = "Mountain Dew Bingo"
    title_bbox = title_font.getbbox(title)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) / 2
    draw.text((title_x, 40), title, fill=(0, 0, 0), font=title_font)

    board_top = 230
    for index, cell in enumerate(cells):
        row, col = divmod(index, size)
        x0 = margin + col * (cell_size + gap)
        y0 = board_top + row * (cell_size + gap)
        x1 = x0 + cell_size
        y1 = y0 + cell_size

        fill_color = (245, 245, 245) if not cell.get("marked") else (220, 240, 220)
        outline_color = (0, 0, 0)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=28, fill=fill_color, outline=outline_color, width=5)

        label = cell.get("label", "")
        lines = _wrap_text(label, cell_font, cell_size - 60)
        text = "\n".join(lines)
        text_bbox = draw.multiline_textbbox((0, 0), text, font=cell_font, align="center")
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = x0 + (cell_size - text_width) / 2
        text_y = y0 + (cell_size - text_height) / 2
        draw.multiline_text((text_x, text_y), text, fill=(0, 0, 0), font=cell_font, align="center")

        if cell.get("marked"):
            line_y = y0 + cell_size / 2
            draw.line((x0 + 24, line_y, x1 - 24, line_y), fill=(200, 0, 0), width=10)

    updated_at = board.get("updated_at")
    if updated_at:
        stamp = f"Updated: {updated_at.split('T')[0]}"
        draw.text((margin, height - 70), stamp, fill=(80, 80, 80), font=subtitle_font)

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
