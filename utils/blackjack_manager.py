import random
from typing import List

RANKS = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
# replace suits with Dew-can themed emojis used in the bot
SUITS = [
    "<:happydewyear:629161277536731157>",
    "<:mauican:661085431252647947>",
    "<:dewcan:653121636551098379>",
    "<:bajablastcan:1427060298510106766>",
]

def make_deck(decks: int = 1) :
    # store cards as "RANK|SUIT" so suits (which may be multi-char emojis) can be parsed reliably
    deck = [f"{r}|{s}" for r in RANKS for s in SUITS] * decks
    random.shuffle(deck)
    return deck

def card_value(card: str) :
    # card format is "RANK|SUIT"; split on the first '|'
    rank, _ = card.split("|", 1)
    if rank in ("J","Q","K"):
        return [10]
    if rank == "A":
        return [1,11]
    return [int(rank)]

def score_hand(cards: List[str]) :
    # compute best score <=21 or minimum otherwise
    totals = [0]
    for c in cards:
        vals = card_value(c)
        new = []
        for t in totals:
            for v in vals:
                new.append(t+v)
        totals = new
    # choose best <=21
    valid = [t for t in totals if t <= 21]
    if valid:
        return max(valid)
    return min(totals)

def is_blackjack(cards: List[str]) :
    return len(cards) == 2 and (11 in sum([card_value(c) for c in cards], [])) and any(v==10 for c in cards for v in card_value(c))
