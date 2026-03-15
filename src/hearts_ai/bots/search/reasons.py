from __future__ import annotations

from hearts_ai.bots.reasons import SerializedReasonPayload, register_default_reason_serializer
from hearts_ai.bots.search.models import (
    SearchBaselineComparisonReason,
    SearchChosenMoveReason,
    SearchComparedMoveReason,
    SearchPlayDecisionReason,
)

_REGISTERED = False


def _serialize_search_chosen_move_reason(reason: SearchChosenMoveReason) -> SerializedReasonPayload:
    return {
        "card": str(reason.card),
        "mode": str(reason.mode),
        "candidate_index": int(reason.candidate_index),
        "follows_led_suit": bool(reason.follows_led_suit),
        "is_point_card": bool(reason.is_point_card),
        "trick_points_so_far": int(reason.trick_points_so_far),
        "average_projected_raw_hand_points": (
            float(reason.average_projected_raw_hand_points)
            if reason.average_projected_raw_hand_points is not None
            else None
        ),
        "average_projected_hand_points": (
            float(reason.average_projected_hand_points)
            if reason.average_projected_hand_points is not None
            else None
        ),
        "average_projected_score_delta": (
            float(reason.average_projected_score_delta)
            if reason.average_projected_score_delta is not None
            else None
        ),
        "average_projected_total_score": (
            float(reason.average_projected_total_score)
            if reason.average_projected_total_score is not None
            else None
        ),
        "average_root_utility": (
            float(reason.average_root_utility)
            if reason.average_root_utility is not None
            else None
        ),
    }


def _serialize_search_compared_move_reason(reason: SearchComparedMoveReason) -> SerializedReasonPayload:
    return {
        "card": str(reason.card),
        "mode": str(reason.mode),
        "candidate_index": int(reason.candidate_index),
        "selection_rank": int(reason.selection_rank),
        "follows_led_suit": bool(reason.follows_led_suit),
        "is_point_card": bool(reason.is_point_card),
        "trick_points_so_far": int(reason.trick_points_so_far),
        "average_projected_raw_hand_points": float(reason.average_projected_raw_hand_points),
        "average_projected_hand_points": float(reason.average_projected_hand_points),
        "average_projected_score_delta": float(reason.average_projected_score_delta),
        "average_projected_total_score": float(reason.average_projected_total_score),
        "average_root_utility": float(reason.average_root_utility),
    }


def _serialize_search_baseline_comparison_reason(
    reason: SearchBaselineComparisonReason,
) -> SerializedReasonPayload:
    return {
        "baseline_bot_name": str(reason.baseline_bot_name),
        "agrees_with_search": bool(reason.agrees_with_search),
        "baseline": _serialize_search_compared_move_reason(reason.baseline),
        "mean_projected_score_delta_advantage": float(reason.mean_projected_score_delta_advantage),
        "mean_root_utility_gain": float(reason.mean_root_utility_gain),
        "worlds_search_better": int(reason.worlds_search_better),
        "worlds_tied": int(reason.worlds_tied),
        "worlds_baseline_better": int(reason.worlds_baseline_better),
        "worst_case_root_utility_loss": float(reason.worst_case_root_utility_loss),
        "best_case_root_utility_gain": float(reason.best_case_root_utility_gain),
    }


def serialize_search_play_decision_reason(reason: SearchPlayDecisionReason) -> SerializedReasonPayload:
    return {
        "chosen_card": str(reason.chosen_card),
        "mode": str(reason.mode),
        "trick_number": int(reason.trick_number),
        "legal_move_count": int(reason.legal_move_count),
        "evaluated_candidate_count": int(reason.evaluated_candidate_count),
        "current_trick_size": int(reason.current_trick_size),
        "led_suit": reason.led_suit.short_name if reason.led_suit is not None else None,
        "chosen": _serialize_search_chosen_move_reason(reason.chosen),
        "requested_world_count": int(reason.requested_world_count),
        "world_count": int(reason.world_count),
        "world_base_seed": int(reason.world_base_seed),
        "selection_policy": [str(metric) for metric in reason.selection_policy],
        "selection_source": str(reason.selection_source),
        "fallback_message": None if reason.fallback_message is None else str(reason.fallback_message),
        "baseline_comparison": (
            _serialize_search_baseline_comparison_reason(reason.baseline_comparison)
            if reason.baseline_comparison is not None
            else None
        ),
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
                "average_projected_raw_hand_points": float(candidate.average_projected_raw_hand_points),
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
