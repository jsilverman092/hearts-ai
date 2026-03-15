from __future__ import annotations

from types import MappingProxyType

from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId, Trick
from hearts_ai.search.models import PublicKnowledge

_QUEEN_SPADES = Card(Suit.SPADES, Rank.QUEEN)


def build_public_knowledge(*, state: GameState) -> PublicKnowledge:
    seen_cards = frozenset(card for trick in all_public_tricks(state=state) for _, card in trick)
    unplayed_cards = frozenset(card for card in make_deck() if card not in seen_cards)
    played_count_by_suit = MappingProxyType(
        {suit: sum(1 for card in seen_cards if card.suit == suit) for suit in Suit}
    )
    unplayed_count_by_suit = MappingProxyType(
        {suit: sum(1 for card in unplayed_cards if card.suit == suit) for suit in Suit}
    )
    remaining_ranks_by_suit = MappingProxyType(
        {
            suit: tuple(sorted(int(card.rank) for card in unplayed_cards if card.suit == suit))
            for suit in Suit
        }
    )
    lowest_remaining_rank_by_suit = MappingProxyType(
        {
            suit: ranks[0] if ranks else None
            for suit, ranks in remaining_ranks_by_suit.items()
        }
    )
    highest_remaining_rank_by_suit = MappingProxyType(
        {
            suit: ranks[-1] if ranks else None
            for suit, ranks in remaining_ranks_by_suit.items()
        }
    )
    remaining_cards_by_player = MappingProxyType({player_id: len(state.hands[player_id]) for player_id in PLAYER_IDS})
    void_suits_by_player = MappingProxyType(infer_void_suits_by_player(state=state))

    return PublicKnowledge(
        seen_cards=seen_cards,
        unplayed_cards=unplayed_cards,
        qs_live=_QUEEN_SPADES not in seen_cards,
        played_count_by_suit=played_count_by_suit,
        unplayed_count_by_suit=unplayed_count_by_suit,
        remaining_ranks_by_suit=remaining_ranks_by_suit,
        lowest_remaining_rank_by_suit=lowest_remaining_rank_by_suit,
        highest_remaining_rank_by_suit=highest_remaining_rank_by_suit,
        remaining_cards_by_player=remaining_cards_by_player,
        void_suits_by_player=void_suits_by_player,
    )


def all_public_tricks(*, state: GameState) -> tuple[Trick, ...]:
    taken_tricks = tuple(trick for player_id in PLAYER_IDS for trick in state.taken_tricks[player_id])
    if not state.trick_in_progress:
        return taken_tricks
    return (*taken_tricks, state.trick_in_progress)


def infer_void_suits_by_player(*, state: GameState) -> dict[PlayerId, frozenset[Suit]]:
    inferred: dict[PlayerId, set[Suit]] = {player_id: set() for player_id in PLAYER_IDS}
    for trick in all_public_tricks(state=state):
        if len(trick) < 2:
            continue
        led_suit = trick[0][1].suit
        for player_id, card in trick[1:]:
            if card.suit != led_suit:
                inferred[player_id].add(led_suit)
    return {player_id: frozenset(suits) for player_id, suits in inferred.items()}


__all__ = [
    "all_public_tricks",
    "build_public_knowledge",
    "infer_void_suits_by_player",
]
