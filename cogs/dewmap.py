import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from utils.dew_map_manager import add_flavors, remove_flavors, list_flavors, create_find, update_find_image, delete_find
from utils.admin_manager import check_admin_status


geolocator = Nominatim(user_agent="dew-map-bot")
tz_finder = TimezoneFinder()


async def geocode_address(address: str):
    loop = asyncio.get_running_loop()
    def _geocode():
        try:
            location = geolocator.geocode(address, timeout=10)
            if location is None:
                return None
            return (location.latitude, location.longitude)
        except Exception:
            return None
    return await loop.run_in_executor(None, _geocode)


class DewFindModal(discord.ui.Modal):
    def __init__(self, cog, flavor_name, size):
        super().__init__(title="Log a Dew Find")
        self.cog = cog
        self.flavor = flavor_name
        self.size = size
        self.place_input = discord.ui.TextInput(label="Store or Location Name", placeholder="e.g., Dew Stop Market", required=True)
        self.address_input = discord.ui.TextInput(label="Full Address", placeholder="street, city, state zip", required=True)
        self.add_item(self.place_input)
        self.add_item(self.address_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        coords = await geocode_address(self.address_input.value.strip())
        if not coords:
            await interaction.followup.send("Couldn't verify that address. Please double-check and try again.", ephemeral=True)
            return
        lat, lon = coords
        tz_name = tz_finder.timezone_at(lat=lat, lng=lon) or "UTC"
        find_id = create_find(
            self.flavor,
            self.size,
            self.place_input.value.strip(),
            self.address_input.value.strip(),
            lat,
            lon,
            tz_name,
        )
        await interaction.followup.send(f"Logged find **{find_id}** at {self.place_input.value.strip()}!", ephemeral=True)
        await self.cog.prompt_for_image(interaction.user, find_id)


class DewMap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_images = {}  # user_id -> find_id

    async def prompt_for_image(self, user: discord.User, find_id: str):
        try:
            dm = await user.create_dm()
            await dm.send(
                f"Thanks for submitting Dew find `{find_id}`! Reply to this DM with an image attachment or direct image URL. Send `no` to skip."
            )
            self.pending_images[user.id] = find_id
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return
        pending_id = self.pending_images.get(message.author.id)
        if not pending_id:
            return

        content = (message.content or "").strip()
        if content.lower() == "no":
            await message.channel.send("No problem, thanks! If you change your mind, reply with the image and find ID later.")
            self.pending_images.pop(message.author.id, None)
            return

        image_url = None
        if message.attachments:
            image_url = message.attachments[0].url
        elif content.startswith("http"):
            image_url = content

        if image_url:
            update_find_image(pending_id, image_url)
            await message.channel.send("Image attached to your find. Thank you!")
            self.pending_images.pop(message.author.id, None)
        else:
            await message.channel.send("Didn't detect an attachment or direct URL. Please send the image or say 'no' to skip.")

    @app_commands.command(name="dewfind", description="Log a flavor find with location info")
    @app_commands.describe(flavor="Flavor name", size="Container size, e.g., 20oz, 2L")
    async def dewfind(self, interaction: discord.Interaction, flavor: str, size: str):
        flavors = list_flavors()
        if flavor not in flavors:
            await interaction.response.send_message("Flavor not found in map database. Ask an admin to add it first.", ephemeral=True)
            return
        modal = DewFindModal(self, flavor, size)
        await interaction.response.send_modal(modal)

    @dewfind.autocomplete("flavor")
    async def flavor_autocomplete(self, interaction: discord.Interaction, current: str):
        flavors = list_flavors()
        matches = [name for name in flavors if current.lower() in name.lower()]
        return [app_commands.Choice(name=name, value=name) for name in matches[:25]]

    @app_commands.command(name="addflavortomap", description="Add comma-separated flavors to map database")
    async def addflavortomap(self, interaction: discord.Interaction, flavors_csv: str):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        flavors = [name.strip() for name in flavors_csv.split(",") if name.strip()]
        added = add_flavors(flavors)
        await interaction.response.send_message(f"Added {len(added)} flavors to the map list.", ephemeral=True)

    @app_commands.command(name="removeflavorfrommap", description="Remove comma-separated flavors from map database")
    async def removeflavorfrommap(self, interaction: discord.Interaction, flavors_csv: str):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        flavors = [name.strip() for name in flavors_csv.split(",") if name.strip()]
        removed = remove_flavors(flavors)
        await interaction.response.send_message(f"Removed {len(removed)} flavors from the map list.", ephemeral=True)

    @app_commands.command(name="removefind", description="Remove a find by ID")
    async def removefind(self, interaction: discord.Interaction, find_id: str):
        if not await check_admin_status(self.bot, interaction):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Ask a mod politely maybe?", ephemeral=True)
            return
        if delete_find(find_id):
            await interaction.response.send_message(f"Removed find `{find_id}` from the map.", ephemeral=True)
        else:
            await interaction.response.send_message("No find with that ID was found.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DewMap(bot))
