import random

import pytest

from hearts_ai.bots.heuristic_bot import HeuristicBot, HeuristicBotV2, HeuristicBotV3
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


def test_heuristic_v2_choose_play_returns_legal_move_and_reason_payload() -> None:
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

    bot = HeuristicBotV2(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(33))
    reason = bot._peek_last_play_reason()

    assert card in legal_moves(state=state, player_id=PlayerId(0))
    assert reason is not None
    assert reason.chosen_card == card
    assert reason.mode == "discard"
    assert len(reason.candidates) == 3


def test_heuristic_v2_choose_play_is_deterministic() -> None:
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

    bot = HeuristicBotV2(player_id=PlayerId(0))
    first = bot.choose_play(state=state, rng=random.Random(44))
    second = bot.choose_play(state=state, rng=random.Random(44))
    assert first == second


def test_heuristic_v2_first_trick_forced_win_sheds_highest_club() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.FOUR), Card(Suit.CLUBS, Rank.EIGHT)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.FOUR)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.THREE)],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.CLUBS, Rank.TWO)),
        (PlayerId(2), Card(Suit.CLUBS, Rank.FOUR)),
    ]
    state.hearts_broken = False
    state.trick_number = 0

    bot = HeuristicBotV2(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(55))

    assert card == Card(Suit.CLUBS, Rank.EIGHT)


def test_heuristic_v2_choose_pass_records_reason_payload() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.TWO),
    ]
    bot = HeuristicBotV2(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(7))
    reason = bot._peek_last_pass_reason()

    assert len(passed) == state.config.pass_count
    assert reason is not None
    assert tuple(passed) == reason.selected_cards


def test_heuristic_v2_avoids_leading_queen_spades_when_lower_spade_available() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.SPADES, Rank.FIVE),
            Card(Suit.SPADES, Rank.NINE),
            Card(Suit.HEARTS, Rank.ACE),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = False
    state.trick_number = 4

    bot = HeuristicBotV2(player_id=PlayerId(0), rollout_samples=0)
    card = bot.choose_play(state=state, rng=random.Random(70))

    assert card == Card(Suit.SPADES, Rank.FIVE)


def test_heuristic_v2_avoids_leading_high_spade_when_lower_spade_available() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.SPADES, Rank.SIX),
            Card(Suit.SPADES, Rank.TEN),
            Card(Suit.HEARTS, Rank.KING),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = False
    state.trick_number = 6

    bot = HeuristicBotV2(player_id=PlayerId(0), rollout_samples=0)
    card = bot.choose_play(state=state, rng=random.Random(71))

    assert card == Card(Suit.SPADES, Rank.SIX)


def test_heuristic_v2_rollout_scores_lead_candidates() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.SPADES, Rank.FIVE),
            Card(Suit.HEARTS, Rank.ACE),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = False
    state.trick_number = 7

    bot = HeuristicBotV2(player_id=PlayerId(0), rollout_samples=5, rollout_weight=0.5)
    bot.choose_play(state=state, rng=random.Random(72))
    reason = bot._peek_last_play_reason()

    assert reason is not None
    assert reason.mode == "lead"

    queen_entry = next(
        candidate
        for candidate in reason.candidates
        if candidate.card == Card(Suit.SPADES, Rank.QUEEN)
    )
    assert abs(queen_entry.rollout_score) > 0.01


def test_heuristic_v2_broken_hearts_prefers_low_heart_escape_over_king_spades() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.HEARTS, Rank.THREE),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = True
    state.trick_number = 8

    bot = HeuristicBotV2(player_id=PlayerId(0))
    card = bot.choose_play(state=state, rng=random.Random(73))

    assert card == Card(Suit.HEARTS, Rank.THREE)


