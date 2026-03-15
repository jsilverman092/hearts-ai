from __future__ import annotations

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import build_public_knowledge


def _fixture_state_with_public_history() -> GameState:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.CLUBS, Rank.THREE),
            Card(Suit.HEARTS, Rank.NINE),
        ],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.FOUR)],
        PlayerId(2): [Card(Suit.SPADES, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.SIX)],
    }
    state.taken_tricks = {
        PlayerId(0): [],
        PlayerId(1): [],
        PlayerId(2): [
            [
                (PlayerId(0), Card(Suit.DIAMONDS, Rank.TWO)),
                (PlayerId(1), Card(Suit.DIAMONDS, Rank.FIVE)),
                (PlayerId(2), Card(Suit.HEARTS, Rank.THREE)),
                (PlayerId(3), Card(Suit.DIAMONDS, Rank.SEVEN)),
            ],
            [
                (PlayerId(1), Card(Suit.SPADES, Rank.TEN)),
                (PlayerId(2), Card(Suit.SPADES, Rank.ACE)),
                (PlayerId(3), Card(Suit.SPADES, Rank.QUEEN)),
                (PlayerId(0), Card(Suit.SPADES, Rank.KING)),
            ],
        ],
        PlayerId(3): [],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.CLUBS, Rank.ACE)),
    ]
    state.turn = PlayerId(0)
    state.trick_number = 2
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = True
    return state


def test_build_public_knowledge_is_stable_for_same_state() -> None:
    state = _fixture_state_with_public_history()

    first = build_public_knowledge(state=state)
    second = build_public_knowledge(state=state)

    assert first == second


def test_build_public_knowledge_is_invariant_to_hidden_opponent_assignment() -> None:
    def build_state(
        *,
        p1_hand: list[Card],
        p2_hand: list[Card],
        p3_hand: list[Card],
    ) -> GameState:
        state = GameState()
        state.hands = {
            PlayerId(0): [
                Card(Suit.CLUBS, Rank.THREE),
                Card(Suit.HEARTS, Rank.NINE),
            ],
            PlayerId(1): p1_hand,
            PlayerId(2): p2_hand,
            PlayerId(3): p3_hand,
        }
        state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}
        state.scores = {player_id: 0 for player_id in PLAYER_IDS}
        state.turn = PlayerId(0)
        state.trick_number = 2
        state.hand_number = 1
        state.pass_direction = "left"
        state.pass_applied = True
        return state

    state_a = build_state(
        p1_hand=[Card(Suit.DIAMONDS, Rank.FOUR), Card(Suit.SPADES, Rank.FIVE)],
        p2_hand=[Card(Suit.CLUBS, Rank.SIX), Card(Suit.DIAMONDS, Rank.SEVEN)],
        p3_hand=[Card(Suit.HEARTS, Rank.TEN), Card(Suit.SPADES, Rank.JACK)],
    )
    state_b = build_state(
        p1_hand=[Card(Suit.HEARTS, Rank.TEN), Card(Suit.SPADES, Rank.JACK)],
        p2_hand=[Card(Suit.DIAMONDS, Rank.FOUR), Card(Suit.SPADES, Rank.FIVE)],
        p3_hand=[Card(Suit.CLUBS, Rank.SIX), Card(Suit.DIAMONDS, Rank.SEVEN)],
    )

    assert build_public_knowledge(state=state_a) == build_public_knowledge(state=state_b)


def test_build_public_knowledge_tracks_remaining_ranks_voids_and_opponent_constraints() -> None:
    state = _fixture_state_with_public_history()
    knowledge = build_public_knowledge(state=state)

    assert knowledge.qs_live is False
    assert knowledge.played_count_by_suit[Suit.SPADES] == 4
    assert knowledge.unplayed_count_by_suit[Suit.HEARTS] == 12
    assert knowledge.remaining_ranks_by_suit[Suit.SPADES] == (2, 3, 4, 5, 6, 7, 8, 9, 11)
    assert knowledge.lowest_remaining_rank_by_suit[Suit.SPADES] == 2
    assert knowledge.highest_remaining_rank_by_suit[Suit.SPADES] == 11
    assert knowledge.player_is_void(player_id=PlayerId(2), suit=Suit.DIAMONDS) is True

    possible_for_p2 = knowledge.possible_unplayed_cards_for_opponent(
        player_id=PlayerId(2),
        own_hand=state.hands[PlayerId(0)],
    )
    impossible_for_p2 = knowledge.impossible_unplayed_cards_for_opponent(
        player_id=PlayerId(2),
        own_hand=state.hands[PlayerId(0)],
    )

    assert Card(Suit.DIAMONDS, Rank.ACE) not in possible_for_p2
    assert Card(Suit.HEARTS, Rank.NINE) not in possible_for_p2
    assert Card(Suit.DIAMONDS, Rank.ACE) in impossible_for_p2
    assert Card(Suit.HEARTS, Rank.NINE) in impossible_for_p2
    assert Card(Suit.CLUBS, Rank.TWO) in possible_for_p2


def test_public_knowledge_detects_suit_exhausted_outside_own_hand() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.CLUBS, Rank.TWO),
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.ACE),
        ],
        PlayerId(1): [Card(Suit.SPADES, Rank.TWO)],
        PlayerId(2): [Card(Suit.SPADES, Rank.THREE)],
        PlayerId(3): [Card(Suit.SPADES, Rank.FOUR)],
    }
    state.taken_tricks = {
        PlayerId(0): [
            [
                (PlayerId(0), Card(Suit.HEARTS, Rank.TWO)),
                (PlayerId(1), Card(Suit.HEARTS, Rank.THREE)),
                (PlayerId(2), Card(Suit.HEARTS, Rank.FOUR)),
                (PlayerId(3), Card(Suit.HEARTS, Rank.FIVE)),
            ],
            [
                (PlayerId(0), Card(Suit.HEARTS, Rank.SIX)),
                (PlayerId(1), Card(Suit.HEARTS, Rank.SEVEN)),
                (PlayerId(2), Card(Suit.HEARTS, Rank.EIGHT)),
                (PlayerId(3), Card(Suit.HEARTS, Rank.NINE)),
            ],
            [
                (PlayerId(0), Card(Suit.HEARTS, Rank.TEN)),
                (PlayerId(1), Card(Suit.HEARTS, Rank.JACK)),
                (PlayerId(2), Card(Suit.HEARTS, Rank.QUEEN)),
                (PlayerId(3), Card(Suit.CLUBS, Rank.THREE)),
            ],
        ],
        PlayerId(1): [],
        PlayerId(2): [],
        PlayerId(3): [],
    }
    state.pass_applied = True
    knowledge = build_public_knowledge(state=state)

    assert knowledge.remaining_ranks_by_suit[Suit.HEARTS] == (13, 14)
    assert knowledge.suit_exhausted_outside_hand(
        suit=Suit.HEARTS,
        own_hand=state.hands[PlayerId(0)],
    ) is True
    assert knowledge.suit_exhausted_outside_hand(
        suit=Suit.CLUBS,
        own_hand=state.hands[PlayerId(0)],
    ) is False
