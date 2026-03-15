import random

import pytest

from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.bots.search import SearchBotConfig, SearchBotV1
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PlayerId


def test_search_bot_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        SearchBotConfig(world_count=0)

    with pytest.raises(ValueError):
        SearchBotConfig(playout_seed_offset=-1)


def test_search_bot_v1_choose_pass_matches_heuristic_v3() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.TWO),
    ]
    search_bot = SearchBotV1(player_id=PlayerId(0))
    heuristic_bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0, rollout_weight=0.0)

    search_pass = search_bot.choose_pass(hand=hand, state=state, rng=random.Random(7))
    heuristic_pass = heuristic_bot.choose_pass(hand=hand, state=state, rng=random.Random(7))

    assert search_pass == heuristic_pass
    assert search_bot.peek_last_decision_reason("pass") == heuristic_bot.peek_last_decision_reason("pass")


def test_search_bot_v1_choose_play_returns_legal_move() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.SPADES, Rank.THREE), Card(Suit.HEARTS, Rank.QUEEN)],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.FOUR)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.SIX)],
    }
    state.trick_in_progress = [(PlayerId(1), Card(Suit.SPADES, Rank.KING))]
    state.hearts_broken = True
    state.turn = PlayerId(0)
    state.trick_number = 3
    state.pass_applied = True

    bot = SearchBotV1(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(123))

    assert card in legal_moves(state=state, player_id=PlayerId(0))
