from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from hearts_ai.engine.types import PlayerId
from hearts_ai.search.candidates import RootMoveCandidate, build_root_move_candidates
from hearts_ai.search.models import SearchPlayerView
from hearts_ai.search.simulation import (
    HeuristicPlayoutConfig,
    SearchRolloutSummary,
    simulate_root_candidate,
)
from hearts_ai.search.worlds import DeterminizedWorldSet, sample_determinized_worlds

_MAX_PLAYOUT_SEED = 2**63 - 1
SELECTION_POLICY = (
    "average_projected_score_delta",
    "average_projected_hand_points",
    "average_projected_total_score",
    "candidate_index",
)


@dataclass(slots=True, frozen=True)
class RootCandidateEvaluation:
    """Aggregate rollout scores for one root move across a shared world set."""

    candidate: RootMoveCandidate
    candidate_index: int
    rollout_summaries: tuple[SearchRolloutSummary, ...]
    average_projected_raw_hand_points: float
    average_projected_hand_points: float
    average_projected_score_delta: float
    average_projected_total_score: float
    average_root_utility: float


@dataclass(slots=True, frozen=True)
class RootMoveEvaluationSet:
    """Shared-world evaluation bundle for one root decision."""

    root_player_id: PlayerId
    base_seed: int
    world_set: DeterminizedWorldSet
    candidate_evaluations: tuple[RootCandidateEvaluation, ...]


def evaluate_root_candidate(
    *,
    candidate: RootMoveCandidate,
    candidate_index: int,
    world_set: DeterminizedWorldSet,
    playout_seed_offset: int = 0,
    playout_config: HeuristicPlayoutConfig | None = None,
) -> RootCandidateEvaluation:
    """Evaluate one root move across a shared determinized world set."""

    rollout_summaries = tuple(
        simulate_root_candidate(
            world=world,
            candidate=candidate,
            seed=_playout_seed_for_world(
                world_sample_seed=world.sample_seed,
                playout_seed_offset=playout_seed_offset,
            ),
            playout_config=playout_config,
        ).summary
        for world in world_set.worlds
    )
    if not rollout_summaries:
        raise ValueError("Cannot aggregate root candidate scores without sampled worlds.")

    root_player_id = world_set.root_player_id
    return RootCandidateEvaluation(
        candidate=candidate,
        candidate_index=candidate_index,
        rollout_summaries=rollout_summaries,
        average_projected_raw_hand_points=fmean(
            summary.projected_raw_hand_points[root_player_id]
            for summary in rollout_summaries
        ),
        average_projected_hand_points=fmean(
            summary.projected_hand_points[root_player_id]
            for summary in rollout_summaries
        ),
        average_projected_score_delta=fmean(
            summary.projected_score_deltas[root_player_id]
            for summary in rollout_summaries
        ),
        average_projected_total_score=fmean(
            summary.projected_scores[root_player_id]
            for summary in rollout_summaries
        ),
        average_root_utility=fmean(summary.root_utility for summary in rollout_summaries),
    )


def evaluate_root_candidates(
    *,
    view: SearchPlayerView,
    seed: int,
    world_count: int,
    playout_seed_offset: int = 0,
    playout_config: HeuristicPlayoutConfig | None = None,
) -> RootMoveEvaluationSet:
    """Evaluate all deterministic root candidates on one shared sampled-world set."""

    candidates = build_root_move_candidates(view)
    if not candidates:
        raise ValueError("Search evaluation requires at least one legal root candidate.")

    world_set = sample_determinized_worlds(
        view=view,
        seed=seed,
        world_count=world_count,
    )
    candidate_evaluations = tuple(
        evaluate_root_candidate(
            candidate=candidate,
            candidate_index=candidate_index,
            world_set=world_set,
            playout_seed_offset=playout_seed_offset,
            playout_config=playout_config,
        )
        for candidate_index, candidate in enumerate(candidates)
    )
    return RootMoveEvaluationSet(
        root_player_id=view.player_id,
        base_seed=seed,
        world_set=world_set,
        candidate_evaluations=candidate_evaluations,
    )


def selection_key_for_candidate(evaluation: RootCandidateEvaluation) -> tuple[float, float, float, int]:
    """Stable ranking key for choosing the best root move.

    Lower values are better:
    1. lower average projected score delta
    2. lower average projected hand points
    3. lower average projected total score
    4. lower original candidate index
    """

    return (
        evaluation.average_projected_score_delta,
        evaluation.average_projected_hand_points,
        evaluation.average_projected_total_score,
        evaluation.candidate_index,
    )


def rank_root_candidate_evaluations(
    evaluation_set: RootMoveEvaluationSet,
) -> tuple[RootCandidateEvaluation, ...]:
    """Return candidates ordered best-to-worst under the stable selection policy."""

    return tuple(
        sorted(
            evaluation_set.candidate_evaluations,
            key=selection_key_for_candidate,
        )
    )


def select_best_root_candidate(evaluation_set: RootMoveEvaluationSet) -> RootCandidateEvaluation:
    """Select the deterministic best root candidate from an evaluated root move set."""

    ranked = rank_root_candidate_evaluations(evaluation_set)
    if not ranked:
        raise ValueError("Cannot select a root candidate from an empty evaluation set.")
    return ranked[0]


def _playout_seed_for_world(*, world_sample_seed: int, playout_seed_offset: int) -> int:
    return (world_sample_seed + playout_seed_offset) % (_MAX_PLAYOUT_SEED + 1)


__all__ = [
    "RootCandidateEvaluation",
    "RootMoveEvaluationSet",
    "evaluate_root_candidate",
    "evaluate_root_candidates",
    "rank_root_candidate_evaluations",
    "SELECTION_POLICY",
    "select_best_root_candidate",
    "selection_key_for_candidate",
]
