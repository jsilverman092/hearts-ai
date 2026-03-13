from __future__ import annotations

from hearts_ai.bots.heuristic.models import PublicInfoV3, _QUEEN_SPADES
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_COUNT, PlayerId, Trick


def _build_public_info_v3(state: GameState) -> PublicInfoV3:
    seen_cards = {
        current
        for trick in _all_public_tricks(state=state)
        for _, current in trick
    }
    played_count_by_suit = {
        suit: sum(1 for current in seen_cards if current.suit == suit) for suit in Suit
    }
    unseen_ranks_by_suit: dict[Suit, tuple[int, ...]] = {}
    lowest_unseen_rank_by_suit: dict[Suit, int | None] = {}
    for suit in Suit:
        unseen = tuple(
            int(rank)
            for rank in Rank
            if Card(suit=suit, rank=rank) not in seen_cards
        )
        unseen_ranks_by_suit[suit] = unseen
        lowest_unseen_rank_by_suit[suit] = unseen[0] if unseen else None

    void_suits_by_player = _infer_void_suits_by_player(state=state)
    return PublicInfoV3(
        qs_live=_QUEEN_SPADES not in seen_cards,
        played_count_by_suit=played_count_by_suit,
        lowest_unseen_rank_by_suit=lowest_unseen_rank_by_suit,
        unseen_ranks_by_suit=unseen_ranks_by_suit,
        void_suits_by_player=void_suits_by_player,
    )


def _all_public_tricks(state: GameState) -> list[Trick]:
    tricks = [
        trick
        for taken in state.taken_tricks.values()
        for trick in taken
    ]
    if state.trick_in_progress:
        tricks.append(state.trick_in_progress)
    return tricks


def _infer_void_suits_by_player(state: GameState) -> dict[PlayerId, frozenset[Suit]]:
    inferred: dict[PlayerId, set[Suit]] = {
        PlayerId(index): set() for index in range(PLAYER_COUNT)
    }
    for trick in _all_public_tricks(state=state):
        if len(trick) < 2:
            continue
        led_suit = trick[0][1].suit
        for player_id, card in trick[1:]:
            if card.suit != led_suit:
                inferred[player_id].add(led_suit)
    return {player_id: frozenset(suits) for player_id, suits in inferred.items()}


def _outside_rank_counts_for_card(
    state: GameState,
    public_info: PublicInfoV3,
    player_id: PlayerId,
    card: Card,
) -> tuple[int, int]:
    rank_value = int(card.rank)
    own_suit_ranks = {
        int(current.rank) for current in state.hands[player_id] if current.suit == card.suit
    }
    unseen_ranks = public_info.unseen_ranks_by_suit[card.suit]
    outside_lower = sum(
        1 for unseen in unseen_ranks if unseen < rank_value and unseen not in own_suit_ranks
    )
    outside_higher = sum(
        1 for unseen in unseen_ranks if unseen > rank_value and unseen not in own_suit_ranks
    )
    return outside_lower, outside_higher


def _void_count_in_players(
    public_info: PublicInfoV3,
    suit: Suit,
    players: list[PlayerId],
) -> int:
    return sum(
        1
        for player_id in players
        if suit in public_info.void_suits_by_player.get(player_id, frozenset())
    )

