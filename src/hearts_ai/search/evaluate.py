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


@dataclass(slots=True, frozen=True)
class RootCandidateEvaluation:
    """Aggregate rollout scores for one root move across a shared world set."""

    candidate: RootMoveCandidate
    rollout_summaries: tuple[SearchRolloutSummary, ...]
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
        rollout_summaries=rollout_summaries,
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
            world_set=world_set,
            playout_seed_offset=playout_seed_offset,
            playout_config=playout_config,
        )
        for candidate in candidates
    )
    return RootMoveEvaluationSet(
        root_player_id=view.player_id,
        base_seed=seed,
        world_set=world_set,
        candidate_evaluations=candidate_evaluations,
    )


def _playout_seed_for_world(*, world_sample_seed: int, playout_seed_offset: int) -> int:
    return (world_sample_seed + playout_seed_offset) % (_MAX_PLAYOUT_SEED + 1)


__all__ = [
    "RootCandidateEvaluation",
    "RootMoveEvaluationSet",
    "evaluate_root_candidate",
    "evaluate_root_candidates",
]
