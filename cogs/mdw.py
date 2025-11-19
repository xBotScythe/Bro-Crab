import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re

from utils.vote_manager import load_votes

class Mdw(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # store bot ref and wiki base url
        self.bot = bot
        self.wiki_base = "https://mountaindew.fandom.com/wiki/"

    async def flavor_autocomplete(self, interaction: discord.Interaction, current: str):
        # pull guild flavors to build autocomplete choices
        flavors = await load_votes(interaction.guild_id)
        return [
            app_commands.Choice(name=flavor, value=flavor)
            for flavor in flavors.keys()
            if current.lower() in flavor.lower()
        ][:25]

    async def get_wiki_intro(self, flavor: str):
        # build wiki url for the requested flavor
        flavor_query = flavor.replace(" ", "_")
        page_url = f"{self.wiki_base}{flavor_query}"

        # fetch raw wiki html
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(page_url) as resp:
                    if resp.status != 200:
                        return flavor, None
                    html = await resp.text()
            except Exception:
                return flavor, None

        soup = BeautifulSoup(html, "html.parser")
        content_div = soup.find("div", class_="mw-parser-output")
        if not content_div:
            return flavor, None

        # drop infobox to avoid description noise
        infobox = content_div.find("aside", class_="portable-infobox")
        if infobox:
            infobox.decompose()

        # drop table of contents blocks
        toc = content_div.find("div", id="toc")
        if toc:
            toc.decompose()

        first_p = None
        # prefer first long paragraph directly within content div
        for p in content_div.find_all("p", recursive=False):
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 20:
                first_p = text
                break

        # fallback: scan all nested paragraphs
        if not first_p:
            for p in content_div.find_all("p"):
                text = p.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    first_p = text
                    break

        if not first_p:
            return flavor, None

        # remove citation brackets since they read poorly in embeds
        first_p = re.sub(r"\[\s*\d+\s*\]", "", first_p)

        return flavor, first_p

    @app_commands.command(name="mdw", description="Get info about a Mountain Dew flavor")
    async def mdw(self, interaction: discord.Interaction, flavor: str, ephemeral: bool = None):
        # default to ephemeral responses unless explicitly forced
        is_ephemeral = ephemeral if ephemeral is not None else True
        await interaction.response.defer(ephemeral=is_ephemeral)

        try:
            # fetch wiki intro with a timeout guard
            title, description = await asyncio.wait_for(self.get_wiki_intro(flavor), timeout=10)
        except asyncio.TimeoutError:
            await interaction.followup.send("Request timed out. Try again later.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"Something went wrong: {e}", ephemeral=True)
            return

        if not description:
            await interaction.followup.send(f"Sorry, no wiki paragraph found for '{flavor}'.", ephemeral=True)
            return

        embed = discord.Embed(
            title=title,
            description=description[:2000],
            color=0x00FF00,
            url=f"{self.wiki_base}{title.replace(' ', '_')}"
        )
        # final response with wiki embed
        await interaction.followup.send(embed=embed, ephemeral=is_ephemeral)

    @mdw.autocomplete("flavor")
    async def mdw_autocomplete(self, interaction: discord.Interaction, current: str):
        # pass through to shared autocomplete helper
        return await self.flavor_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    # register cog with bot
    await bot.add_cog(Mdw(bot))
