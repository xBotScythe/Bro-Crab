# cogs/duel.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import asyncio, random, os, json
from typing import Optional

MAX_HP = 30
DATA_FILE = "data/server_data.json"

# Duel logic helpers
def resolve_round(p1_move, p2_move, p1_atk, p1_def, p2_atk, p2_def):
    p1_damage = p2_damage = 0
    p1_bonus = p2_bonus = 0
    crit_chance = 0.1
    crit_multiplier = 1.5

    if p1_move == "atk" and p2_move == "atk":
        dmg1 = p2_atk * (crit_multiplier if random.random() < crit_chance else 1)
        dmg2 = p1_atk * (crit_multiplier if random.random() < crit_chance else 1)
        p1_damage = round(dmg1)
        p2_damage = round(dmg2)
    elif p1_move == "atk" and p2_move == "def":
        dmg = max(0, p1_atk - p2_def)
        if random.random() < crit_chance:
            dmg = round(dmg * crit_multiplier)
        p2_damage = round(dmg)
        p2_bonus = 1
    elif p1_move == "def" and p2_move == "atk":
        dmg = max(0, p2_atk - p1_def)
        if random.random() < crit_chance:
            dmg = round(dmg * crit_multiplier)
        p1_damage = round(dmg)
        p1_bonus = 1
    else:
        p1_bonus = p2_bonus = 1

    return p1_damage, p2_damage, p1_bonus, p2_bonus

# UI Views
class AcceptView(View):
    def __init__(self, challenger_id, target_id):
        super().__init__(timeout=60)
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.accepted = asyncio.Event()
        self.message: Optional[discord.Message] = None

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="Duel invite timed out.", view=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This invite isn't for you.", ephemeral=True)
            return
        self.accepted.set()
        await interaction.response.edit_message(content="Duel accepted — preparing the arena...", view=None)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This invite isn't for you.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Duel declined.", view=None)
        self.stop()

