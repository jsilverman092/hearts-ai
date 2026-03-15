from __future__ import annotations

from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import (
    DeterminizedWorldSet,
    ImpossibleWorldError,
    PublicKnowledge,
    SearchPlayerView,
    SeatPrivateKnowledge,
    build_search_player_view,
    sample_determinized_world,
    sample_determinized_worlds,
)


def test_sample_determinized_worlds_preserves_card_conservation_and_private_pass_facts() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    passed_card = Card(Suit.DIAMONDS, Rank.TWO)
    view = build_search_player_view(
        state=state,
        player_id=PlayerId(0),
        private_knowledge=SeatPrivateKnowledge(
            passed_cards_by_recipient={PlayerId(1): (passed_card,)}
        ),
    )

    world_set = sample_determinized_worlds(view=view, seed=19, world_count=4)

    assert isinstance(world_set, DeterminizedWorldSet)
    assert world_set.root_player_id == PlayerId(0)
    assert world_set.base_seed == 19
    assert len(world_set.worlds) == 4

    expected_deck = set(make_deck())
    for index, world in enumerate(world_set.worlds):
        assert world.root_player_id == PlayerId(0)
        assert world.sample_index == index
        assert passed_card in world.hidden_hands[PlayerId(1)]
        assert tuple(world.state.hands[PlayerId(0)]) == tuple(sorted(view.hand))
        assert all(len(world.state.hands[player_id]) == 13 for player_id in PLAYER_IDS)

        all_hidden_cards = [card for player_id in PLAYER_IDS for card in world.state.hands[player_id]]
        assert len(all_hidden_cards) == 52
        assert len(set(all_hidden_cards)) == 52
        assert set(all_hidden_cards) == expected_deck


def test_sample_determinized_worlds_are_fixed_seed_deterministic() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    view = build_search_player_view(state=state, player_id=PlayerId(0))

    first = sample_determinized_worlds(view=view, seed=31, world_count=5)
    second = sample_determinized_worlds(view=view, seed=31, world_count=5)

    assert first == second


def test_sample_determinized_worlds_are_invariant_to_true_hidden_assignment() -> None:
    state_a = _full_state_with_rotating_hidden_hands(rotation=0)
    state_b = _full_state_with_rotating_hidden_hands(rotation=1)

    view_a = build_search_player_view(state=state_a, player_id=PlayerId(0))
    view_b = build_search_player_view(state=state_b, player_id=PlayerId(0))

    worlds_a = sample_determinized_worlds(view=view_a, seed=43, world_count=5)
    worlds_b = sample_determinized_worlds(view=view_b, seed=43, world_count=5)

    assert worlds_a == worlds_b


def test_sample_determinized_world_respects_public_void_constraints() -> None:
    diamond_two = Card(Suit.DIAMONDS, Rank.TWO)
    diamond_three = Card(Suit.DIAMONDS, Rank.THREE)
    spade_two = Card(Suit.SPADES, Rank.TWO)
    view = _manual_view(
        own_hand=(Card(Suit.CLUBS, Rank.TWO),),
        unplayed_cards=(Card(Suit.CLUBS, Rank.TWO), diamond_two, diamond_three, spade_two),
        remaining_cards_by_player={
            PlayerId(0): 1,
            PlayerId(1): 1,
            PlayerId(2): 1,
            PlayerId(3): 1,
        },
        void_suits_by_player={
            PlayerId(0): frozenset(),
            PlayerId(1): frozenset(),
            PlayerId(2): frozenset({Suit.DIAMONDS}),
            PlayerId(3): frozenset(),
        },
    )

    world = sample_determinized_world(view=view, seed=5)

    assert all(card.suit != Suit.DIAMONDS for card in world.hidden_hands[PlayerId(2)])


def test_sample_determinized_world_rejects_known_pass_to_publicly_void_recipient() -> None:
    view = _manual_view(
        own_hand=(Card(Suit.CLUBS, Rank.TWO),),
        unplayed_cards=(
            Card(Suit.CLUBS, Rank.TWO),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING),
        ),
        remaining_cards_by_player={
            PlayerId(0): 1,
            PlayerId(1): 1,
            PlayerId(2): 1,
            PlayerId(3): 0,
        },
        void_suits_by_player={
            PlayerId(0): frozenset(),
            PlayerId(1): frozenset(),
            PlayerId(2): frozenset({Suit.DIAMONDS}),
            PlayerId(3): frozenset(),
        },
        private_knowledge=SeatPrivateKnowledge(
            passed_cards_by_recipient={PlayerId(2): (Card(Suit.DIAMONDS, Rank.ACE),)}
        ),
    )

    try:
        sample_determinized_world(view=view, seed=7)
    except ImpossibleWorldError as exc:
        assert "void" in str(exc).lower()
    else:
        raise AssertionError("Expected impossible-world rejection for void-recipient pass fact.")


