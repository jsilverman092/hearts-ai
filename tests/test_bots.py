import random

import pytest

from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PlayerId


def test_random_bot_choose_play_returns_legal_move() -> None:
    forced_card = Card(Suit.SPADES, Rank.THREE)
    state = GameState()
    state.hands = {
        PlayerId(0): [forced_card, Card(Suit.HEARTS, Rank.QUEEN)],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.FOUR)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.SIX)],
    }
    state.trick_in_progress = [(PlayerId(1), Card(Suit.SPADES, Rank.KING))]
    state.hearts_broken = True
    state.trick_number = 3

    bot = RandomBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(123))

    assert card == forced_card
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_random_bot_choose_pass_returns_valid_cards() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.CLUBS, Rank.TWO),
        Card(Suit.CLUBS, Rank.THREE),
        Card(Suit.CLUBS, Rank.FOUR),
        Card(Suit.CLUBS, Rank.FIVE),
        Card(Suit.CLUBS, Rank.SIX),
    ]
    bot = RandomBot(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(7))

    assert len(passed) == state.config.pass_count
    assert len(set(passed)) == state.config.pass_count
    assert all(card in hand for card in passed)


def test_random_bot_choose_pass_hold_returns_empty() -> None:
    state = GameState()
    state.pass_direction = "hold"
    hand = [Card(Suit.HEARTS, Rank.ACE), Card(Suit.CLUBS, Rank.TWO)]
    bot = RandomBot(player_id=PlayerId(0))

    assert bot.choose_pass(hand=hand, state=state, rng=random.Random(5)) == []


def test_random_bot_choose_play_raises_without_legal_moves() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.FOUR)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.SIX)],
    }
    bot = RandomBot(player_id=PlayerId(0))

    with pytest.raises(InvalidStateError):
        bot.choose_play(state=state, rng=random.Random(1))