class DuelView(View):
    def __init__(self, cog, duel_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.duel_id = duel_id

    async def interaction_check(self, interaction: discord.Interaction) :
        duel = self.cog.active_duels.get(self.duel_id)
        return duel and interaction.user.id in (duel["p1_id"], duel["p2_id"])

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.primary)
    async def attack(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.player_choice(interaction, self.duel_id, "atk")

    @discord.ui.button(label="Defend", style=discord.ButtonStyle.secondary)
    async def defend(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.player_choice(interaction, self.duel_id, "def")

# Duel Cog
class Duel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_duels = {}  # duel_id 
        self.flavors = {}       # guild_id : stats}

    def load_flavors(self, guild_id: int):
        self.flavors = {}
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    self.flavors = data.get(str(guild_id), {}).get("flavor_roles", {})
            except Exception as e:
                print("Error loading server_data.json:", e)

    def user_flavor_role(self, member: discord.Member, flavor_keys):
        for role in member.roles:
            if role.name.lower() in (k.lower() for k in flavor_keys):
                return role.name
        return None

    def duel_status_text(self, state):
        return (f"Round: {state['round']}\n\n"
                f"**{state['p1_name']}** ({state['p1_flavor']}) — HP: {state['p1_hp']}\n"
                f"ATK {state['p1_atk']} / DEF {state['p1_def'] + state['p1_temp_def']}\n\n"
                f"**{state['p2_name']}** ({state['p2_flavor']}) — HP: {state['p2_hp']}\n"
                f"ATK {state['p2_atk']} / DEF {state['p2_def'] + state['p2_temp_def']}\n\n"
                "Both players choose attack or defend using the buttons below (choices hidden).")

        # Slash command
    @app_commands.command(name="duel", description="Challenge a user to a duel")
    @app_commands.describe(target="User to challenge")
    async def duel(self, interaction: discord.Interaction, target: discord.Member):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        self.load_flavors(guild.id)
        if not self.flavors:
            await interaction.response.send_message("No duel items configured for this server.", ephemeral=True)
            return

        challenger = interaction.user
        if challenger.id == target.id:
            await interaction.response.send_message("You can't duel yourself.", ephemeral=True)
            return

        flavor_keys = set(self.flavors.keys())
        chall_flavor = self.user_flavor_role(challenger, flavor_keys)
        targ_flavor = self.user_flavor_role(target, flavor_keys)
        if not chall_flavor or not targ_flavor:
            await interaction.response.send_message("Both players need a flavor role.", ephemeral=True)
            return

        chall_stats = self.flavors[chall_flavor]["duel_stats"]
        targ_stats = self.flavors[targ_flavor]["duel_stats"]

        embed = discord.Embed(
            title=f"{challenger.display_name} challenges {target.display_name}!",
            description=(f"**{chall_flavor}** — ATK {chall_stats['atk']} / DEF {chall_stats['def']}\n"
                         f"**{targ_flavor}** — ATK {targ_stats['atk']} / DEF {targ_stats['def']}\n\n"
                         "Waiting for acceptance..."),
            color=0x00FF00
        )
        view = AcceptView(challenger.id, target.id)
        msg = await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

        asyncio.create_task(
            self.handle_duel_accept(view, challenger, target, chall_stats, targ_stats, interaction.channel)
        )

        # Duel lifecycle
    async def handle_duel_accept(self, view, challenger, target, chall_stats, targ_stats, channel):
        try:
            await asyncio.wait_for(view.accepted.wait(), timeout=60)
        except asyncio.TimeoutError:
            await view.message.edit(content="Duel invite timed out.", view=None)
            return

        duel_id = str(random.randint(10**8, 10**9 - 1))
        state = {
            "duel_id": duel_id,
            "p1_id": challenger.id,
            "p2_id": target.id,
            "p1_name": challenger.display_name,
            "p2_name": target.display_name,
            "p1_flavor": self.user_flavor_role(challenger, set(self.flavors.keys())),
            "p2_flavor": self.user_flavor_role(target, set(self.flavors.keys())),
            "p1_atk": chall_stats["atk"],
            "p1_def": chall_stats["def"],
            "p2_atk": targ_stats["atk"],
            "p2_def": targ_stats["def"],
            "p1_hp": MAX_HP,
            "p2_hp": MAX_HP,
            "p1_move": None,
            "p2_move": None,
            "p1_temp_def": 0,
            "p2_temp_def": 0,
            "round": 1,
            "message_id": None,
            "channel_id": channel.id
        }
        self.active_duels[duel_id] = state

        arena_embed = discord.Embed(
            title="Dew Duel — Arena",
            description=self.duel_status_text(state),
            color=0x00FF00
        )
        arena_view = DuelView(self, duel_id)
        msg = await channel.send(embed=arena_embed, view=arena_view)
        state["message_id"] = msg.id

        asyncio.create_task(self.duel_watcher(duel_id))

    async def player_choice(self, interaction, duel_id: str, choice: str):
        state = self.active_duels.get(duel_id)
        if not state:
            await interaction.response.send_message("Duel not found.", ephemeral=True)
            return

        uid = interaction.user.id
        if uid == state["p1_id"]:
            if state["p1_move"] is not None:
                await interaction.response.send_message("You already chose this round.", ephemeral=True)
                return
            state["p1_move"] = choice
        elif uid == state["p2_id"]:
            if state["p2_move"] is not None:
                await interaction.response.send_message("You already chose this round.", ephemeral=True)
                return
            state["p2_move"] = choice
        else:
            await interaction.response.send_message("You're not part of this duel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await self.update_duel_message(duel_id)

    async def wait_for_both_moves(self, duel_id):
        while True:
            state = self.active_duels.get(duel_id)
            if not state:
                return
            if state["p1_move"] and state["p2_move"]:
                return
            await asyncio.sleep(0.3)

    async def duel_watcher(self, duel_id):
        while duel_id in self.active_duels:
            state = self.active_duels.get(duel_id)
            if not state:
                return
            try:
                await asyncio.wait_for(self.wait_for_both_moves(duel_id), timeout=60)
            except asyncio.TimeoutError:
                if state["p1_move"] is None:
                    await self.end_duel(duel_id, state["p2_id"], f"{state['p1_name']} did not choose (forfeit).")
                    return
                if state["p2_move"] is None:
                    await self.end_duel(duel_id, state["p1_id"], f"{state['p2_name']} did not choose (forfeit).")
                    return

            p1_total_def = state["p1_def"] + state["p1_temp_def"]
            p2_total_def = state["p2_def"] + state["p2_temp_def"]
            p1_dmg, p2_dmg, p1_bonus, p2_bonus = resolve_round(
                state["p1_move"], state["p2_move"],
                state["p1_atk"], p1_total_def,
                state["p2_atk"], p2_total_def
            )

            state["p1_hp"] -= p1_dmg
            state["p2_hp"] -= p2_dmg
            state["p1_temp_def"] = p1_bonus
            state["p2_temp_def"] = p2_bonus
            state["round"] += 1

            await self.update_duel_message(duel_id, after_resolve=True, last_moves=(state["p1_move"], state["p2_move"], p1_dmg, p2_dmg))
            state["p1_move"] = state["p2_move"] = None

            if state["p1_hp"] <= 0 and state["p2_hp"] <= 0:
                await self.end_duel(duel_id, None, "Draw")
                return
            elif state["p1_hp"] <= 0:
                await self.end_duel(duel_id, state["p2_id"], f"{state['p1_name']} fell to 0 HP.")
                return
            elif state["p2_hp"] <= 0:
                await self.end_duel(duel_id, state["p1_id"], f"{state['p2_name']} fell to 0 HP.")
                return

            await asyncio.sleep(0.5)

    async def update_duel_message(self, duel_id, after_resolve=False, last_moves=None):
        state = self.active_duels.get(duel_id)
        if not state: return
        channel = self.bot.get_channel(state["channel_id"])
        if not channel: return
        try:
            msg = await channel.fetch_message(state["message_id"])
        except Exception:
            return

        desc = self.duel_status_text(state)
        if after_resolve and last_moves:
            p1_move, p2_move, p1_dmg, p2_dmg = last_moves
            line = f"Last round: {state['p1_name']} chose **{p1_move}**, {state['p2_name']} chose **{p2_move}**. "
            if p1_dmg: line += f"{state['p1_name']} took {p1_dmg} dmg. "
            if p2_dmg: line += f"{state['p2_name']} took {p2_dmg} dmg. "
            desc = line + "\n\n" + desc

        embed = discord.Embed(title="Dew Duel — Arena", description=desc, color=0x00FF00)
        embed.set_footer(text=f"Round {state['round']} — waiting for both choices")
        await msg.edit(embed=embed, view=DuelView(self, duel_id))

    async def end_duel(self, duel_id, winner_id: Optional[int], reason=""):
        state = self.active_duels.get(duel_id)
        if not state:
            return
        channel = self.bot.get_channel(state["channel_id"])
        msg = None
        if channel:
            try:
                msg = await channel.fetch_message(state["message_id"])
            except Exception:
                pass

        if winner_id is None:
            title = "Dew Duel — Draw"
            desc = f"Result: Draw. {reason}"
        else:
            winner_name = state["p1_name"] if winner_id == state["p1_id"] else state["p2_name"]
            title = "Dew Duel — Finished"
            desc = f"Winner: {winner_name}. {reason}"

        if msg:
            embed = discord.Embed(title=title, description=desc, color=0x00FF00)
            await msg.edit(embed=embed, view=None)

        self.active_duels.pop(duel_id, None)
    
    @app_commands.command(name="duelrules", description="Learn how Dew Duel works and see flavor stats")
    async def duelrules(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Dew Duel — Rules & Mechanics",
            description=(
                "Welcome to Dew Duel! Here's how it works:\n\n"
                "**1. HP, ATK, DEF**\n"
                "- Each player starts with **30 HP**.\n"
                "- Attack (ATK) determines damage dealt.\n"
                "- Defense (DEF) reduces incoming damage.\n\n"
                "**2. Moves**\n"
                "- **Attack**: Deal damage based on your ATK vs opponent DEF.\n"
                "- **Defend**: Reduce damage this round and gain temporary bonus DEF.\n"
                "- Both players choose simultaneously.\n\n"
                "**3. Critical Hits & Bonuses**\n"
                "- 10% chance to deal **1.5x damage**.\n"
                "- Defending successfully gives a small DEF bonus next round.\n\n"
                "**4. Winning**\n"
                "- Reduce your opponent's HP to 0 to win.\n"
                "- If both reach 0 HP simultaneously, it’s a draw.\n\n"
                                        ),
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Setup
async def setup(bot):
    await bot.add_cog(Duel(bot))
