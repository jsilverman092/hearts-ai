from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hearts_ai.engine.cards import Card
from hearts_ai.engine.rules import is_point_card
from hearts_ai.engine.scoring import trick_points
from hearts_ai.search.models import SearchPlayerView

SearchPlayMode = Literal["lead", "follow", "discard"]


@dataclass(slots=True, frozen=True)
class RootMoveCandidate:
    """Deterministic root-move descriptor derived from a SearchPlayerView."""

    card: Card
    mode: SearchPlayMode
    follows_led_suit: bool
    is_point_card: bool
    trick_points_so_far: int


def build_root_move_candidates(view: SearchPlayerView) -> tuple[RootMoveCandidate, ...]:
    """Enumerate deterministic root candidates from a search-side player view."""

    mode = _play_mode(view=view)
    led_suit = view.current_trick[0][1].suit if view.current_trick else None
    trick_points_so_far = trick_points(list(view.current_trick)) if view.current_trick else 0
    ordered_cards = tuple(sorted(view.legal_moves, key=_candidate_sort_key))
    return tuple(
        RootMoveCandidate(
            card=card,
            mode=mode,
            follows_led_suit=led_suit is not None and card.suit == led_suit,
            is_point_card=is_point_card(card),
            trick_points_so_far=trick_points_so_far,
        )
        for card in ordered_cards
    )


def _play_mode(view: SearchPlayerView) -> SearchPlayMode:
    if not view.current_trick:
        return "lead"
    led_suit = view.current_trick[0][1].suit
    if any(card.suit == led_suit for card in view.legal_moves):
        return "follow"
    return "discard"


def _candidate_sort_key(card: Card) -> tuple[int, int]:
    return (int(card.rank), int(card.suit))


__all__ = ["RootMoveCandidate", "SearchPlayMode", "build_root_move_candidates"]