def test_heuristic_v3_preserves_three_hearts_over_dangerous_offsuit_honors() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.HEARTS, Rank.THREE),
        Card(Suit.HEARTS, Rank.FIVE),
        Card(Suit.DIAMONDS, Rank.JACK),
        Card(Suit.CLUBS, Rank.JACK),
        Card(Suit.CLUBS, Rank.TWO),
        Card(Suit.CLUBS, Rank.FOUR),
    ]
    bot = HeuristicBotV3(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(81))

    assert Card(Suit.DIAMONDS, Rank.JACK) in passed
    assert Card(Suit.CLUBS, Rank.JACK) in passed
    assert Card(Suit.HEARTS, Rank.THREE) not in passed


def test_heuristic_v3_passes_queen_spades_when_short_spades() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.NINE),
        Card(Suit.SPADES, Rank.FOUR),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.CLUBS, Rank.JACK),
    ]
    bot = HeuristicBotV3(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(82))

    assert Card(Suit.SPADES, Rank.QUEEN) in passed


def test_heuristic_v3_keeps_queen_spades_with_long_spade_shape() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.NINE),
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.SPADES, Rank.FIVE),
        Card(Suit.SPADES, Rank.THREE),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.ACE),
    ]
    bot = HeuristicBotV3(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(83))

    assert Card(Suit.SPADES, Rank.QUEEN) not in passed


def test_heuristic_v3_keeps_as_ks_with_cover_when_no_queen_spades() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.SPADES, Rank.NINE),
        Card(Suit.SPADES, Rank.SIX),
        Card(Suit.SPADES, Rank.THREE),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.QUEEN),
    ]
    bot = HeuristicBotV3(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(84))

    assert Card(Suit.SPADES, Rank.ACE) not in passed
    assert Card(Suit.SPADES, Rank.KING) not in passed


def test_heuristic_v3_choose_pass_records_reason_payload() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.NINE),
        Card(Suit.SPADES, Rank.FOUR),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.CLUBS, Rank.JACK),
    ]
    bot = HeuristicBotV3(player_id=PlayerId(0))

    passed = bot.choose_pass(hand=hand, state=state, rng=random.Random(85))
    reason = bot._peek_last_pass_reason()

    assert len(passed) == state.config.pass_count
    assert reason is not None
    assert tuple(passed) == reason.selected_cards


def test_heuristic_v3_avoids_short_qs_shape_spade_lead_when_non_spade_available() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.SPADES, Rank.SEVEN),
            Card(Suit.SPADES, Rank.FOUR),
            Card(Suit.DIAMONDS, Rank.JACK),
            Card(Suit.CLUBS, Rank.KING),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = False
    state.trick_number = 6

    bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0)
    card = bot.choose_play(state=state, rng=random.Random(90))

    assert card == Card(Suit.DIAMONDS, Rank.JACK)


def test_heuristic_v3_avoids_spade_lead_with_fragile_ak_protection_shape() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.ACE),
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.SPADES, Rank.FIVE),
            Card(Suit.DIAMONDS, Rank.JACK),
            Card(Suit.CLUBS, Rank.KING),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = False
    state.trick_number = 6

    bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0)
    card = bot.choose_play(state=state, rng=random.Random(91))

    assert card == Card(Suit.DIAMONDS, Rank.JACK)


def test_heuristic_v3_short_qs_shape_penalty_is_not_absolute_on_forced_spade_lead() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.SPADES, Rank.SEVEN),
            Card(Suit.SPADES, Rank.FOUR),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = False
    state.trick_number = 7

    bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0)
    card = bot.choose_play(state=state, rng=random.Random(92))

    assert card == Card(Suit.SPADES, Rank.FOUR)


def test_heuristic_v3_prefers_jack_spades_over_ten_clubs_when_qs_unseen() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.SPADES, Rank.JACK),
            Card(Suit.CLUBS, Rank.TEN),
            Card(Suit.HEARTS, Rank.KING),
        ],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.hearts_broken = False
    state.trick_number = 5

    bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0)
    card = bot.choose_play(state=state, rng=random.Random(93))

    assert card == Card(Suit.SPADES, Rank.JACK)
