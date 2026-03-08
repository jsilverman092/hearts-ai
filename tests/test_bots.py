import random

import pytest

from hearts_ai.bots.heuristic_bot import HeuristicBot
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


def test_heuristic_bot_choose_pass_prioritizes_spade_dangers() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.TWO),
    ]
    bot = HeuristicBot(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(7))

    assert passed == [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.SPADES, Rank.ACE),
    ]


def test_heuristic_bot_choose_pass_keeps_low_spades_over_offsuit_cards() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.FOUR),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.HEARTS, Rank.THREE),
        Card(Suit.HEARTS, Rank.TWO),
    ]
    bot = HeuristicBot(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(13))

    assert Card(Suit.SPADES, Rank.FOUR) not in passed
    assert Card(Suit.CLUBS, Rank.ACE) in passed
    assert all(card in hand for card in passed)


def test_heuristic_bot_choose_pass_hold_returns_empty() -> None:
    state = GameState()
    state.pass_direction = "hold"
    hand = [Card(Suit.HEARTS, Rank.ACE), Card(Suit.CLUBS, Rank.TWO)]
    bot = HeuristicBot(player_id=PlayerId(0))

    assert bot.choose_pass(hand=hand, state=state, rng=random.Random(5)) == []


def test_heuristic_bot_choose_pass_raises_if_pass_count_exceeds_hand_size() -> None:
    state = GameState()
    state.pass_direction = "left"
    state.config.pass_count = 3
    hand = [Card(Suit.CLUBS, Rank.TWO), Card(Suit.DIAMONDS, Rank.THREE)]
    bot = HeuristicBot(player_id=PlayerId(0))

    with pytest.raises(InvalidStateError):
        bot.choose_pass(hand=hand, state=state, rng=random.Random(2))


def test_heuristic_bot_choose_play_leads_low_non_heart() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.HEARTS, Rank.TWO),
            Card(Suit.CLUBS, Rank.TEN),
            Card(Suit.DIAMONDS, Rank.THREE),
            Card(Suit.SPADES, Rank.FOUR),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.DIAMONDS, Rank.TWO)],
        PlayerId(3): [Card(Suit.SPADES, Rank.TWO)],
    }
    state.hearts_broken = False
    state.trick_number = 1

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(2))

    assert card == Card(Suit.DIAMONDS, Rank.THREE)
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_choose_play_first_trick_returns_two_of_clubs() -> None:
    two_clubs = Card(Suit.CLUBS, Rank.TWO)
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.HEARTS, Rank.KING), two_clubs],
        PlayerId(1): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(2): [Card(Suit.SPADES, Rank.FOUR)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.FIVE)],
    }
    state.hearts_broken = False
    state.trick_number = 0

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(1))

    assert card == two_clubs
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_first_trick_forced_win_sheds_highest_club() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.FOUR), Card(Suit.CLUBS, Rank.EIGHT)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.KING)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.THREE)],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.CLUBS, Rank.TWO)),
        (PlayerId(2), Card(Suit.CLUBS, Rank.FOUR)),
    ]
    state.hearts_broken = False
    state.trick_number = 0

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(10))

    assert card == Card(Suit.CLUBS, Rank.EIGHT)
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_first_trick_prefers_highest_losing_club_when_possible() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.SEVEN), Card(Suit.CLUBS, Rank.JACK)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.EIGHT)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.THREE)],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.CLUBS, Rank.TWO)),
        (PlayerId(2), Card(Suit.CLUBS, Rank.EIGHT)),
    ]
    state.hearts_broken = False
    state.trick_number = 0

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(11))

    assert card == Card(Suit.CLUBS, Rank.SEVEN)
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_choose_play_sheds_queen_of_spades_offsuit() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.THREE),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.KING)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.THREE)],
    }
    state.trick_in_progress = [(PlayerId(1), Card(Suit.CLUBS, Rank.KING))]
    state.hearts_broken = False
    state.trick_number = 5

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(9))

    assert card == Card(Suit.SPADES, Rank.QUEEN)
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_choose_play_without_points_prefers_high_losing_follow() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.SPADES, Rank.THREE), Card(Suit.SPADES, Rank.QUEEN)],
        PlayerId(1): [Card(Suit.SPADES, Rank.KING)],
        PlayerId(2): [Card(Suit.DIAMONDS, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.TWO)],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.SPADES, Rank.KING)),
        (PlayerId(2), Card(Suit.DIAMONDS, Rank.FIVE)),
    ]
    state.hearts_broken = True
    state.trick_number = 4

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(6))

    assert card == Card(Suit.SPADES, Rank.QUEEN)
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_choose_play_with_points_prefers_high_losing_follow() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.SPADES, Rank.THREE), Card(Suit.SPADES, Rank.QUEEN)],
        PlayerId(1): [Card(Suit.SPADES, Rank.KING)],
        PlayerId(2): [Card(Suit.HEARTS, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.TWO)],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.SPADES, Rank.KING)),
        (PlayerId(2), Card(Suit.HEARTS, Rank.FIVE)),
    ]
    state.hearts_broken = True
    state.trick_number = 4

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(3))

    assert card == Card(Suit.SPADES, Rank.QUEEN)
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_choose_play_with_points_and_no_losing_card_chooses_lowest_follow() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.SPADES, Rank.KING), Card(Suit.SPADES, Rank.ACE)],
        PlayerId(1): [Card(Suit.SPADES, Rank.QUEEN)],
        PlayerId(2): [Card(Suit.HEARTS, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.TWO)],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.SPADES, Rank.QUEEN)),
        (PlayerId(2), Card(Suit.HEARTS, Rank.FIVE)),
    ]
    state.hearts_broken = True
    state.trick_number = 6

    bot = HeuristicBot(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(4))

    assert card == Card(Suit.SPADES, Rank.KING)
    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_heuristic_bot_choose_play_is_deterministic() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.THREE),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.KING)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.THREE)],
    }
    state.trick_in_progress = [(PlayerId(1), Card(Suit.CLUBS, Rank.KING))]
    state.hearts_broken = False
    state.trick_number = 5

    bot = HeuristicBot(player_id=PlayerId(0))
    first = bot.choose_play(state=state, rng=random.Random(1))
    second = bot.choose_play(state=state, rng=random.Random(999))

    assert first == second


def test_heuristic_bot_choose_play_raises_without_legal_moves() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.FOUR)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.SIX)],
    }
    bot = HeuristicBot(player_id=PlayerId(0))

    with pytest.raises(InvalidStateError):
        bot.choose_play(state=state, rng=random.Random(1))
