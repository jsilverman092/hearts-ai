from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import (
    PublicKnowledge,
    SearchPlayerView,
    build_root_move_candidates,
    build_search_player_view,
)


def _empty_public_knowledge() -> PublicKnowledge:
    return PublicKnowledge(
        played_count_by_suit={suit: 0 for suit in Suit},
        unplayed_count_by_suit={suit: 13 for suit in Suit},
        remaining_cards_by_player={player_id: 13 for player_id in PLAYER_IDS},
        void_suits_by_player={player_id: frozenset() for player_id in PLAYER_IDS},
    )


def test_build_root_move_candidates_orders_cards_deterministically_in_lead_mode() -> None:
    view = SearchPlayerView(
        player_id=PlayerId(0),
        hand=(
            Card(Suit.SPADES, Rank.FIVE),
            Card(Suit.CLUBS, Rank.THREE),
            Card(Suit.HEARTS, Rank.THREE),
        ),
        legal_moves=(
            Card(Suit.SPADES, Rank.FIVE),
            Card(Suit.HEARTS, Rank.THREE),
            Card(Suit.CLUBS, Rank.THREE),
        ),
        current_trick=(),
        taken_tricks={player_id: () for player_id in PLAYER_IDS},
        scores={player_id: 0 for player_id in PLAYER_IDS},
        hearts_broken=False,
        turn=PlayerId(0),
        trick_number=0,
        hand_number=1,
        pass_direction="left",
        pass_applied=True,
        target_score=50,
        config=GameConfig(target_score=50),
        public_knowledge=_empty_public_knowledge(),
    )

    candidates = build_root_move_candidates(view)

    assert tuple(candidate.card for candidate in candidates) == (
        Card(Suit.CLUBS, Rank.THREE),
        Card(Suit.HEARTS, Rank.THREE),
        Card(Suit.SPADES, Rank.FIVE),
    )
    assert all(candidate.mode == "lead" for candidate in candidates)
    assert all(candidate.trick_points_so_far == 0 for candidate in candidates)


def test_build_root_move_candidates_marks_follow_mode_and_led_suit_match() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.THREE), Card(Suit.CLUBS, Rank.SEVEN)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.ACE)],
        PlayerId(2): [Card(Suit.HEARTS, Rank.TWO)],
        PlayerId(3): [Card(Suit.SPADES, Rank.FOUR)],
    }
    state.trick_in_progress = [(PlayerId(1), Card(Suit.CLUBS, Rank.ACE))]
    state.turn = PlayerId(0)
    state.pass_applied = True

    view = build_search_player_view(state=state, player_id=PlayerId(0))
    candidates = build_root_move_candidates(view)

    assert tuple(candidate.card for candidate in candidates) == (
        Card(Suit.CLUBS, Rank.THREE),
        Card(Suit.CLUBS, Rank.SEVEN),
    )
    assert all(candidate.mode == "follow" for candidate in candidates)
    assert all(candidate.follows_led_suit for candidate in candidates)
    assert all(candidate.trick_points_so_far == 0 for candidate in candidates)


def test_build_root_move_candidates_marks_discard_mode_and_trick_points() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.SPADES, Rank.QUEEN), Card(Suit.HEARTS, Rank.THREE)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.ACE)],
        PlayerId(2): [Card(Suit.HEARTS, Rank.KING)],
        PlayerId(3): [Card(Suit.DIAMONDS, Rank.FOUR)],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.CLUBS, Rank.ACE)),
        (PlayerId(2), Card(Suit.HEARTS, Rank.KING)),
    ]
    state.turn = PlayerId(0)
    state.pass_applied = True

    view = build_search_player_view(state=state, player_id=PlayerId(0))
    candidates = build_root_move_candidates(view)

    assert tuple(candidate.card for candidate in candidates) == (
        Card(Suit.HEARTS, Rank.THREE),
        Card(Suit.SPADES, Rank.QUEEN),
    )
    assert all(candidate.mode == "discard" for candidate in candidates)
    assert all(not candidate.follows_led_suit for candidate in candidates)
    assert [candidate.is_point_card for candidate in candidates] == [True, True]
    assert all(candidate.trick_points_so_far == 1 for candidate in candidates)
