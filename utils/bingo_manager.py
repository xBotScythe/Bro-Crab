import random
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from utils.json_manager import load_json_async, write_json_async

USER_DATA_FILE = "data/user_data.json"
SERVER_DATA_FILE = "data/server_data.json"
FREE_SPACE_LABEL = "Free Space"
FONT_PATH = "data/comicsans.ttf"


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
    for path in (FONT_PATH, "DejaVuSans-Bold.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_board(board: Dict):
    size = board.get("size", 5)
    cells = board.get("cells", [])
    cell_size = 280 if size == 3 else 230
    margin = 80
    header_space = 180
    grid_left = margin
    grid_top = margin + header_space
    grid_right = grid_left + size * cell_size
    grid_bottom = grid_top + size * cell_size
    width = grid_right + margin
    height = grid_bottom + margin

    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    header_letters = "BINGO"[:size]
    header_font = _load_font(int(cell_size * 0.35))
    letter_color = (20, 24, 36)
    for idx, letter in enumerate(header_letters):
        center_x = grid_left + idx * cell_size + cell_size / 2
        bbox = header_font.getbbox(letter)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = center_x - text_width / 2
        text_y = margin
        draw.text((text_x, text_y), letter, fill=letter_color, font=header_font)

    line_color = (206, 212, 218)
    draw.rounded_rectangle((grid_left, grid_top, grid_right, grid_bottom), radius=50, outline=line_color, width=6)
    for i in range(1, size):
        y = grid_top + i * cell_size
        draw.line((grid_left, y, grid_right, y), fill=line_color, width=4)
        x = grid_left + i * cell_size
        draw.line((x, grid_top, x, grid_bottom), fill=line_color, width=4)

    cell_font = _load_font(max(60, int(cell_size * 0.22)))

    for index, cell in enumerate(cells):
        row, col = divmod(index, size)
        x0 = grid_left + col * cell_size
        y0 = grid_top + row * cell_size
        x1 = x0 + cell_size
        y1 = y0 + cell_size

        if cell.get("marked"):
            fill_box = (x0 + 12, y0 + 12, x1 - 12, y1 - 12)
            draw.rounded_rectangle(fill_box, radius=30, fill=(234, 244, 234))

        label = cell.get("label", "")
        lines = _wrap_text(label, cell_font, cell_size - 100)
        text = "\n".join(lines)
        text_bbox = draw.multiline_textbbox((0, 0), text, font=cell_font, align="center")
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = x0 + (cell_size - text_width) / 2
        text_y = y0 + (cell_size - text_height) / 2
        draw.multiline_text((text_x, text_y), text, fill=letter_color, font=cell_font, align="center")

        if cell.get("marked"):
            line_y = y0 + cell_size / 2
            draw.line((x0 + 40, line_y, x1 - 40, line_y), fill=(200, 0, 0), width=12)

    updated_at = board.get("updated_at")
    if updated_at:
        date_font = _load_font(36)
        stamp = f"Updated: {updated_at.split('T')[0]}"
        draw.text((grid_left, grid_bottom + 20), stamp, fill=(120, 120, 120), font=date_font)

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
