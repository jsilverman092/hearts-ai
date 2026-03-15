from __future__ import annotations

import random
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from statistics import fmean

from hearts_ai.bots.reasons import DecisionKind
from hearts_ai.bots.heuristic import HeuristicBotV3, PlayDecisionReason
from hearts_ai.bots.search.models import (
    SearchBotConfig,
    SearchBaselineComparisonReason,
    SearchChosenMoveReason,
    SearchComparedMoveReason,
    SearchPlayCandidateReason,
    SearchPlayDecisionReason,
)
from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId
from hearts_ai.search import (
    RootCandidateEvaluation,
    RootMoveEvaluationSet,
    RootMoveCandidate,
    SeatPrivateMemory,
    build_root_move_candidates,
    build_search_player_view,
    evaluate_root_candidates,
)
from hearts_ai.search.worlds import ImpossibleWorldError

_MAX_DECISION_SEED = 2**63 - 1
SEARCH_BOT_V1_SELECTION_POLICY = (
    "average_projected_score_delta",
    "average_projected_hand_points",
    "average_projected_total_score",
    "heuristic_v3_exact_tie_order",
    "candidate_index",
)


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

        heuristic_ordered_cards = _heuristic_ordered_cards(
            state=state,
            player_id=self.player_id,
            seed=decision_seed,
        )
        baseline_card = heuristic_ordered_cards[0]
        ranked = _rank_candidate_evaluations_with_baseline_tiebreak(
            evaluation=evaluation,
            heuristic_ordered_cards=heuristic_ordered_cards,
        )
        selected = ranked[0]
        self._last_play_reason = SearchPlayDecisionReason(
            chosen_card=selected.candidate.card,
            mode=selected.candidate.mode,
            trick_number=state.trick_number,
            legal_move_count=len(view.legal_moves),
            evaluated_candidate_count=len(evaluation.candidate_evaluations),
            current_trick_size=len(view.current_trick),
            led_suit=view.current_trick[0][1].suit if view.current_trick else None,
            chosen=_chosen_move_reason_from_evaluation(selected),
            requested_world_count=self.config.world_count,
            world_count=len(evaluation.world_set.worlds),
            world_base_seed=evaluation.base_seed,
            selection_policy=SEARCH_BOT_V1_SELECTION_POLICY,
            selection_source="search",
            fallback_message=None,
            baseline_comparison=_baseline_comparison_for_card(
                evaluation=evaluation,
                selected=selected,
                ranked=ranked,
                baseline_card=baseline_card,
            ),
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
                    average_projected_raw_hand_points=candidate_evaluation.average_projected_raw_hand_points,
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
        fallback_candidate_index, fallback_candidate = _candidate_for_card(view=view, card=chosen_card)
        self._last_play_reason = SearchPlayDecisionReason(
            chosen_card=chosen_card,
            mode=fallback_candidate.mode,
            trick_number=state.trick_number,
            legal_move_count=len(view.legal_moves),
            evaluated_candidate_count=0,
            current_trick_size=len(view.current_trick),
            led_suit=view.current_trick[0][1].suit if view.current_trick else None,
            chosen=_chosen_move_reason_from_candidate(
                candidate=fallback_candidate,
                candidate_index=fallback_candidate_index,
            ),
            requested_world_count=self.config.world_count,
            world_count=0,
            world_base_seed=world_base_seed,
            selection_policy=SEARCH_BOT_V1_SELECTION_POLICY,
            selection_source=selection_source,
            fallback_message=fallback_message,
            baseline_comparison=None,
            candidates=(),
        )
        return chosen_card


def _candidate_for_card(*, view, card: Card) -> tuple[int, RootMoveCandidate]:
    for candidate_index, candidate in enumerate(build_root_move_candidates(view)):
        if candidate.card == card:
            return candidate_index, candidate
    raise ValueError(f"Chosen card {card} was not present in root move candidates.")


def _chosen_move_reason_from_evaluation(
    evaluation: RootCandidateEvaluation,
) -> SearchChosenMoveReason:
    candidate = evaluation.candidate
    return SearchChosenMoveReason(
        card=candidate.card,
        mode=candidate.mode,
        candidate_index=evaluation.candidate_index,
        follows_led_suit=candidate.follows_led_suit,
        is_point_card=candidate.is_point_card,
        trick_points_so_far=candidate.trick_points_so_far,
        average_projected_raw_hand_points=evaluation.average_projected_raw_hand_points,
        average_projected_hand_points=evaluation.average_projected_hand_points,
        average_projected_score_delta=evaluation.average_projected_score_delta,
        average_projected_total_score=evaluation.average_projected_total_score,
        average_root_utility=evaluation.average_root_utility,
    )


def _chosen_move_reason_from_candidate(
    *,
    candidate: RootMoveCandidate,
    candidate_index: int,
) -> SearchChosenMoveReason:
    return SearchChosenMoveReason(
        card=candidate.card,
        mode=candidate.mode,
        candidate_index=candidate_index,
        follows_led_suit=candidate.follows_led_suit,
        is_point_card=candidate.is_point_card,
        trick_points_so_far=candidate.trick_points_so_far,
        average_projected_raw_hand_points=None,
        average_projected_hand_points=None,
        average_projected_score_delta=None,
        average_projected_total_score=None,
        average_root_utility=None,
    )


def _search_metric_key(evaluation: RootCandidateEvaluation) -> tuple[float, float, float]:
    return (
        evaluation.average_projected_score_delta,
        evaluation.average_projected_hand_points,
        evaluation.average_projected_total_score,
    )


def _rank_candidate_evaluations_with_baseline_tiebreak(
    *,
    evaluation: RootMoveEvaluationSet,
    heuristic_ordered_cards: tuple[Card, ...],
) -> tuple[RootCandidateEvaluation, ...]:
    heuristic_rank_by_card = {
        card: rank
        for rank, card in enumerate(heuristic_ordered_cards)
    }
    return tuple(
        sorted(
            evaluation.candidate_evaluations,
            key=lambda candidate_evaluation: (
                *_search_metric_key(candidate_evaluation),
                heuristic_rank_by_card.get(
                    candidate_evaluation.candidate.card,
                    len(heuristic_rank_by_card),
                ),
                candidate_evaluation.candidate_index,
            ),
        )
    )


def _heuristic_ordered_cards(
    *,
    state: GameState,
    player_id: PlayerId,
    seed: int,
) -> tuple[Card, ...]:
    bot = HeuristicBotV3(player_id=player_id)
    chosen_card = bot.choose_play(state=deepcopy(state), rng=random.Random(seed))
    reason = bot.peek_last_decision_reason("play")
    if not isinstance(reason, PlayDecisionReason):
        raise TypeError("HeuristicBotV3 did not expose a structured play decision reason.")
    ordered_cards = tuple(candidate.card for candidate in reason.candidates)
    if not ordered_cards:
        raise ValueError("HeuristicBotV3 produced no candidate ordering for tie-break use.")
    if ordered_cards[0] != chosen_card:
        raise ValueError("HeuristicBotV3 candidate ordering was inconsistent with its chosen card.")
    return ordered_cards


def _baseline_comparison_for_card(
    *,
    evaluation: RootMoveEvaluationSet,
    selected: RootCandidateEvaluation,
    ranked: tuple[RootCandidateEvaluation, ...],
    baseline_card: Card,
) -> SearchBaselineComparisonReason:
    rank_by_candidate_index = {
        candidate_evaluation.candidate_index: selection_rank
        for selection_rank, candidate_evaluation in enumerate(ranked, start=1)
    }
    baseline_evaluation = _candidate_evaluation_for_card(
        evaluation=evaluation,
        card=baseline_card,
    )
    root_player_id = evaluation.root_player_id
    root_utility_gains = tuple(
        selected_summary.root_utility - baseline_summary.root_utility
        for selected_summary, baseline_summary in zip(
            selected.rollout_summaries,
            baseline_evaluation.rollout_summaries,
        )
    )
    score_delta_advantages = tuple(
        float(baseline_summary.projected_score_deltas[root_player_id])
        - float(selected_summary.projected_score_deltas[root_player_id])
        for selected_summary, baseline_summary in zip(
            selected.rollout_summaries,
            baseline_evaluation.rollout_summaries,
        )
    )
    return SearchBaselineComparisonReason(
        baseline_bot_name="heuristic_v3",
        agrees_with_search=baseline_evaluation.candidate.card == selected.candidate.card,
        baseline=_compared_move_reason_from_evaluation(
            evaluation=baseline_evaluation,
            selection_rank=rank_by_candidate_index[baseline_evaluation.candidate_index],
        ),
        mean_projected_score_delta_advantage=fmean(score_delta_advantages),
        mean_root_utility_gain=fmean(root_utility_gains),
        worlds_search_better=sum(gain > 0.0 for gain in root_utility_gains),
        worlds_tied=sum(gain == 0.0 for gain in root_utility_gains),
        worlds_baseline_better=sum(gain < 0.0 for gain in root_utility_gains),
        worst_case_root_utility_loss=max((-gain for gain in root_utility_gains if gain < 0.0), default=0.0),
        best_case_root_utility_gain=max((gain for gain in root_utility_gains if gain > 0.0), default=0.0),
    )


def _candidate_evaluation_for_card(
    *,
    evaluation: RootMoveEvaluationSet,
    card: Card,
) -> RootCandidateEvaluation:
    for candidate_evaluation in evaluation.candidate_evaluations:
        if candidate_evaluation.candidate.card == card:
            return candidate_evaluation
    raise ValueError(f"Baseline card {card} was not present in root candidate evaluations.")


def _compared_move_reason_from_evaluation(
    *,
    evaluation: RootCandidateEvaluation,
    selection_rank: int,
) -> SearchComparedMoveReason:
    candidate = evaluation.candidate
    return SearchComparedMoveReason(
        card=candidate.card,
        mode=candidate.mode,
        candidate_index=evaluation.candidate_index,
        selection_rank=selection_rank,
        follows_led_suit=candidate.follows_led_suit,
        is_point_card=candidate.is_point_card,
        trick_points_so_far=candidate.trick_points_so_far,
        average_projected_raw_hand_points=evaluation.average_projected_raw_hand_points,
        average_projected_hand_points=evaluation.average_projected_hand_points,
        average_projected_score_delta=evaluation.average_projected_score_delta,
        average_projected_total_score=evaluation.average_projected_total_score,
        average_root_utility=evaluation.average_root_utility,
    )


__all__ = ["SearchBotV1"]
