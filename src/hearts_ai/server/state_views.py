from __future__ import annotations

from typing import Any

from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.scoring import trick_points
from hearts_ai.engine.types import PLAYER_IDS
from hearts_ai.server.tables import Table


def table_snapshot(table: Table, *, viewer_secret: str | None = None) -> dict[str, Any]:
    viewer_seat = None
    viewer_can_control_pace = False
    viewer_advisory_bot_name = table.viewer_advisory_bot_name(viewer_secret)
    if viewer_secret is not None:
        participant = table.participants.get(viewer_secret)
        viewer_seat = participant.seat if participant is not None else None
        viewer_can_control_pace = bool(
            participant is not None
            and (
                (table.host_secret is not None and viewer_secret == table.host_secret)
                or participant.seat == 0
            )
        )

    seats: list[dict[str, Any]] = []
    for player_id in PLAYER_IDS:
        if player_id in table.bot_seats:
            seat_kind = "bot"
            display_name = f"Bot {int(player_id)}"
            bot_name = table.bot_name_for_seat(player_id)
        else:
            secret = table.seat_secrets[player_id]
            if secret is None:
                seat_kind = "open"
                display_name = None
            else:
                seat_kind = "human"
                display_name = table.seat_display_name(player_id)
            bot_name = None
        seats.append(
            {
                "seat": int(player_id),
                "kind": seat_kind,
                "display_name": display_name,
                "bot_name": bot_name,
            }
        )

    trick_cards = [
        {"player_id": int(player_id), "card": str(card)} for player_id, card in table.state.trick_in_progress
    ]
    scores = {str(int(player_id)): table.state.scores[player_id] for player_id in PLAYER_IDS}
    seat_hand_points = {
        str(int(player_id)): sum(trick_points(trick) for trick in table.state.taken_tricks[player_id])
        for player_id in PLAYER_IDS
    }
    last_trick = (
        {
            "winner": int(table.last_trick.winner_id),
            "cards": [
                {"player_id": int(player_id), "card": str(card)}
                for player_id, card in table.last_trick.trick
            ],
            "points": table.last_trick.points,
            "trick_seq": table.last_trick.trick_seq,
        }
        if table.last_trick is not None
        else None
    )

    hand_cards: list[str] = []
    legal_for_viewer: list[str] = []
    if viewer_seat is not None and viewer_seat not in table.bot_seats:
        hand_cards = [str(card) for card in table.state.hands[viewer_seat]]
        if table.phase == "playing" and table.state.turn == viewer_seat:
            try:
                legal_for_viewer = [str(card) for card in legal_moves(table.state, viewer_seat)]
            except InvalidStateError:
                legal_for_viewer = []

    pass_status = {
        str(int(player_id)): player_id in table.pending_passes
        for player_id in PLAYER_IDS
        if table.phase == "passing"
    }

    return {
        "table_code": table.table_code,
        "phase": table.phase,
        "version": table.version,
        "seed": table.seed,
        "game_id": table.game_id,
        "record_path": str(table.record_path) if table.record_path is not None else None,
        "summary_path": str(table.summary_path) if table.summary_path is not None else None,
        "target_score": table.config.target_score,
        "pass_count": table.config.pass_count,
        "hand_number": table.state.hand_number,
        "trick_number": table.state.trick_number,
        "pass_direction": table.state.pass_direction,
        "hearts_broken": table.state.hearts_broken,
        "turn": int(table.state.turn) if table.state.turn is not None else None,
        "scores": scores,
        "seat_hand_points": seat_hand_points,
        "current_trick": trick_cards,
        "last_trick": last_trick,
        "seats": seats,
        "viewer_seat": int(viewer_seat) if viewer_seat is not None else None,
        "viewer_can_control_pace": viewer_can_control_pace,
        "viewer_advisory_bot_name": viewer_advisory_bot_name,
        "viewer_hand": hand_cards,
        "viewer_legal_moves": legal_for_viewer,
        "pass_submissions": pass_status,
        "debug_last_bot_decision": table.debug_last_bot_decision,
    }


__all__ = ["table_snapshot"]
