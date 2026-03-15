from __future__ import annotations

from dataclasses import dataclass, field

from hearts_ai.search.simulation import HeuristicPlayoutConfig


@dataclass(slots=True, frozen=True)
class SearchBotConfig:
    """Configuration surface for the first search bot."""

    world_count: int = 12
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


__all__ = ["SearchBotConfig"]
