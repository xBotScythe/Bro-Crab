import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from utils.blackjack_manager import make_deck, score_hand, is_blackjack
from utils.booster_manager import check_boost_status
from utils.economy_manager import EconomyManager
import utils.blackjack_manager as bj
from utils.cooldown_manager import *

class BlackjackView(View):
    def __init__(self, bot, game):
        super().__init__(timeout=60)
        self.bot = bot
        self.game = game

    async def on_timeout(self):
        # auto-stand on timeout
        if not self.game['finished']:
            await self.game['finish_func']()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.game['player']:
            await interaction.response.send_message("This is not your game.", ephemeral=True)
            return
        if self.game['finished']:
            await interaction.response.send_message("Game already finished.", ephemeral=True)
            return
        # draw card
        card = self.game['deck'].pop()
        self.game['player_cards'].append(card)
        if score_hand(self.game['player_cards']) > 21:
            await self.game['finish_func']()
            await interaction.response.edit_message(embed=self.game['render'](), view=None)
            return
        await interaction.response.edit_message(embed=self.game['render'](), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.blurple)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.game['player']:
            await interaction.response.send_message("This is not your game.", ephemeral=True)
            return
        if self.game['finished']:
            await interaction.response.send_message("Game already finished.", ephemeral=True)
            return
        await self.game['finish_func']()
        await interaction.response.edit_message(embed=self.game['render'](), view=None)


class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # prefer a shared EconomyManager attached to the bot to avoid multiple in-memory copies
        if hasattr(bot, "economy_manager"):
            self.economy = bot.economy_manager
        else:
            self.economy = EconomyManager(bot)
            bot.economy_manager = self.economy
        self.active_games = {}

    def create_game(self, player_id: int, bet: int):
        deck = make_deck()
        player_cards = [deck.pop(), deck.pop()]
        dealer_cards = [deck.pop(), deck.pop()]
        game = {
            'player': player_id,
            'bet': bet,
            'deck': deck,
            'player_cards': player_cards,
            'dealer_cards': dealer_cards,
            'finished': False,
            'result': None,
        }

        def render():
            def fmt(cards, hide_second=False):
                out = []
                for i, c in enumerate(cards):
                    rank, suit = c.split('|', 1)
                    if hide_second and i == 1:
                        out.append('??')
                    else:
                        out.append(f"{rank}{suit}")
                return ' '.join(out)

            pc = fmt(game['player_cards'])
            dc = fmt(game['dealer_cards'], hide_second=True)
            score = score_hand(game['player_cards'])
            embed = discord.Embed(title="Blackjack", color=discord.Color.green())
            embed.add_field(name="Your Hand", value=f"{pc}\nScore: {score}", inline=False)
            embed.add_field(name="Dealer", value=dc, inline=False)
            embed.set_footer(text=f"Bet: {game['bet']}")
            return embed

        async def finish():
            # dealer plays
            game['finished'] = True
            # reveal dealer
            while score_hand(game['dealer_cards']) < 17:
                game['dealer_cards'].append(game['deck'].pop())
            pscore = score_hand(game['player_cards'])
            dscore = score_hand(game['dealer_cards'])
            # determine outcome
            payout = 0
            if pscore > 21:
                game['result'] = 'bust'
                payout = 0
            elif is_blackjack(game['player_cards']) and not is_blackjack(game['dealer_cards']):
                game['result'] = 'blackjack'
                payout = int(game['bet'] * 1.5)
            elif dscore > 21 or pscore > dscore:
                game['result'] = 'win'
                payout = game['bet']
            elif pscore == dscore:
                game['result'] = 'push'
                payout = 0
            else:
                game['result'] = 'lose'
                payout = -game['bet']

            # settle
            if payout > 0:
                self.economy.update_balance(player_id, payout + game['bet'])
            elif payout == 0 and game['result'] == 'push':
                # return bet
                self.economy.update_balance(player_id, game['bet'])
            else:
                # lost, do nothing (bet already deducted)
                pass
            # replace render with final summary
            def final_render():
                pc = ' '.join([f"{r}{s}" for r,s in (c.split('|',1) for c in game['player_cards'])])
                dc = ' '.join([f"{r}{s}" for r,s in (c.split('|',1) for c in game['dealer_cards'])])
                embed = discord.Embed(title="Blackjack - Result", color=discord.Color.blue())
                embed.add_field(name="Your Hand", value=f"{pc}\nScore: {pscore}", inline=False)
                embed.add_field(name="Dealer", value=f"{dc}\nScore: {dscore}", inline=False)
                embed.add_field(name="Result", value=game['result'].upper(), inline=False)
                embed.set_footer(text=f"Bet: {game['bet']}")
                return embed

            game['render'] = final_render
            # remove active game record
            try:
                del self.active_games[player_id]
            except KeyError:
                pass

        game['render'] = render
        game['finish_func'] = finish
        return game

    @app_commands.command(name='blackjack', description='Play a quick blackjack round')
    @app_commands.describe(bet='Amount to wager')
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        COOLDOWN_TIME = 120 # 2 minutes
        # basic validation
        is_valid_user = await check_boost_status(self.bot, interaction)
        if not is_valid_user:
            if await check_cooldown(interaction, COOLDOWN_TIME):
                time_left = await get_remaining_cooldown(interaction, COOLDOWN_TIME)
                await interaction.response.send_message(f"You're on cooldown! Try again in {time_left}.", ephemeral=True)
                return
        bal = self.economy.get_balance(interaction.user.id)
        if bet <= 0:
            await interaction.response.send_message('Bet must be positive.', ephemeral=True)
            return
        if bal < bet:
            await interaction.response.send_message('Insufficient funds.', ephemeral=True)
            return
        if interaction.user.id in self.active_games:
            await interaction.response.send_message('You already have an active game.', ephemeral=True)
            return

        # deduct bet
        self.economy.update_balance(interaction.user.id, -bet)
        game = self.create_game(interaction.user.id, bet)
        self.active_games[interaction.user.id] = game
        view = BlackjackView(self.bot, game)

        await interaction.response.send_message(embed=game['render'](), view=view)
        await set_cooldown(interaction)

async def setup(bot):
    await bot.add_cog(Blackjack(bot))
