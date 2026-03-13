from __future__ import annotations

import random
from collections.abc import Callable
from typing import Literal

from hearts_ai.bots.heuristic.models import PlayCandidateReason, PlayDecisionReason, _QUEEN_SPADES
from hearts_ai.bots.heuristic.rollout import _rollout_score_base, _shared_rollout_sample_seeds
from hearts_ai.bots.heuristic.scoring import _score_discard_priority_base
from hearts_ai.engine.cards import Card, Suit
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.scoring import trick_points
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PlayerId


def _play_mode(state: GameState, legal: list[Card]) -> Literal["lead", "follow", "discard"]:
    if not state.trick_in_progress:
        return "lead"
    led_suit = state.trick_in_progress[0][1].suit
    has_follow = any(card.suit == led_suit for card in legal)
    return "follow" if has_follow else "discard"


def _moon_defense_target(state: GameState, player_id: PlayerId, threshold: int) -> PlayerId | None:
    hand_points = {
        pid: sum(trick_points(trick) for trick in state.taken_tricks[pid])
        for pid in state.taken_tricks
    }
    sole_point_holder = [pid for pid, points in hand_points.items() if points > 0]
    if len(sole_point_holder) != 1:
        return None
    target = sole_point_holder[0]
    if target == player_id:
        return None
    target_points = hand_points[target]
    target_tricks = state.taken_tricks[target]
    hearts_taken = sum(
        1 for trick in target_tricks for _, card in trick if card.suit == Suit.HEARTS
    )
    qs_taken = any(
        card == _QUEEN_SPADES for trick in target_tricks for _, card in trick
    )
    hearts_heavy_trigger = 8
    qs_plus_hearts_trigger = 2
    high_total_trigger = max(threshold + 4, 16)
    if hearts_taken >= hearts_heavy_trigger:
        return target
    if qs_taken and hearts_taken >= qs_plus_hearts_trigger:
        return target
    if target_points >= high_total_trigger:
        return target
    return None


def _choose_play_with_reason(
    state: GameState,
    player_id: PlayerId,
    rollout_samples: int,
    rollout_weight: float,
    moon_defense_threshold: int,
    score_play_candidate: Callable[
        [GameState, PlayerId, list[Card], Card, Literal["lead", "follow", "discard"], PlayerId | None],
        tuple[float, list[str]],
    ],
    rng: random.Random,
) -> tuple[Card, PlayDecisionReason]:
    legal = legal_moves(state=state, player_id=player_id)
    if not legal:
        raise InvalidStateError(f"No legal moves available for player {int(player_id)}.")

    mode = _play_mode(state=state, legal=legal)
    moon_target = _moon_defense_target(
        state=state,
        player_id=player_id,
        threshold=moon_defense_threshold,
    )
    shared_rollout_sample_seeds = _shared_rollout_sample_seeds(
        samples=rollout_samples,
        rng=rng,
    )
    candidate_reasons: list[PlayCandidateReason] = []
    for card in legal:
        base_score, tags = score_play_candidate(
            state=state,
            player_id=player_id,
            legal=legal,
            card=card,
            mode=mode,
            moon_target=moon_target,
        )
        rollout_score = _rollout_score_base(
            state=state,
            player_id=player_id,
            card=card,
            mode=mode,
            moon_target=moon_target,
            samples=rollout_samples,
            sample_seeds=shared_rollout_sample_seeds,
            rng=rng,
        )
        total_score = base_score + (rollout_weight * rollout_score)
        candidate_reasons.append(
            PlayCandidateReason(
                card=card,
                base_score=base_score,
                rollout_score=rollout_score,
                total_score=total_score,
                tags=tuple(tags),
            )
        )

    ordered_candidates = tuple(
        sorted(
            candidate_reasons,
            key=lambda entry: (
                entry.total_score,
                *_move_tiebreak(mode=mode, card=entry.card),
            ),
            reverse=True,
        )
    )
    chosen = ordered_candidates[0].card
    play_reason = PlayDecisionReason(
        mode=mode,
        trick_number=state.trick_number,
        chosen_card=chosen,
        moon_defense_target=moon_target,
        candidates=ordered_candidates,
    )
    return chosen, play_reason


def _move_tiebreak(mode: Literal["lead", "follow", "discard"], card: Card) -> tuple[int, int, int]:
    if mode == "lead":
        # Prefer lower lead cards on ties.
        return (-int(card.rank), -int(card.suit), 0)
    priority = _score_discard_priority_base(card)
    return (priority[0], priority[1], priority[2])
