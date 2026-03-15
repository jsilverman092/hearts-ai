from __future__ import annotations

from collections.abc import Mapping
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

    This starts intentionally small. Later phases can add explicit memory such as
    exact own-pass knowledge without changing the SearchPlayerView boundary.
    """

    passed_cards_by_recipient: Mapping[PlayerId, tuple[Card, ...]] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class PublicKnowledge:
    """Publicly derivable card-state facts for hidden-information search."""

    seen_cards: frozenset[Card] = field(default_factory=frozenset)
    unplayed_cards: frozenset[Card] = field(default_factory=frozenset)
    qs_live: bool = True
    played_count_by_suit: Mapping[Suit, int] = field(default_factory=dict)
    unplayed_count_by_suit: Mapping[Suit, int] = field(default_factory=dict)
    remaining_cards_by_player: Mapping[PlayerId, int] = field(default_factory=dict)
    void_suits_by_player: Mapping[PlayerId, frozenset[Suit]] = field(default_factory=dict)


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
