from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from hearts_ai.engine.cards import Card, Suit
from hearts_ai.search.candidates import SearchPlayMode
from hearts_ai.search.simulation import HeuristicPlayoutConfig

SearchSelectionMetric = Literal[
    "average_projected_score_delta",
    "average_projected_hand_points",
    "average_projected_total_score",
    "heuristic_v3_exact_tie_order",
    "candidate_index",
]
SearchSelectionSource = Literal[
    "search",
    "heuristic_fallback_impossible_world",
    "heuristic_fallback_empty_world_set",
]


@dataclass(slots=True, frozen=True)
class SearchBotConfig:
    """Configuration surface for the first search bot.

    Defaults stay intentionally conservative so the bot remains usable in CLI
    play and benchmark flows while the search stack is still shallow.
    """

    world_count: int = 1
    playout_seed_offset: int = 1_000_003
    fallback_to_heuristic_v3_on_impossible_world: bool = True
    fallback_to_heuristic_v3_on_empty_world_set: bool = True
    playout: HeuristicPlayoutConfig = field(default_factory=HeuristicPlayoutConfig)

    def __post_init__(self) -> None:
        if self.world_count <= 0:
            raise ValueError(f"world_count must be > 0, got {self.world_count}")
        if self.playout_seed_offset < 0:
            raise ValueError(
                f"playout_seed_offset must be >= 0, got {self.playout_seed_offset}"
            )


@dataclass(slots=True, frozen=True)
class SearchPlayCandidateReason:
    card: Card
    mode: SearchPlayMode
    candidate_index: int
    selection_rank: int
    selected: bool
    follows_led_suit: bool
    is_point_card: bool
    trick_points_so_far: int
    average_projected_hand_points: float
    average_projected_score_delta: float
    average_projected_total_score: float
    average_root_utility: float


@dataclass(slots=True, frozen=True)
class SearchChosenMoveReason:
    """Compact summary of the chosen root move for display/debug surfaces."""

    card: Card
    mode: SearchPlayMode
    candidate_index: int
    follows_led_suit: bool
    is_point_card: bool
    trick_points_so_far: int
    average_projected_hand_points: float | None
    average_projected_score_delta: float | None
    average_projected_total_score: float | None
    average_root_utility: float | None


@dataclass(slots=True, frozen=True)
class SearchComparedMoveReason:
    """Compact summary of a non-selected move compared against the search choice."""

    card: Card
    mode: SearchPlayMode
    candidate_index: int
    selection_rank: int
    follows_led_suit: bool
    is_point_card: bool
    trick_points_so_far: int
    average_projected_hand_points: float
    average_projected_score_delta: float
    average_projected_total_score: float
    average_root_utility: float


@dataclass(slots=True, frozen=True)
class SearchBaselineComparisonReason:
    """Shared-world comparison between the search choice and heuristic_v3."""

    baseline_bot_name: str
    agrees_with_search: bool
    baseline: SearchComparedMoveReason
    mean_projected_score_delta_advantage: float
    mean_root_utility_gain: float
    worlds_search_better: int
    worlds_tied: int
    worlds_baseline_better: int
    worst_case_root_utility_loss: float
    best_case_root_utility_gain: float


@dataclass(slots=True, frozen=True)
class SearchPlayDecisionReason:
    chosen_card: Card
    mode: SearchPlayMode
    trick_number: int
    legal_move_count: int
    evaluated_candidate_count: int
    current_trick_size: int
    led_suit: Suit | None
    chosen: SearchChosenMoveReason
    requested_world_count: int
    world_count: int
    world_base_seed: int
    selection_policy: tuple[SearchSelectionMetric, ...]
    selection_source: SearchSelectionSource
    fallback_message: str | None
    baseline_comparison: SearchBaselineComparisonReason | None
    candidates: tuple[SearchPlayCandidateReason, ...]


__all__ = [
    "SearchBotConfig",
    "SearchBaselineComparisonReason",
    "SearchComparedMoveReason",
    "SearchPlayCandidateReason",
    "SearchChosenMoveReason",
    "SearchPlayDecisionReason",
    "SearchSelectionMetric",
    "SearchSelectionSource",
]
