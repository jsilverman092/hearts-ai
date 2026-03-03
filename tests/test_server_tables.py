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

