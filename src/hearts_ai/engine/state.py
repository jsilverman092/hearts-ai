from __future__ import annotations

from dataclasses import dataclass, field

from hearts_ai.engine.types import Deal, PLAYER_IDS, PlayerId, Trick

PASS_DIRECTIONS: tuple[str, ...] = ("left", "right", "across", "hold")


def _empty_deal() -> Deal:
    return {player_id: [] for player_id in PLAYER_IDS}


def _empty_taken_tricks() -> dict[PlayerId, list[Trick]]:
    return {player_id: [] for player_id in PLAYER_IDS}


def _zero_scores() -> dict[PlayerId, int]:
    return {player_id: 0 for player_id in PLAYER_IDS}


@dataclass(slots=True)
class GameConfig:
    target_score: int = 50
    pass_directions: tuple[str, ...] = PASS_DIRECTIONS
    pass_count: int = 3
    require_two_clubs_open: bool = True
    enforce_follow_suit: bool = True
    hearts_must_be_broken_to_lead: bool = True
    no_points_on_first_trick: bool = True

    def __post_init__(self) -> None:
        if self.target_score <= 0:
            raise ValueError(f"target_score must be > 0, got {self.target_score}")
        if self.pass_count < 0 or self.pass_count > 13:
            raise ValueError(f"pass_count must be in [0, 13], got {self.pass_count}")
        if not self.pass_directions:
            raise ValueError("pass_directions must not be empty")

        invalid = [direction for direction in self.pass_directions if direction not in PASS_DIRECTIONS]
        if invalid:
            raise ValueError(f"Unsupported pass direction(s): {invalid!r}")


@dataclass(slots=True)
class GameState:
    config: GameConfig = field(default_factory=GameConfig)
    hands: Deal = field(default_factory=_empty_deal)
    trick_in_progress: Trick = field(default_factory=list)
    taken_tricks: dict[PlayerId, list[Trick]] = field(default_factory=_empty_taken_tricks)
    scores: dict[PlayerId, int] = field(default_factory=_zero_scores)
    hearts_broken: bool = False
    turn: PlayerId | None = None
    trick_number: int = 0
    hand_number: int = 0
    pass_direction: str = PASS_DIRECTIONS[0]
    pass_applied: bool = False
    hand_scored: bool = False


__all__ = ["GameConfig", "GameState", "PASS_DIRECTIONS"]
