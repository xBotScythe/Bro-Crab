import discord, asyncio, json
from discord import app_commands
from discord.ext import commands
from utils.emulator_manager import EmulatorController, send_press_remote, send_press_sequence_remote

USER_DATA_LOCK = asyncio.Lock()

async def read_user_data():
    async with USER_DATA_LOCK:
        # read JSON safely in thread
        return await asyncio.to_thread(lambda: json.load(open("data/user_data.json", "r")))

async def write_user_data(data):
    async with USER_DATA_LOCK:
        await asyncio.to_thread(lambda: json.dump(data, open("data/user_data.json", "w"), indent=4))



class EmulatorCtrl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="controller", 
        description="Show the emulator controller interface"
    )
    async def controller(self, interaction: discord.Interaction):
        """Send the interactive controller view."""
        view = EmulatorController()  # Make sure this is a discord.ui.View
        await interaction.response.send_message(
            "Use the buttons below to control the emulator:", 
            view=view, 
            ephemeral=True
        )
    
    @app_commands.command(name="sequence", description="Send a sequence of button presses to the emulator")
    @app_commands.describe(sequence="Sequence of button presses (e.g., UP,UP,DOWN,DOWN,LEFT,RIGHT,LEFT,RIGHT,B,A,START)")
    async def sequence(self, interaction: discord.Interaction, sequence: str):
        """Send a sequence of button presses to the emulator."""
        buttons = sequence.strip().split(",")
        valid_buttons = {"A", "B", "UP", "DOWN", "LEFT", "RIGHT", "START", "SELECT"}

        # validate input
        for button in buttons:
            if button.upper() not in valid_buttons:
                await interaction.response.send_message(
                    f"Invalid button: {button}. Valid buttons are: {', '.join(valid_buttons)}",
                    ephemeral=True
                )
                return

        await interaction.response.defer(ephemeral=True)
        # send the button presses
        send_press_sequence_remote(buttons)

        await interaction.followup.send(
            f"Sent button sequence: {' '.join(buttons)}",
            ephemeral=True
        )
    # leaderboard command
    @app_commands.command(
        name="leaderboard",
        description="Show who has the most button presses!"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        raw = await read_user_data()
        guild_id = str(interaction.guild.id)

        if guild_id not in raw:
            await interaction.response.send_message(
                "No data found for this server.",
                ephemeral=True
            )
            return

        data = raw[guild_id]
        leaderboard = []

        # build cache of members
        members = {str(member.id): member.display_name for member in interaction.guild.members}

        for user_id, user_data in data.items():
            count = user_data.get("button_pressed_count", 0)
            if count > 0:
                name = members.get(user_id, f"<User {user_id}>")
                leaderboard.append((name, count))

        if not leaderboard:
            await interaction.response.send_message(
                "No button presses recorded yet.",
                ephemeral=True
            )
            return

        # sort descending
        leaderboard.sort(key=lambda x: x[1], reverse=True)

        # build message
        msg = "**Button Press Leaderboard:**\n"
        for idx, (username, count) in enumerate(leaderboard[:10], start=1):
            msg += f"{idx}. **{username}** — {count} presses\n"

        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(EmulatorCtrl(bot))
