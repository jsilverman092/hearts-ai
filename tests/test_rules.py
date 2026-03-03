from dataclasses import dataclass

import pytest

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import IllegalMoveError, InvalidStateError
from hearts_ai.engine.rules import legal_moves, trick_winner, validate_move
from hearts_ai.engine.types import Deal, PlayerId, Trick


@dataclass
class StubRulesState:
    hands: Deal
    trick_in_progress: Trick
    hearts_broken: bool
    trick_number: int


def test_opening_lead_must_be_two_of_clubs() -> None:
    two_clubs = Card(Suit.CLUBS, Rank.TWO)
    state = StubRulesState(
        hands={
            PlayerId(0): [Card(Suit.HEARTS, Rank.ACE), two_clubs],
            PlayerId(1): [Card(Suit.CLUBS, Rank.THREE)],
            PlayerId(2): [Card(Suit.SPADES, Rank.FOUR)],
            PlayerId(3): [Card(Suit.DIAMONDS, Rank.FIVE)],
        },
        trick_in_progress=[],
        hearts_broken=False,
        trick_number=0,
    )

    assert legal_moves(state=state, player_id=PlayerId(0)) == [two_clubs]


def test_opening_lead_from_player_without_two_clubs_is_invalid() -> None:
    state = StubRulesState(
        hands={
            PlayerId(0): [Card(Suit.CLUBS, Rank.THREE)],
            PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
            PlayerId(2): [Card(Suit.SPADES, Rank.FOUR)],
            PlayerId(3): [Card(Suit.DIAMONDS, Rank.FIVE)],
        },
        trick_in_progress=[],
        hearts_broken=False,
        trick_number=0,
    )

    with pytest.raises(InvalidStateError):
        legal_moves(state=state, player_id=PlayerId(0))


def test_follow_suit_is_required_when_possible() -> None:
    spade_three = Card(Suit.SPADES, Rank.THREE)
    state = StubRulesState(
        hands={
            PlayerId(0): [Card(Suit.CLUBS, Rank.TWO)] * 10,
            PlayerId(1): [Card(Suit.DIAMONDS, Rank.THREE)] * 10,
            PlayerId(2): [spade_three, Card(Suit.HEARTS, Rank.QUEEN)],
            PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)] * 10,
        },
        trick_in_progress=[(PlayerId(0), Card(Suit.SPADES, Rank.KING))],
        hearts_broken=True,
        trick_number=1,
    )

    assert legal_moves(state=state, player_id=PlayerId(2)) == [spade_three]


def test_cannot_lead_hearts_until_broken_unless_only_hearts() -> None:
    state = StubRulesState(
        hands={
            PlayerId(0): [Card(Suit.HEARTS, Rank.FIVE), Card(Suit.CLUBS, Rank.ACE)],
            PlayerId(1): [Card(Suit.DIAMONDS, Rank.TWO)] * 10,
            PlayerId(2): [Card(Suit.SPADES, Rank.THREE)] * 10,
            PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)] * 10,
        },
        trick_in_progress=[],
        hearts_broken=False,
        trick_number=1,
    )

    assert legal_moves(state=state, player_id=PlayerId(0)) == [Card(Suit.CLUBS, Rank.ACE)]

    state.hands[PlayerId(0)] = [Card(Suit.HEARTS, Rank.FIVE), Card(Suit.HEARTS, Rank.SIX)]
    assert legal_moves(state=state, player_id=PlayerId(0)) == state.hands[PlayerId(0)]


def test_first_trick_forbids_points_when_non_point_exists() -> None:
    diamond_ten = Card(Suit.DIAMONDS, Rank.TEN)
    state = StubRulesState(
        hands={
            PlayerId(0): [Card(Suit.CLUBS, Rank.THREE)] * 12,
            PlayerId(1): [Card(Suit.HEARTS, Rank.FIVE), Card(Suit.SPADES, Rank.QUEEN), diamond_ten],
            PlayerId(2): [Card(Suit.SPADES, Rank.ACE)] * 12,
            PlayerId(3): [Card(Suit.DIAMONDS, Rank.KING)] * 12,
        },
        trick_in_progress=[(PlayerId(0), Card(Suit.CLUBS, Rank.TWO))],
        hearts_broken=False,
        trick_number=0,
    )

    assert legal_moves(state=state, player_id=PlayerId(1)) == [diamond_ten]


def test_first_trick_allows_points_when_forced() -> None:
    queen_spades = Card(Suit.SPADES, Rank.QUEEN)
    heart_five = Card(Suit.HEARTS, Rank.FIVE)
    state = StubRulesState(
        hands={
            PlayerId(0): [Card(Suit.CLUBS, Rank.THREE)] * 12,
            PlayerId(1): [queen_spades, heart_five],
            PlayerId(2): [Card(Suit.SPADES, Rank.ACE)] * 12,
            PlayerId(3): [Card(Suit.DIAMONDS, Rank.KING)] * 12,
        },
        trick_in_progress=[(PlayerId(0), Card(Suit.CLUBS, Rank.TWO))],
        hearts_broken=False,
        trick_number=0,
    )

    assert legal_moves(state=state, player_id=PlayerId(1)) == [queen_spades, heart_five]


def test_trick_winner_uses_led_suit_high_card() -> None:
    trick: Trick = [
        (PlayerId(0), Card(Suit.DIAMONDS, Rank.TEN)),
        (PlayerId(1), Card(Suit.SPADES, Rank.ACE)),
        (PlayerId(2), Card(Suit.DIAMONDS, Rank.ACE)),
        (PlayerId(3), Card(Suit.DIAMONDS, Rank.KING)),
    ]
    assert trick_winner(trick) == PlayerId(2)


def test_validate_move_raises_for_illegal_card() -> None:
    state = StubRulesState(
        hands={
            PlayerId(0): [Card(Suit.SPADES, Rank.THREE), Card(Suit.HEARTS, Rank.QUEEN)],
            PlayerId(1): [Card(Suit.DIAMONDS, Rank.THREE)] * 10,
            PlayerId(2): [Card(Suit.CLUBS, Rank.FOUR)] * 10,
            PlayerId(3): [Card(Suit.SPADES, Rank.FIVE)] * 10,
        },
        trick_in_progress=[(PlayerId(1), Card(Suit.SPADES, Rank.KING))],
        hearts_broken=True,
        trick_number=2,
    )

    with pytest.raises(IllegalMoveError):
        validate_move(state=state, player_id=PlayerId(0), card=Card(Suit.HEARTS, Rank.QUEEN))
