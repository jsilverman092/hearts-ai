from __future__ import annotations

import random
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType

from hearts_ai.bots.base import Bot
from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.engine.cards import Card
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.game import is_hand_over, play_card
from hearts_ai.engine.scoring import hand_points
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search.candidates import RootMoveCandidate
from hearts_ai.search.worlds import DeterminizedWorld


@dataclass(slots=True, frozen=True)
class HeuristicPlayoutConfig:
    """Deterministic rollout policy settings for whole-hand simulation."""

    rollout_samples: int = 0
    rollout_weight: float = 0.0
    moon_defense_threshold: int = 12


@dataclass(slots=True, frozen=True)
class SearchRolloutSummary:
    """Root-move simulation summary for one determinized world."""

    world_sample_index: int
    world_sample_seed: int
    root_player_id: PlayerId
    candidate: RootMoveCandidate
    projected_hand_points: Mapping[PlayerId, int]
    projected_score_deltas: Mapping[PlayerId, int]
    projected_scores: Mapping[PlayerId, int]
    root_utility: float


@dataclass(slots=True)
class SearchRolloutResult:
    """Completed whole-hand rollout plus its immutable summary."""

    summary: SearchRolloutSummary
    final_state: GameState = field(repr=False, compare=False)


def clone_determinized_state(*, world: DeterminizedWorld) -> GameState:
    """Clone a determinized world state for isolated simulation."""

    return deepcopy(world.state)


def build_deterministic_playout_bots(
    *,
    config: HeuristicPlayoutConfig | None = None,
) -> dict[PlayerId, Bot]:
    """Create one low-noise heuristic-v3 playout bot per seat."""

    active_config = config or HeuristicPlayoutConfig()
    return {
        player_id: HeuristicBotV3(
            player_id=player_id,
            rollout_samples=active_config.rollout_samples,
            rollout_weight=active_config.rollout_weight,
            moon_defense_threshold=active_config.moon_defense_threshold,
        )
        for player_id in PLAYER_IDS
    }


def simulate_root_candidate(
    *,
    world: DeterminizedWorld,
    candidate: RootMoveCandidate,
    seed: int | None = None,
    playout_config: HeuristicPlayoutConfig | None = None,
) -> SearchRolloutResult:
    """Apply a root move in one sampled world and roll the hand to completion."""

    state = clone_determinized_state(world=world)
    if state.turn != world.root_player_id:
        raise InvalidStateError(
            f"Determinized world root player {int(world.root_player_id)} is not on turn."
        )

    starting_scores = {player_id: state.scores[player_id] for player_id in PLAYER_IDS}
    play_card(state=state, player_id=world.root_player_id, card=candidate.card)

    playout_bots = build_deterministic_playout_bots(config=playout_config)
    playout_rngs = _build_playout_rngs(seed=world.sample_seed if seed is None else seed)
    _play_hand_to_completion(state=state, playout_bots=playout_bots, playout_rngs=playout_rngs)

    summary = summarize_rollout(
        world=world,
        candidate=candidate,
        starting_scores=starting_scores,
        final_state=state,
    )
    return SearchRolloutResult(summary=summary, final_state=state)


def summarize_rollout(
    *,
    world: DeterminizedWorld,
    candidate: RootMoveCandidate,
    starting_scores: Mapping[PlayerId, int],
    final_state: GameState,
) -> SearchRolloutSummary:
    """Project immutable scoring outputs from a completed simulated hand."""

    if not is_hand_over(final_state):
        raise InvalidStateError("Cannot summarize a rollout before the hand is complete.")
    if not final_state.hand_scored:
        raise InvalidStateError("Completed rollout state must already be hand-scored.")

    projected_hand_points_raw = hand_points(final_state.taken_tricks)
    projected_score_deltas_raw = {
        player_id: final_state.scores[player_id] - starting_scores[player_id]
        for player_id in PLAYER_IDS
    }
    projected_scores_raw = {
        player_id: final_state.scores[player_id]
        for player_id in PLAYER_IDS
    }
    return SearchRolloutSummary(
        world_sample_index=world.sample_index,
        world_sample_seed=world.sample_seed,
        root_player_id=world.root_player_id,
        candidate=candidate,
        projected_hand_points=MappingProxyType(projected_hand_points_raw),
        projected_score_deltas=MappingProxyType(projected_score_deltas_raw),
        projected_scores=MappingProxyType(projected_scores_raw),
        root_utility=-float(projected_score_deltas_raw[world.root_player_id]),
    )


def _play_hand_to_completion(
    *,
    state: GameState,
    playout_bots: Mapping[PlayerId, Bot],
    playout_rngs: Mapping[PlayerId, random.Random],
) -> None:
    while not is_hand_over(state):
        player_id = state.turn
        if player_id is None:
            raise InvalidStateError("Cannot continue playout without an active turn.")
        bot = playout_bots[player_id]
        card = bot.choose_play(state=state, rng=playout_rngs[player_id])
        play_card(state=state, player_id=player_id, card=card)


def _build_playout_rngs(*, seed: int) -> Mapping[PlayerId, random.Random]:
    rng = random.Random(seed)
    return MappingProxyType(
        {
            player_id: random.Random(rng.randrange(0, 2**63))
            for player_id in PLAYER_IDS
        }
    )


__all__ = [
    "HeuristicPlayoutConfig",
    "SearchRolloutResult",
    "SearchRolloutSummary",
    "build_deterministic_playout_bots",
    "clone_determinized_state",
    "simulate_root_candidate",
    "summarize_rollout",
]
