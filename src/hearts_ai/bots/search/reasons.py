from __future__ import annotations

from hearts_ai.bots.reasons import SerializedReasonPayload, register_default_reason_serializer
from hearts_ai.bots.search.models import SearchPlayDecisionReason

_REGISTERED = False


def serialize_search_play_decision_reason(reason: SearchPlayDecisionReason) -> SerializedReasonPayload:
    return {
        "chosen_card": str(reason.chosen_card),
        "mode": str(reason.mode),
        "trick_number": int(reason.trick_number),
        "requested_world_count": int(reason.requested_world_count),
        "world_count": int(reason.world_count),
        "world_base_seed": int(reason.world_base_seed),
        "selection_policy": [str(metric) for metric in reason.selection_policy],
        "selection_source": str(reason.selection_source),
        "fallback_message": None if reason.fallback_message is None else str(reason.fallback_message),
        "candidates": [
            {
                "card": str(candidate.card),
                "mode": str(candidate.mode),
                "candidate_index": int(candidate.candidate_index),
                "selection_rank": int(candidate.selection_rank),
                "selected": bool(candidate.selected),
                "follows_led_suit": bool(candidate.follows_led_suit),
                "is_point_card": bool(candidate.is_point_card),
                "trick_points_so_far": int(candidate.trick_points_so_far),
                "average_projected_hand_points": float(candidate.average_projected_hand_points),
                "average_projected_score_delta": float(candidate.average_projected_score_delta),
                "average_projected_total_score": float(candidate.average_projected_total_score),
                "average_root_utility": float(candidate.average_root_utility),
            }
            for candidate in reason.candidates
        ],
    }


def register_search_reason_serializers() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    register_default_reason_serializer(
        SearchPlayDecisionReason,
        serialize_search_play_decision_reason,
    )
    _REGISTERED = True


register_search_reason_serializers()


__all__ = [
    "register_search_reason_serializers",
    "serialize_search_play_decision_reason",
]
