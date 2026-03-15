from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

from hearts_ai.engine.cards import Card, Suit
from hearts_ai.engine.types import PlayerId

VisibleTrickPlay: TypeAlias = tuple[PlayerId, Card]
VisibleTrick: TypeAlias = tuple[VisibleTrickPlay, ...]
VisibleTakenTricks: TypeAlias = Mapping[PlayerId, tuple[VisibleTrick, ...]]


@dataclass(slots=True, frozen=True)
class SeatPrivateKnowledge:
    """Seat-private facts that are safe for search to use.

    This remains read-only. Mutable seat memory lives in `search.memory` and is
    snapshotted into this search-facing boundary object.
    """

    passed_cards_by_recipient: Mapping[PlayerId, tuple[Card, ...]] = field(default_factory=dict)

    def cards_passed_to(self, recipient: PlayerId) -> tuple[Card, ...]:
        return self.passed_cards_by_recipient.get(recipient, ())

    def recipient_for_passed_card(self, card: Card) -> PlayerId | None:
        for recipient, cards in self.passed_cards_by_recipient.items():
            if card in cards:
                return recipient
        return None

    def has_passed_card(self, *, card: Card, recipient: PlayerId | None = None) -> bool:
        if recipient is not None:
            return card in self.passed_cards_by_recipient.get(recipient, ())
        return self.recipient_for_passed_card(card) is not None


@dataclass(slots=True, frozen=True)
class PublicKnowledge:
    """Publicly derivable card-state facts for hidden-information search."""

    seen_cards: frozenset[Card] = field(default_factory=frozenset)
    unplayed_cards: frozenset[Card] = field(default_factory=frozenset)
    qs_live: bool = True
    played_count_by_suit: Mapping[Suit, int] = field(default_factory=dict)
    unplayed_count_by_suit: Mapping[Suit, int] = field(default_factory=dict)
    remaining_ranks_by_suit: Mapping[Suit, tuple[int, ...]] = field(default_factory=dict)
    lowest_remaining_rank_by_suit: Mapping[Suit, int | None] = field(default_factory=dict)
    highest_remaining_rank_by_suit: Mapping[Suit, int | None] = field(default_factory=dict)
    remaining_cards_by_player: Mapping[PlayerId, int] = field(default_factory=dict)
    void_suits_by_player: Mapping[PlayerId, frozenset[Suit]] = field(default_factory=dict)

    def player_is_void(self, *, player_id: PlayerId, suit: Suit) -> bool:
        return suit in self.void_suits_by_player.get(player_id, frozenset())

    def suit_exhausted_outside_hand(self, *, suit: Suit, own_hand: Iterable[Card]) -> bool:
        own_unplayed_count = sum(
            1
            for card in own_hand
            if card.suit == suit and card in self.unplayed_cards
        )
        return self.unplayed_count_by_suit.get(suit, 0) == own_unplayed_count

    def possible_unplayed_cards_for_opponent(
        self,
        *,
        player_id: PlayerId,
        own_hand: Iterable[Card],
    ) -> frozenset[Card]:
        if self.remaining_cards_by_player.get(player_id, 0) <= 0:
            return frozenset()
        own_unplayed_cards = frozenset(card for card in own_hand if card in self.unplayed_cards)
        blocked_suits = self.void_suits_by_player.get(player_id, frozenset())
        return frozenset(
            card
            for card in self.unplayed_cards
            if card not in own_unplayed_cards and card.suit not in blocked_suits
        )

    def impossible_unplayed_cards_for_opponent(
        self,
        *,
        player_id: PlayerId,
        own_hand: Iterable[Card],
    ) -> frozenset[Card]:
        if self.remaining_cards_by_player.get(player_id, 0) <= 0:
            return frozenset(self.unplayed_cards)
        possible_cards = self.possible_unplayed_cards_for_opponent(
            player_id=player_id,
            own_hand=own_hand,
        )
        return frozenset(card for card in self.unplayed_cards if card not in possible_cards)


@dataclass(slots=True, frozen=True)
class SearchPlayerView:
    """Search-side boundary object for one acting seat.

    This view is meant to be the only game-state surface consumed by future
    search code. It intentionally models only the acting player's hand plus
    public information and seat-private knowledge.
    """

    player_id: PlayerId
    hand: tuple[Card, ...]
    legal_moves: tuple[Card, ...]
    current_trick: VisibleTrick
    taken_tricks: VisibleTakenTricks
    scores: Mapping[PlayerId, int]
    hearts_broken: bool
    turn: PlayerId | None
    trick_number: int
    hand_number: int
    pass_direction: str
    pass_applied: bool
    target_score: int
    public_knowledge: PublicKnowledge
    private_knowledge: SeatPrivateKnowledge = field(default_factory=SeatPrivateKnowledge)


__all__ = [
    "PublicKnowledge",
    "SearchPlayerView",
    "SeatPrivateKnowledge",
    "VisibleTakenTricks",
    "VisibleTrick",
    "VisibleTrickPlay",
]
