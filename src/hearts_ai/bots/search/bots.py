from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from hearts_ai.bots.reasons import DecisionKind
from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.bots.search.models import SearchBotConfig
from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId
from hearts_ai.search import (
    RootCandidateEvaluation,
    RootMoveEvaluationSet,
    SeatPrivateMemory,
    build_search_player_view,
    evaluate_root_candidates,
)


@dataclass(slots=True)
class SearchBotV1:
    """Phase-2 shell for the first sampled-world search bot."""

    player_id: PlayerId
    config: SearchBotConfig = field(default_factory=SearchBotConfig)
    _heuristic_delegate: HeuristicBotV3 = field(init=False, repr=False)
    _private_memory: SeatPrivateMemory = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._heuristic_delegate = HeuristicBotV3(
            player_id=self.player_id,
            rollout_samples=self.config.playout.rollout_samples,
            rollout_weight=self.config.playout.rollout_weight,
            moon_defense_threshold=self.config.playout.moon_defense_threshold,
        )
        self._private_memory = SeatPrivateMemory(player_id=self.player_id)

    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        return self._heuristic_delegate.choose_pass(hand=hand, state=state, rng=rng)

    def on_new_game(self) -> None:
        self._private_memory.on_new_game()

    def on_new_hand(self, state: GameState) -> None:
        self._private_memory.on_new_hand(state)

    def on_own_pass_selected(
        self,
        *,
        state: GameState,
        selected_cards: Sequence[Card],
        recipient: PlayerId | None,
    ) -> None:
        del recipient
        self._private_memory.record_own_pass(state=state, selected_cards=selected_cards)

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        view = build_search_player_view(
            state=state,
            player_id=self.player_id,
            private_knowledge=self._private_memory.snapshot(),
        )
        evaluation = evaluate_root_candidates(
            view=view,
            seed=rng.randrange(0, 2**63),
            world_count=self.config.world_count,
            playout_seed_offset=self.config.playout_seed_offset,
            playout_config=self.config.playout,
        )
        return _select_best_candidate(evaluation).candidate.card

    def peek_last_decision_reason(self, decision_kind: DecisionKind) -> object | None:
        if decision_kind == "play":
            return None
        return self._heuristic_delegate.peek_last_decision_reason(decision_kind)


def _select_best_candidate(evaluation: RootMoveEvaluationSet) -> RootCandidateEvaluation:
    return max(
        enumerate(evaluation.candidate_evaluations),
        key=lambda item: (item[1].average_root_utility, -item[0]),
    )[1]


__all__ = ["SearchBotV1"]
