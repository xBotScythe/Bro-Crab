import time
import discord
from discord import ui
import requests

from utils.json_manager import load_json_async, write_json_async

LAPTOP_IP = "100.66.147.4" # tailscale ip
PORT = 7777  

def send_press_sequence_remote(buttons: list):
    button_map = {"a": "A", "b": "B", "up": "Up", "down": "Down", "left": "Left", "right": "Right", "start": "Start", "select": "Select"}
    url = f"http://{LAPTOP_IP}:{PORT}/press"
    try:
        for button in buttons:
            mapped_button = button_map[button.lower()]
            requests.post(url, json={"button": mapped_button}, timeout=2)
            time.sleep(0.35)  # brief pause between presses
        print(f"Sent button sequence: {buttons}")
    except Exception as e:
        print("Error sending sequence:", e)

def send_press_remote(button: str):
    url = f"http://{LAPTOP_IP}:{PORT}/press"
    try:
        requests.post(url, json={"button": button}, timeout=2)
        print(f"Sent button: {button}")
    except Exception as e:
        print("Error sending:", e)


class EmulatorController(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # Directional buttons
        for label in ["Up", "Down", "Left", "Right"]:
            btn = ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=label)
            btn.callback = self.button_callback
            self.add_item(btn)

        # Action buttons
        for label in ["A", "B", "Start", "Select", "L", "R"]:
            btn = ui.Button(label=label, style=discord.ButtonStyle.secondary, custom_id=label)
            btn.callback = self.button_callback
            self.add_item(btn)

    async def button_callback(self, interaction: discord.Interaction):
        cmd = interaction.data["custom_id"]
        file_path = "data/user_data.json"
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        #  Send button press to emulator 
        try:
            send_press_remote(cmd)
        except Exception as e:
            print(f"Error sending button: {e}")
        data = await load_json_async(file_path)

        # ensure guild and user entries exist
        data.setdefault(guild_id, {})
        data[guild_id].setdefault(user_id, {})

        # increment button press count
        data[guild_id][user_id]["button_pressed_count"] = data[guild_id][user_id].get("button_pressed_count", 0) + 1

        await write_json_async(data, file_path)

        #  silent ephemeral ack so buttons don't "spin" 
        await interaction.response.defer(ephemeral=True)