def test_sample_determinized_world_rejects_forced_hand_overflow() -> None:
    view = _manual_view(
        own_hand=(Card(Suit.CLUBS, Rank.TWO),),
        unplayed_cards=(
            Card(Suit.CLUBS, Rank.TWO),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.KING),
        ),
        remaining_cards_by_player={
            PlayerId(0): 1,
            PlayerId(1): 1,
            PlayerId(2): 1,
            PlayerId(3): 0,
        },
        private_knowledge=SeatPrivateKnowledge(
            passed_cards_by_recipient={
                PlayerId(1): (
                    Card(Suit.DIAMONDS, Rank.ACE),
                    Card(Suit.DIAMONDS, Rank.KING),
                )
            }
        ),
    )

    try:
        sample_determinized_world(view=view, seed=11)
    except ImpossibleWorldError as exc:
        assert "more cards" in str(exc).lower()
    else:
        raise AssertionError("Expected impossible-world rejection for forced hand overflow.")


def test_sample_determinized_world_preserves_full_game_config_snapshot() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    state.config = GameConfig(
        target_score=75,
        pass_directions=("across", "hold"),
        pass_count=2,
        require_two_clubs_open=False,
        enforce_follow_suit=True,
        hearts_must_be_broken_to_lead=False,
        no_points_on_first_trick=False,
    )
    state.pass_direction = "across"
    view = build_search_player_view(state=state, player_id=PlayerId(0))

    world = sample_determinized_world(view=view, seed=13)

    assert view.config == state.config
    assert view.config is not state.config
    assert world.state.config == state.config
    assert world.state.config is not state.config


def _full_state_with_rotating_hidden_hands(*, rotation: int) -> GameState:
    deck = tuple(make_deck())
    own_hand = list(deck[:13])
    hidden_chunks = [
        list(deck[13:26]),
        list(deck[26:39]),
        list(deck[39:52]),
    ]
    hidden_chunks = hidden_chunks[rotation:] + hidden_chunks[:rotation]

    state = GameState()
    state.hands = {
        PlayerId(0): sorted(own_hand),
        PlayerId(1): sorted(hidden_chunks[0]),
        PlayerId(2): sorted(hidden_chunks[1]),
        PlayerId(3): sorted(hidden_chunks[2]),
    }
    state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}
    state.scores = {player_id: 0 for player_id in PLAYER_IDS}
    state.turn = PlayerId(0)
    state.trick_number = 0
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = True
    return state


def _manual_view(
    *,
    own_hand: tuple[Card, ...],
    unplayed_cards: tuple[Card, ...],
    remaining_cards_by_player: dict[PlayerId, int],
    void_suits_by_player: dict[PlayerId, frozenset[Suit]] | None = None,
    private_knowledge: SeatPrivateKnowledge | None = None,
) -> SearchPlayerView:
    seen_cards = frozenset(card for card in make_deck() if card not in unplayed_cards)
    unplayed = frozenset(unplayed_cards)
    voids = void_suits_by_player or {player_id: frozenset() for player_id in PLAYER_IDS}
    remaining_ranks_by_suit = {
        suit: tuple(sorted(int(card.rank) for card in unplayed if card.suit == suit))
        for suit in Suit
    }
    knowledge = PublicKnowledge(
        seen_cards=seen_cards,
        unplayed_cards=unplayed,
        qs_live=Card(Suit.SPADES, Rank.QUEEN) in unplayed,
        played_count_by_suit={suit: 13 - sum(1 for card in unplayed if card.suit == suit) for suit in Suit},
        unplayed_count_by_suit={suit: sum(1 for card in unplayed if card.suit == suit) for suit in Suit},
        remaining_ranks_by_suit=remaining_ranks_by_suit,
        lowest_remaining_rank_by_suit={
            suit: ranks[0] if ranks else None
            for suit, ranks in remaining_ranks_by_suit.items()
        },
        highest_remaining_rank_by_suit={
            suit: ranks[-1] if ranks else None
            for suit, ranks in remaining_ranks_by_suit.items()
        },
        remaining_cards_by_player=remaining_cards_by_player,
        void_suits_by_player=voids,
    )
    return SearchPlayerView(
        player_id=PlayerId(0),
        hand=tuple(sorted(own_hand)),
        legal_moves=tuple(sorted(own_hand)),
        current_trick=(),
        taken_tricks={player_id: () for player_id in PLAYER_IDS},
        scores={player_id: 0 for player_id in PLAYER_IDS},
        hearts_broken=True,
        turn=PlayerId(0),
        trick_number=12,
        hand_number=1,
        pass_direction="left",
        pass_applied=True,
        target_score=50,
        config=GameConfig(target_score=50),
        public_knowledge=knowledge,
        private_knowledge=private_knowledge or SeatPrivateKnowledge(),
    )
