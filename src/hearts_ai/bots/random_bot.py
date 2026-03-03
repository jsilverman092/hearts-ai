from __future__ import annotations

import random
from dataclasses import dataclass

from hearts_ai.engine.cards import Card
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId


@dataclass(slots=True, frozen=True)
class RandomBot:
    player_id: PlayerId

    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        pass_count = state.config.pass_count
        if state.pass_direction == "hold" or pass_count == 0:
            return []
        if pass_count > len(hand):
            raise InvalidStateError(
                f"Cannot pass {pass_count} cards from hand of size {len(hand)} for player {int(self.player_id)}."
            )
        return sorted(rng.sample(hand, pass_count))

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        moves = legal_moves(state=state, player_id=self.player_id)
        if not moves:
            raise InvalidStateError(f"No legal moves available for player {int(self.player_id)}.")
        return rng.choice(moves)


__all__ = ["RandomBot"]
