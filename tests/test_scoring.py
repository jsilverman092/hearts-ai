import pytest

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.game import play_card, score_hand
from hearts_ai.engine.scoring import SHOOT_THE_MOON_POINTS, card_points, hand_points, trick_points
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId


def _empty_taken_tricks() -> dict[PlayerId, list[list[tuple[PlayerId, Card]]]]:
    return {player_id: [] for player_id in PLAYER_IDS}


def test_card_and_trick_points() -> None:
    assert card_points(Card(Suit.HEARTS, Rank.ACE)) == 1
    assert card_points(Card(Suit.SPADES, Rank.QUEEN)) == 13
    assert card_points(Card(Suit.CLUBS, Rank.ACE)) == 0

    trick = [
        (PlayerId(0), Card(Suit.HEARTS, Rank.THREE)),
        (PlayerId(1), Card(Suit.SPADES, Rank.QUEEN)),
        (PlayerId(2), Card(Suit.CLUBS, Rank.KING)),
    ]
    assert trick_points(trick) == 14


def test_hand_points_standard_scoring() -> None:
    taken_tricks = _empty_taken_tricks()
    taken_tricks[PlayerId(0)].append(
        [
            (PlayerId(0), Card(Suit.HEARTS, Rank.THREE)),
            (PlayerId(1), Card(Suit.SPADES, Rank.QUEEN)),
        ]
    )
    taken_tricks[PlayerId(2)].append([(PlayerId(3), Card(Suit.HEARTS, Rank.FIVE))])

    assert hand_points(taken_tricks) == {
        PlayerId(0): 14,
        PlayerId(1): 0,
        PlayerId(2): 1,
        PlayerId(3): 0,
    }


def test_hand_points_shoot_the_moon() -> None:
    taken_tricks = _empty_taken_tricks()
    taken_tricks[PlayerId(3)] = [[(PlayerId(0), Card(Suit.HEARTS, rank))] for rank in Rank]
    taken_tricks[PlayerId(3)].append([(PlayerId(1), Card(Suit.SPADES, Rank.QUEEN))])

    assert hand_points(taken_tricks) == {
        PlayerId(0): SHOOT_THE_MOON_POINTS,
        PlayerId(1): SHOOT_THE_MOON_POINTS,
        PlayerId(2): SHOOT_THE_MOON_POINTS,
        PlayerId(3): 0,
    }


def test_score_hand_updates_state_once() -> None:
    state = GameState()
    state.hands = {player_id: [] for player_id in PLAYER_IDS}
    state.taken_tricks = _empty_taken_tricks()
    state.taken_tricks[PlayerId(1)] = [[(PlayerId(0), Card(Suit.HEARTS, Rank.ACE))]]

    delta = score_hand(state)
    assert delta[PlayerId(1)] == 1
    assert state.scores[PlayerId(1)] == 1
    assert state.hand_scored is True

    with pytest.raises(InvalidStateError):
        score_hand(state)


def test_final_trick_auto_scores_hand() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.HEARTS, Rank.TWO)],
        PlayerId(1): [Card(Suit.SPADES, Rank.QUEEN)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.TWO)],
    }
    state.turn = PlayerId(0)
    state.trick_number = 12
    state.pass_direction = "hold"
    state.pass_applied = True
    state.taken_tricks = _empty_taken_tricks()

    play_card(state=state, player_id=PlayerId(0), card=Card(Suit.HEARTS, Rank.TWO))
    play_card(state=state, player_id=PlayerId(1), card=Card(Suit.SPADES, Rank.QUEEN))
    play_card(state=state, player_id=PlayerId(2), card=Card(Suit.CLUBS, Rank.TWO))
    play_card(state=state, player_id=PlayerId(3), card=Card(Suit.DIAMONDS, Rank.TWO))

    assert state.hand_scored is True
    assert state.scores == {
        PlayerId(0): 14,
        PlayerId(1): 0,
        PlayerId(2): 0,
        PlayerId(3): 0,
    }
