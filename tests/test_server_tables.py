from pathlib import Path

from hearts_ai.engine.record import replay_jsonl
from hearts_ai.engine.rules import legal_moves
from hearts_ai.server.state_views import table_snapshot
from hearts_ai.server.tables import TableManager


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
    table, _ = manager.create_table(display_name="Host", target_score=20, seed=1)
    manager.add_bot(table.table_code, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

    table = manager.get_table(table.table_code)
    assert table.phase == "game_over"
    assert any(score >= 20 for score in table.state.scores.values())


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

    for _ in range(600):
        current = manager.get_table(table.table_code)
        if current.phase == "game_over":
            break
        if current.phase == "passing":
            if 0 in current.pending_passes:
                continue
            hand = sorted(current.state.hands[0])
            cards = [str(card) for card in hand[: current.config.pass_count]]
            manager.submit_pass(table.table_code, player_secret=player_secret, cards=cards)
            continue
        if current.phase == "playing":
            if current.state.turn == 0:
                moves = legal_moves(current.state, 0)
                manager.play_card(table.table_code, player_secret=player_secret, card=str(moves[0]))
            continue

    assert manager.get_table(table.table_code).phase == "game_over"


def test_persistence_writes_replay_and_summary(tmp_path: Path) -> None:
    manager = TableManager.with_persistence(records_dir=tmp_path)
    table, _ = manager.create_table(display_name="Host", target_score=20, seed=13)
    manager.add_bot(table.table_code, seat=0)
    manager.add_bot(table.table_code, seat=1)
    manager.add_bot(table.table_code, seat=2)
    manager.add_bot(table.table_code, seat=3)

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
