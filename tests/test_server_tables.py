from pathlib import Path

import pytest

import hearts_ai.bots.runtime as bot_runtime_module
from hearts_ai.engine.game import is_hand_over
from hearts_ai.engine.record import replay_jsonl
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.scoring import trick_points
from hearts_ai.server.state_views import table_snapshot
from hearts_ai.server.tables import InvalidTableActionError, TableManager, UnauthorizedError


def test_table_starts_after_all_seats_filled() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Jason", target_score=50, seed=7)

    assert table.phase == "lobby"
    manager.claim_seat(table.table_code, player_secret=player_secret, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    table = manager.get_table(table.table_code)
    assert table.phase in {"passing", "playing", "game_over"}
    assert table.is_started() is True


def test_all_bot_table_runs_to_game_over() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=20, seed=1)
    manager.add_bot(table.table_code, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    for _ in range(2000):
        table = manager.get_table(table.table_code)
        if table.phase == "game_over":
            break
        manager.advance_one_action(table.table_code, player_secret=player_secret)

    finished = manager.get_table(table.table_code)
    assert finished.phase == "game_over"
    assert any(score >= 20 for score in finished.state.scores.values())


def test_all_heuristic_bot_table_is_deterministic() -> None:
    manager_one = TableManager()
    table_one, player_secret_one = manager_one.create_table(display_name="Host", target_score=20, seed=1)
    manager_one.add_bot(table_one.table_code, seat=0, bot_name="heuristic")
    manager_one.add_bot(table_one.table_code, seat=1, bot_name="heuristic")
    manager_one.add_bot(table_one.table_code, seat=2, bot_name="heuristic")
    manager_one.add_bot(table_one.table_code, seat=3, bot_name="heuristic")

    for _ in range(2000):
        current = manager_one.get_table(table_one.table_code)
        if current.phase == "game_over":
            break
        manager_one.advance_one_action(table_one.table_code, player_secret=player_secret_one)

    finished_one = manager_one.get_table(table_one.table_code)
    assert finished_one.phase == "game_over"

    manager_two = TableManager()
    table_two, player_secret_two = manager_two.create_table(display_name="Host", target_score=20, seed=1)
    manager_two.add_bot(table_two.table_code, seat=0, bot_name="heuristic")
    manager_two.add_bot(table_two.table_code, seat=1, bot_name="heuristic")
    manager_two.add_bot(table_two.table_code, seat=2, bot_name="heuristic")
    manager_two.add_bot(table_two.table_code, seat=3, bot_name="heuristic")

    for _ in range(2000):
        current = manager_two.get_table(table_two.table_code)
        if current.phase == "game_over":
            break
        manager_two.advance_one_action(table_two.table_code, player_secret=player_secret_two)

    finished_two = manager_two.get_table(table_two.table_code)
    assert finished_two.phase == "game_over"
    assert finished_one.state.scores == finished_two.state.scores


def test_add_bot_persists_bot_type_in_table_and_snapshot() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=7)
    manager.claim_seat(table.table_code, player_secret=player_secret, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2, bot_name="heuristic")
    manager.add_bot(table.table_code, seat=3, bot_name="heuristic")

    current = manager.get_table(table.table_code)
    assert current.bot_name_for_seat(1) == "random"
    assert current.bot_name_for_seat(2) == "heuristic"
    assert current.bot_name_for_seat(3) == "heuristic"

    snapshot = table_snapshot(current, viewer_secret=player_secret)
    seats = {seat["seat"]: seat for seat in snapshot["seats"]}
    assert seats[1]["bot_name"] == "random"
    assert seats[2]["bot_name"] == "heuristic"
    assert seats[3]["bot_name"] == "heuristic"


def test_viewer_advisory_bot_preference_persists_in_snapshot() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=7)

    initial_snapshot = table_snapshot(table, viewer_secret=player_secret)
    assert initial_snapshot["viewer_advisory_bot_name"] == "heuristic_v3"

    manager.set_viewer_advisory_bot(table.table_code, player_secret=player_secret, bot_name="heuristic_v2")
    updated = manager.get_table(table.table_code)
    updated_snapshot = table_snapshot(updated, viewer_secret=player_secret)
    assert updated_snapshot["viewer_advisory_bot_name"] == "heuristic_v2"


def test_viewer_advisory_bot_preference_rejects_unknown_bot_type() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=7)

    with pytest.raises(InvalidTableActionError):
        manager.set_viewer_advisory_bot(table.table_code, player_secret=player_secret, bot_name="unknown-bot")


