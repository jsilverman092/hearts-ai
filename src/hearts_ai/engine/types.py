from __future__ import annotations

from typing import NewType, TypeAlias

from hearts_ai.engine.cards import Card

PlayerId = NewType("PlayerId", int)
PLAYER_COUNT = 4
PLAYER_IDS: tuple[PlayerId, ...] = (
    PlayerId(0),
    PlayerId(1),
    PlayerId(2),
    PlayerId(3),
)

Hand: TypeAlias = list[Card]
TrickPlay: TypeAlias = tuple[PlayerId, Card]
Trick: TypeAlias = list[TrickPlay]
Deal: TypeAlias = dict[PlayerId, Hand]


def to_player_id(value: int) -> PlayerId:
    if value < 0 or value >= PLAYER_COUNT:
        raise ValueError(f"Player id must be in [0, {PLAYER_COUNT - 1}], got {value}")
    return PlayerId(value)


__all__ = [
    "Deal",
    "Hand",
    "PLAYER_COUNT",
    "PLAYER_IDS",
    "PlayerId",
    "Trick",
    "TrickPlay",
    "to_player_id",
]
