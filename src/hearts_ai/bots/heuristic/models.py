from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.types import PlayerId

_QUEEN_SPADES = Card(Suit.SPADES, Rank.QUEEN)
_KING_SPADES = Card(Suit.SPADES, Rank.KING)
_ACE_SPADES = Card(Suit.SPADES, Rank.ACE)


@dataclass(slots=True, frozen=True)
class PassCandidateReason:
    card: Card
    score: tuple[int, int, int]


@dataclass(slots=True, frozen=True)
class PassDecisionReason:
    selected_cards: tuple[Card, ...]
    candidates: tuple[PassCandidateReason, ...]


@dataclass(slots=True, frozen=True)
class PlayCandidateReason:
    card: Card
    base_score: float
    rollout_score: float
    total_score: float
    tags: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class PlayDecisionReason:
    mode: Literal["lead", "follow", "discard"]
    trick_number: int
    chosen_card: Card
    moon_defense_target: PlayerId | None
    candidates: tuple[PlayCandidateReason, ...]


@dataclass(slots=True, frozen=True)
class PublicInfoV3:
    qs_live: bool
    played_count_by_suit: dict[Suit, int]
    lowest_unseen_rank_by_suit: dict[Suit, int | None]
    unseen_ranks_by_suit: dict[Suit, tuple[int, ...]]
    void_suits_by_player: dict[PlayerId, frozenset[Suit]]


__all__ = [
    "PassCandidateReason",
    "PassDecisionReason",
    "PlayCandidateReason",
    "PlayDecisionReason",
    "PublicInfoV3",
]