def test_snapshot_includes_viewer_pass_recommendation_for_supported_bot() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=7)
    manager.claim_seat(table.table_code, player_secret=player_secret, seat=0)
    manager.add_bot(table.table_code, seat=1, bot_name="random")
    manager.add_bot(table.table_code, seat=2, bot_name="random")
    manager.add_bot(table.table_code, seat=3, bot_name="random")
    manager.set_viewer_advisory_bot(table.table_code, player_secret=player_secret, bot_name="heuristic_v3")

    snapshot = table_snapshot(manager.get_table(table.table_code), viewer_secret=player_secret)
    recommendation = snapshot["debug_viewer_recommendation"]
    assert recommendation is not None
    assert recommendation["status"] == "ok"
    assert recommendation["decision_kind"] == "pass"
    assert recommendation["bot_name"] == "heuristic_v3"
    payload = recommendation["payload"]
    assert isinstance(payload.get("selected_cards"), list)
    assert len(payload.get("selected_cards")) == snapshot["pass_count"]


def test_snapshot_marks_unsupported_viewer_recommendation_bot() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=7)
    manager.claim_seat(table.table_code, player_secret=player_secret, seat=0)
    manager.add_bot(table.table_code, seat=1, bot_name="random")
    manager.add_bot(table.table_code, seat=2, bot_name="random")
    manager.add_bot(table.table_code, seat=3, bot_name="random")
    manager.set_viewer_advisory_bot(table.table_code, player_secret=player_secret, bot_name="random")

    snapshot = table_snapshot(manager.get_table(table.table_code), viewer_secret=player_secret)
    recommendation = snapshot["debug_viewer_recommendation"]
    assert recommendation is not None
    assert recommendation["status"] == "unsupported_bot"
    assert recommendation["bot_name"] == "random"


def test_add_bot_rejects_unknown_bot_type() -> None:
    manager = TableManager()
    table, _ = manager.create_table(display_name="Host", target_score=50, seed=7)

    with pytest.raises(InvalidTableActionError):
        manager.add_bot(table.table_code, seat=0, bot_name="unknown-bot")


def test_add_bot_updates_existing_bot_type() -> None:
    manager = TableManager()
    table, _ = manager.create_table(display_name="Host", target_score=50, seed=7)
    manager.add_bot(table.table_code, seat=1, bot_name="random")
    manager.add_bot(table.table_code, seat=1, bot_name="heuristic")

    current = manager.get_table(table.table_code)
    assert current.bot_name_for_seat(1) == "heuristic"


def test_server_table_reuses_persistent_bot_instances_across_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[tuple[str, int]] = []
    real_create_bot = bot_runtime_module.create_bot

    def _counting_create_bot(bot_name, player_id):
        created.append((bot_name, int(player_id)))
        return real_create_bot(bot_name, player_id=player_id)

    monkeypatch.setattr(bot_runtime_module, "create_bot", _counting_create_bot)

    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=20, seed=19)
    manager.add_bot(table.table_code, seat=0, bot_name="random")
    manager.add_bot(table.table_code, seat=1, bot_name="random")
    manager.add_bot(table.table_code, seat=2, bot_name="random")
    manager.add_bot(table.table_code, seat=3, bot_name="random")

    assert sorted(created) == [("random", 0), ("random", 1), ("random", 2), ("random", 3)]

    for _ in range(20):
        manager.advance_one_action(table.table_code, player_secret=host_secret)

    assert sorted(created) == [("random", 0), ("random", 1), ("random", 2), ("random", 3)]


def test_add_bot_rejects_configuration_after_game_start() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=7)
    manager.claim_seat(table.table_code, player_secret=player_secret, seat=0)
    manager.add_bot(table.table_code, seat=1, bot_name="random")
    manager.add_bot(table.table_code, seat=2, bot_name="random")
    manager.add_bot(table.table_code, seat=3, bot_name="random")

    started = manager.get_table(table.table_code)
    assert started.phase in {"passing", "playing"}

    with pytest.raises(InvalidTableActionError):
        manager.add_bot(table.table_code, seat=1, bot_name="heuristic")


