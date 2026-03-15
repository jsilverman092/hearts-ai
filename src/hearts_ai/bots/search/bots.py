from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from hearts_ai.bots.reasons import DecisionKind
from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.bots.search.models import (
    SearchBotConfig,
    SearchPlayCandidateReason,
    SearchPlayDecisionReason,
)
from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId
from hearts_ai.search import (
    SELECTION_POLICY,
    SeatPrivateMemory,
    build_root_move_candidates,
    build_search_player_view,
    evaluate_root_candidates,
    rank_root_candidate_evaluations,
)
from hearts_ai.search.worlds import ImpossibleWorldError

_MAX_DECISION_SEED = 2**63 - 1


@dataclass(slots=True)
class SearchBotV1:
    """Phase-2 shell for the first sampled-world search bot."""

    player_id: PlayerId
    config: SearchBotConfig = field(default_factory=SearchBotConfig)
    _heuristic_delegate: HeuristicBotV3 = field(init=False, repr=False)
    _private_memory: SeatPrivateMemory = field(init=False, repr=False)
    _last_play_reason: SearchPlayDecisionReason | None = field(init=False, default=None, repr=False)

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
        self._last_play_reason = None

    def on_new_hand(self, state: GameState) -> None:
        self._private_memory.on_new_hand(state)
        self._last_play_reason = None

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
        self._last_play_reason = None
        rng_state_before_search = rng.getstate()
        view = build_search_player_view(
            state=state,
            player_id=self.player_id,
            private_knowledge=self._private_memory.snapshot(),
        )
        decision_seed = rng.randrange(0, _MAX_DECISION_SEED + 1)
        try:
            evaluation = evaluate_root_candidates(
                view=view,
                seed=decision_seed,
                world_count=self.config.world_count,
                playout_seed_offset=self.config.playout_seed_offset,
                playout_config=self.config.playout,
            )
        except ImpossibleWorldError as exc:
            if not self.config.fallback_to_heuristic_v3_on_impossible_world:
                raise
            rng.setstate(rng_state_before_search)
            return self._choose_play_via_heuristic_fallback(
                state=state,
                rng=rng,
                view=view,
                world_base_seed=decision_seed,
                selection_source="heuristic_fallback_impossible_world",
                fallback_message=str(exc),
            )

        if not evaluation.world_set.worlds or not evaluation.candidate_evaluations:
            if not self.config.fallback_to_heuristic_v3_on_empty_world_set:
                raise ValueError("Search evaluation produced no sampled worlds to rank.")
            rng.setstate(rng_state_before_search)
            return self._choose_play_via_heuristic_fallback(
                state=state,
                rng=rng,
                view=view,
                world_base_seed=decision_seed,
                selection_source="heuristic_fallback_empty_world_set",
                fallback_message="Search evaluation produced no sampled worlds to rank.",
            )

        ranked = rank_root_candidate_evaluations(evaluation)
        selected = ranked[0]
        self._last_play_reason = SearchPlayDecisionReason(
            chosen_card=selected.candidate.card,
            mode=selected.candidate.mode,
            trick_number=state.trick_number,
            requested_world_count=self.config.world_count,
            world_count=len(evaluation.world_set.worlds),
            world_base_seed=evaluation.base_seed,
            selection_policy=SELECTION_POLICY,
            selection_source="search",
            fallback_message=None,
            candidates=tuple(
                SearchPlayCandidateReason(
                    card=candidate_evaluation.candidate.card,
                    mode=candidate_evaluation.candidate.mode,
                    candidate_index=candidate_evaluation.candidate_index,
                    selection_rank=selection_rank,
                    selected=selection_rank == 1,
                    follows_led_suit=candidate_evaluation.candidate.follows_led_suit,
                    is_point_card=candidate_evaluation.candidate.is_point_card,
                    trick_points_so_far=candidate_evaluation.candidate.trick_points_so_far,
                    average_projected_hand_points=candidate_evaluation.average_projected_hand_points,
                    average_projected_score_delta=candidate_evaluation.average_projected_score_delta,
                    average_projected_total_score=candidate_evaluation.average_projected_total_score,
                    average_root_utility=candidate_evaluation.average_root_utility,
                )
                for selection_rank, candidate_evaluation in enumerate(ranked, start=1)
            ),
        )
        return selected.candidate.card

    def peek_last_decision_reason(self, decision_kind: DecisionKind) -> object | None:
        if decision_kind == "play":
            return self._last_play_reason
        return self._heuristic_delegate.peek_last_decision_reason(decision_kind)

    def _choose_play_via_heuristic_fallback(
        self,
        *,
        state: GameState,
        rng: random.Random,
        view,
        world_base_seed: int,
        selection_source: str,
        fallback_message: str,
    ) -> Card:
        chosen_card = self._heuristic_delegate.choose_play(state=state, rng=rng)
        fallback_candidate = _candidate_for_card(view=view, card=chosen_card)
        self._last_play_reason = SearchPlayDecisionReason(
            chosen_card=chosen_card,
            mode=fallback_candidate.mode,
            trick_number=state.trick_number,
            requested_world_count=self.config.world_count,
            world_count=0,
            world_base_seed=world_base_seed,
            selection_policy=SELECTION_POLICY,
            selection_source=selection_source,
            fallback_message=fallback_message,
            candidates=(),
        )
        return chosen_card


def _candidate_for_card(*, view, card: Card):
    for candidate in build_root_move_candidates(view):
        if candidate.card == card:
            return candidate
    raise ValueError(f"Chosen card {card} was not present in root move candidates.")


__all__ = ["SearchBotV1"]
