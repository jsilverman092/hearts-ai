from __future__ import annotations

import random
from dataclasses import dataclass, field

from hearts_ai.bots.reasons import DecisionKind
from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.bots.search.models import SearchBotConfig
from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId


@dataclass(slots=True)
class SearchBotV1:
    """Phase-2 shell for the first sampled-world search bot."""

    player_id: PlayerId
    config: SearchBotConfig = field(default_factory=SearchBotConfig)
    _heuristic_delegate: HeuristicBotV3 = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._heuristic_delegate = HeuristicBotV3(
            player_id=self.player_id,
            rollout_samples=self.config.playout.rollout_samples,
            rollout_weight=self.config.playout.rollout_weight,
            moon_defense_threshold=self.config.playout.moon_defense_threshold,
        )

    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        return self._heuristic_delegate.choose_pass(hand=hand, state=state, rng=rng)

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        # Step 1 keeps play behavior usable while the sampled-world evaluator is wired next.
        return self._heuristic_delegate.choose_play(state=state, rng=rng)

    def peek_last_decision_reason(self, decision_kind: DecisionKind) -> object | None:
        return self._heuristic_delegate.peek_last_decision_reason(decision_kind)


__all__ = ["SearchBotV1"]
