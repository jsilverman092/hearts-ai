import random

import pytest

from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.errors import IllegalMoveError, InvalidStateError
from hearts_ai.engine.game import apply_pass, deal, is_game_over, is_hand_over, new_game, play_card
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId


def test_new_game_deals_cards_and_sets_opening_turn() -> None:
    state = new_game(rng=random.Random(1))

    assert state.hand_number == 1
    assert state.pass_direction == "left"
    assert state.pass_applied is False
    assert state.trick_number == 0
    assert state.hearts_broken is False
    assert sum(len(hand) for hand in state.hands.values()) == 52
    assert all(len(state.hands[player_id]) == 13 for player_id in PLAYER_IDS)
    assert Card(Suit.CLUBS, Rank.TWO) in state.hands[state.turn]


def test_deal_requires_current_hand_to_be_over() -> None:
    state = new_game(rng=random.Random(2))
    with pytest.raises(InvalidStateError):
        deal(state=state, rng=random.Random(3))


def test_apply_pass_left_rotates_cards_between_players() -> None:
    config = GameConfig(pass_directions=("left",))
    state = GameState(config=config)
    deck = make_deck()
    for index, player_id in enumerate(PLAYER_IDS):
        state.hands[player_id] = sorted(deck[index * 13 : (index + 1) * 13])
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = False

    pass_map = {
        PlayerId(0): [
            Card(Suit.CLUBS, Rank.TWO),
            Card(Suit.CLUBS, Rank.THREE),
            Card(Suit.CLUBS, Rank.FOUR),
        ],
        PlayerId(1): [
            Card(Suit.DIAMONDS, Rank.TWO),
            Card(Suit.DIAMONDS, Rank.THREE),
            Card(Suit.DIAMONDS, Rank.FOUR),
        ],
        PlayerId(2): [
            Card(Suit.HEARTS, Rank.TWO),
            Card(Suit.HEARTS, Rank.THREE),
            Card(Suit.HEARTS, Rank.FOUR),
        ],
        PlayerId(3): [
            Card(Suit.SPADES, Rank.TWO),
            Card(Suit.SPADES, Rank.THREE),
            Card(Suit.SPADES, Rank.FOUR),
        ],
    }

    apply_pass(state=state, pass_map=pass_map)

    assert state.pass_applied is True
    assert all(len(state.hands[player_id]) == 13 for player_id in PLAYER_IDS)
    assert Card(Suit.CLUBS, Rank.TWO) in state.hands[PlayerId(1)]
    assert Card(Suit.DIAMONDS, Rank.TWO) in state.hands[PlayerId(2)]
    assert Card(Suit.HEARTS, Rank.TWO) in state.hands[PlayerId(3)]
    assert Card(Suit.SPADES, Rank.TWO) in state.hands[PlayerId(0)]
    assert state.turn == PlayerId(1)


def test_play_card_advances_turn_and_awards_trick() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.DIAMONDS, Rank.TWO)],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.KING)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.ACE)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.THREE)],
    }
    state.turn = PlayerId(0)
    state.trick_number = 1
    state.pass_direction = "hold"
    state.pass_applied = True
    state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}

    play_card(state=state, player_id=PlayerId(0), card=Card(Suit.DIAMONDS, Rank.TWO))
    assert state.turn == PlayerId(1)
    play_card(state=state, player_id=PlayerId(1), card=Card(Suit.DIAMONDS, Rank.KING))
    assert state.turn == PlayerId(2)
    play_card(state=state, player_id=PlayerId(2), card=Card(Suit.CLUBS, Rank.ACE))
    assert state.turn == PlayerId(3)
    play_card(state=state, player_id=PlayerId(3), card=Card(Suit.DIAMONDS, Rank.THREE))

    assert state.turn == PlayerId(1)
    assert state.trick_number == 2
    assert state.trick_in_progress == []
    assert len(state.taken_tricks[PlayerId(1)]) == 1
    assert is_hand_over(state) is True


def test_play_card_rejects_wrong_turn() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.DIAMONDS, Rank.TWO)],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.THREE)],
        PlayerId(2): [Card(Suit.DIAMONDS, Rank.FOUR)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.FIVE)],
    }
    state.turn = PlayerId(0)
    state.trick_number = 1
    state.pass_direction = "hold"
    state.pass_applied = True

    with pytest.raises(IllegalMoveError):
        play_card(state=state, player_id=PlayerId(1), card=Card(Suit.DIAMONDS, Rank.THREE))


def test_is_game_over_uses_target_score() -> None:
    state = GameState(config=GameConfig(target_score=50))
    state.scores[PlayerId(2)] = 50
    assert is_game_over(state) is True
