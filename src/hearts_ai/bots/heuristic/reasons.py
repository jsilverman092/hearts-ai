from __future__ import annotations

from hearts_ai.bots.heuristic.models import PassDecisionReason, PlayDecisionReason
from hearts_ai.bots.reasons import SerializedReasonPayload, register_default_reason_serializer

_REGISTERED = False


def serialize_pass_decision_reason(reason: PassDecisionReason) -> SerializedReasonPayload:
    return {
        "selected_cards": [str(card) for card in reason.selected_cards],
        "candidates": [
            {
                "card": str(candidate.card),
                "score": [int(value) for value in candidate.score],
            }
            for candidate in reason.candidates
        ],
    }


def serialize_play_decision_reason(reason: PlayDecisionReason) -> SerializedReasonPayload:
    return {
        "mode": str(reason.mode),
        "chosen_card": str(reason.chosen_card),
        "moon_defense_target": int(reason.moon_defense_target) if reason.moon_defense_target is not None else None,
        "candidates": [
            {
                "card": str(candidate.card),
                "base_score": float(candidate.base_score),
                "rollout_score": float(candidate.rollout_score),
                "total_score": float(candidate.total_score),
                "tags": [str(tag) for tag in candidate.tags],
            }
            for candidate in reason.candidates
        ],
    }


def register_heuristic_reason_serializers() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    register_default_reason_serializer(PassDecisionReason, serialize_pass_decision_reason)
    register_default_reason_serializer(PlayDecisionReason, serialize_play_decision_reason)
    _REGISTERED = True


register_heuristic_reason_serializers()


__all__ = [
    "register_heuristic_reason_serializers",
    "serialize_pass_decision_reason",
    "serialize_play_decision_reason",
]