def test_state_snapshot_hides_other_hands() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Human", target_score=50, seed=11)
    manager.claim_seat(table.table_code, player_secret=player_secret, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    table = manager.get_table(table.table_code)
    public_snapshot = table_snapshot(table)
    private_snapshot = table_snapshot(table, viewer_secret=player_secret)

    assert public_snapshot["viewer_hand"] == []
    assert private_snapshot["phase"] == "passing"
    assert len(private_snapshot["viewer_hand"]) == 13


def test_human_plus_bots_game_reaches_game_over_without_bot_legal_move_crash() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Human", target_score=20, seed=3)
    manager.claim_seat(table.table_code, player_secret=player_secret, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    for _ in range(2000):
        current = manager.get_table(table.table_code)
        if current.phase == "game_over":
            break
        if current.phase == "passing":
            if 0 in current.pending_passes:
                manager.advance_one_action(table.table_code, player_secret=player_secret)
                continue
            hand = sorted(current.state.hands[0])
            cards = [str(card) for card in hand[: current.config.pass_count]]
            manager.submit_pass(table.table_code, player_secret=player_secret, cards=cards)
            continue
        if current.phase == "playing":
            if is_hand_over(current.state):
                manager.advance_one_action(table.table_code, player_secret=player_secret)
                continue
            if current.state.turn == 0:
                moves = legal_moves(current.state, 0)
                manager.play_card(table.table_code, player_secret=player_secret, card=str(moves[0]))
            else:
                manager.advance_one_action(table.table_code, player_secret=player_secret)
            continue
        if current.phase == "hand_scoring":
            manager.advance_one_action(table.table_code, player_secret=player_secret)
            continue

    assert manager.get_table(table.table_code).phase == "game_over"


def test_persistence_writes_replay_and_summary(tmp_path: Path) -> None:
    manager = TableManager.with_persistence(records_dir=tmp_path)
    table, player_secret = manager.create_table(display_name="Host", target_score=20, seed=13)
    manager.add_bot(table.table_code, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    for _ in range(2000):
        current = manager.get_table(table.table_code)
        if current.phase == "game_over":
            break
        manager.advance_one_action(table.table_code, player_secret=player_secret)

    finished = manager.get_table(table.table_code)
    assert finished.phase == "game_over"
    assert finished.record_path is not None
    assert finished.record_path.exists()
    assert finished.summary_path is not None
    assert finished.summary_path.exists()

    replayed = replay_jsonl(finished.record_path)
    assert len(replayed) == 1
    _, replayed_state = replayed[0]
    assert replayed_state.scores == finished.state.scores

    summary_lines = finished.summary_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(summary_lines) == 1


def test_advance_requires_host_or_seat_zero() -> None:
    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=20, seed=17)
    guest_secret = manager.join_table(table.table_code, display_name="Guest")

    manager.claim_seat(table.table_code, player_secret=host_secret, seat=1)
    manager.claim_seat(table.table_code, player_secret=guest_secret, seat=2)
    manager.add_bot(table.table_code, seat=0)
    manager.add_bot(table.table_code, seat=3)

    with pytest.raises(UnauthorizedError):
        manager.advance_one_action(table.table_code, player_secret=guest_secret)


def test_advance_reports_waiting_when_human_action_required() -> None:
    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=20, seed=37)
    manager.claim_seat(table.table_code, player_secret=host_secret, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    # Drive bot pass submissions until only the human pass is outstanding.
    for _ in range(20):
        current = manager.get_table(table.table_code)
        if current.phase == "passing" and all(player in current.pending_passes for player in (1, 2, 3)):
            break
        result = manager.advance_one_action(table.table_code, player_secret=host_secret)
        assert result.advanced is True
    else:
        raise AssertionError("Did not reach waiting-on-human pass state.")

    current = manager.get_table(table.table_code)
    assert current.phase == "passing"
    assert 0 not in current.pending_passes
    waiting_version = current.version

    waiting_pass = manager.advance_one_action(table.table_code, player_secret=host_secret)
    assert waiting_pass.advanced is False
    assert waiting_pass.action is None
    assert waiting_pass.can_advance is False
    assert manager.get_table(table.table_code).version == waiting_version

    hand = sorted(current.state.hands[0])
    cards = [str(card) for card in hand[: current.config.pass_count]]
    manager.submit_pass(table.table_code, player_secret=host_secret, cards=cards)

    applied = manager.advance_one_action(table.table_code, player_secret=host_secret)
    assert applied.advanced is True
    assert applied.action == "pass_applied"

    # Advance bots until play blocks on the human turn.
    for _ in range(60):
        current = manager.get_table(table.table_code)
        if current.phase == "playing" and current.state.turn == 0:
            break
        step = manager.advance_one_action(table.table_code, player_secret=host_secret)
        assert step.advanced is True
    else:
        raise AssertionError("Did not reach waiting-on-human play state.")

    current = manager.get_table(table.table_code)
    assert current.phase == "playing"
    assert current.state.turn == 0
    waiting_version = current.version

    waiting_play = manager.advance_one_action(table.table_code, player_secret=host_secret)
    assert waiting_play.advanced is False
    assert waiting_play.action is None
    assert waiting_play.can_advance is False
    assert manager.get_table(table.table_code).version == waiting_version


def test_snapshot_exposes_last_trick_and_seat_hand_points() -> None:
    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=30, seed=23)
    manager.add_bot(table.table_code, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    for _ in range(400):
        current = manager.get_table(table.table_code)
        if current.state.trick_number >= 1 and not current.state.trick_in_progress:
            break
        manager.advance_one_action(table.table_code, player_secret=host_secret)

    current = manager.get_table(table.table_code)
    snapshot = table_snapshot(current, viewer_secret=host_secret)

    expected_hand_points = {
        str(int(player_id)): sum(trick_points(trick) for trick in current.state.taken_tricks[player_id])
        for player_id in current.state.taken_tricks
    }
    assert snapshot["seat_hand_points"] == expected_hand_points
    assert snapshot["last_trick"] is not None
    assert snapshot["last_trick"]["trick_seq"] == current.state.trick_number
    assert snapshot["last_trick"]["winner"] == int(current.state.turn)
    expected_cards = [
        {"player_id": int(player_id), "card": str(card)}
        for player_id, card in current.state.taken_tricks[current.state.turn][-1]
    ]
    assert snapshot["last_trick"]["cards"] == expected_cards


def test_snapshot_resets_last_trick_and_hand_points_on_new_hand() -> None:
    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=100, seed=29)
    manager.add_bot(table.table_code, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    start_hand = manager.get_table(table.table_code).state.hand_number
    for _ in range(5000):
        current = manager.get_table(table.table_code)
        if current.state.hand_number > start_hand and current.state.trick_number == 0:
            break
        manager.advance_one_action(table.table_code, player_secret=host_secret)

    current = manager.get_table(table.table_code)
    snapshot = table_snapshot(current, viewer_secret=host_secret)
    assert current.state.hand_number > start_hand
    assert snapshot["trick_number"] == 0
    assert snapshot["last_trick"] is None
    assert snapshot["seat_hand_points"] == {"0": 0, "1": 0, "2": 0, "3": 0}


def test_snapshot_exposes_heuristic_v2_debug_decision_payload() -> None:
    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=30, seed=31)
    manager.add_bot(table.table_code, seat=0, bot_name="heuristic_v2")
    manager.add_bot(table.table_code, seat=1, bot_name="heuristic_v2")
    manager.add_bot(table.table_code, seat=2, bot_name="heuristic_v2")
    manager.add_bot(table.table_code, seat=3, bot_name="heuristic_v2")

    for _ in range(16):
        result = manager.advance_one_action(table.table_code, player_secret=host_secret)
        if result.action in {"bot_pass_submitted", "bot_card_played"}:
            break
    else:
        raise AssertionError("Did not capture a heuristic_v2 decision action.")

    current = manager.get_table(table.table_code)
    snapshot = table_snapshot(current, viewer_secret=host_secret)
    debug = snapshot["debug_last_bot_decision"]

    assert isinstance(debug, dict)
    assert debug["bot_name"] == "heuristic_v2"
    assert debug["decision_kind"] in {"pass", "play"}
    assert isinstance(debug["seat"], int)
    assert isinstance(debug["hand_number"], int)
    assert isinstance(debug["trick_number"], int)
    assert isinstance(debug["payload"], dict)
    if debug["decision_kind"] == "pass":
        assert "selected_cards" in debug["payload"]
        assert "candidates" in debug["payload"]
    else:
        assert "chosen_card" in debug["payload"]
        assert "candidates" in debug["payload"]


def test_snapshot_debug_decision_is_none_when_no_heuristic_v2_action() -> None:
    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=30, seed=33)
    manager.add_bot(table.table_code, seat=0, bot_name="random")
    manager.add_bot(table.table_code, seat=1, bot_name="random")
    manager.add_bot(table.table_code, seat=2, bot_name="random")
    manager.add_bot(table.table_code, seat=3, bot_name="random")

    manager.advance_one_action(table.table_code, player_secret=host_secret)
    current = manager.get_table(table.table_code)
    snapshot = table_snapshot(current, viewer_secret=host_secret)
    assert snapshot["debug_last_bot_decision"] is None


def test_snapshot_exposes_heuristic_v3_debug_decision_payload() -> None:
    manager = TableManager()
    table, host_secret = manager.create_table(display_name="Host", target_score=30, seed=35)
    manager.add_bot(table.table_code, seat=0, bot_name="heuristic_v3")
    manager.add_bot(table.table_code, seat=1, bot_name="heuristic_v3")
    manager.add_bot(table.table_code, seat=2, bot_name="heuristic_v3")
    manager.add_bot(table.table_code, seat=3, bot_name="heuristic_v3")

    for _ in range(16):
        result = manager.advance_one_action(table.table_code, player_secret=host_secret)
        if result.action in {"bot_pass_submitted", "bot_card_played"}:
            break
    else:
        raise AssertionError("Did not capture a heuristic_v3 decision action.")

    current = manager.get_table(table.table_code)
    snapshot = table_snapshot(current, viewer_secret=host_secret)
    debug = snapshot["debug_last_bot_decision"]

    assert isinstance(debug, dict)
    assert debug["bot_name"] == "heuristic_v3"
