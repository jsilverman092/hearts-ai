from __future__ import annotations

import random
from typing import Protocol

from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId


class Bot(Protocol):
    player_id: PlayerId

    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        ...

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        ...


__all__ = ["Bot"]
