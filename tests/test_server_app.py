import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from hearts_ai.engine.record import replay_jsonl
from hearts_ai.server.app import create_app
from hearts_ai.server.tables import TableManager


def test_root_serves_ui_shell() -> None:
    app = create_app(table_manager=TableManager())
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Hearts AI Live" in response.text


def test_websocket_join_with_existing_secret() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=9)
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "schema_version": 1,
                    "type": "join_table",
                    "table_code": table.table_code,
                    "display_name": "Host",
                    "player_secret": player_secret,
                }
            )
            joined = ws.receive_json()
            assert joined["type"] == "table_joined"
            assert joined["player_secret"] == player_secret

            snapshot = ws.receive_json()
            assert snapshot["type"] == "state_snapshot"
            assert snapshot["payload"]["table_code"] == table.table_code


def test_rest_claim_seat_broadcasts_snapshot() -> None:
    manager = TableManager()
    table, player_secret = manager.create_table(display_name="Host", target_score=50, seed=5)
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "schema_version": 1,
                    "type": "join_table",
                    "table_code": table.table_code,
                    "display_name": "Host",
                    "player_secret": player_secret,
                }
            )
            ws.receive_json()
            ws.receive_json()

            response = client.post(
                f"/tables/{table.table_code}/seats/0",
                json={"player_secret": player_secret},
            )
            assert response.status_code == 200

            broadcast = ws.receive_json()
            assert broadcast["type"] == "state_snapshot"
            assert broadcast["payload"]["viewer_seat"] == 0


def _drive_game_to_completion(client: TestClient, *, table_code: str, player_secret: str) -> dict[str, int]:
    max_steps = 1000
    for _ in range(max_steps):
        snapshot = client.get(
            f"/tables/{table_code}",
            params={"player_secret": player_secret},
        ).json()

        phase = snapshot["phase"]
        if phase == "game_over":
            return snapshot["scores"]

        if phase == "passing":
            viewer_seat = snapshot["viewer_seat"]
            assert viewer_seat is not None
            viewer_key = str(viewer_seat)
            if snapshot["pass_submissions"].get(viewer_key):
                continue
            pass_count = int(snapshot["pass_count"])
            cards = sorted(snapshot["viewer_hand"])[:pass_count]
            response = client.post(
                f"/tables/{table_code}/pass",
                json={"player_secret": player_secret, "cards": cards},
            )
            assert response.status_code == 200
            continue

        if phase == "playing" and snapshot["turn"] == snapshot["viewer_seat"]:
            legal = snapshot["viewer_legal_moves"]
            assert legal
            response = client.post(
                f"/tables/{table_code}/play",
                json={"player_secret": player_secret, "card": legal[0]},
            )
            assert response.status_code == 200
            continue

    raise AssertionError(f"Game did not complete within {max_steps} steps.")


def test_server_integration_full_game_deterministic_with_websocket(tmp_path) -> None:
    manager = TableManager.with_persistence(records_dir=tmp_path)
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            created = client.post(
                "/tables",
                json={"display_name": "Host", "target_score": 30, "seed": 123},
            ).json()
            table_code = created["table_code"]
            player_secret = created["player_secret"]

            ws.send_json(
                {
                    "schema_version": 1,
                    "type": "join_table",
                    "table_code": table_code,
                    "display_name": "Host",
                    "player_secret": player_secret,
                }
            )
            joined = ws.receive_json()
            assert joined["type"] == "table_joined"
            _ = ws.receive_json()

            assert client.post(
                f"/tables/{table_code}/seats/0",
                json={"player_secret": player_secret},
            ).status_code == 200
            assert client.post(f"/tables/{table_code}/bots/1").status_code == 200
            assert client.post(f"/tables/{table_code}/bots/2").status_code == 200
            assert client.post(f"/tables/{table_code}/bots/3").status_code == 200

            scores_one = _drive_game_to_completion(
                client,
                table_code=table_code,
                player_secret=player_secret,
            )

        created_two = client.post(
            "/tables",
            json={"display_name": "Host", "target_score": 30, "seed": 123},
        ).json()
        table_code_two = created_two["table_code"]
        player_secret_two = created_two["player_secret"]
        assert client.post(
            f"/tables/{table_code_two}/seats/0",
            json={"player_secret": player_secret_two},
        ).status_code == 200
        assert client.post(f"/tables/{table_code_two}/bots/1").status_code == 200
        assert client.post(f"/tables/{table_code_two}/bots/2").status_code == 200
        assert client.post(f"/tables/{table_code_two}/bots/3").status_code == 200
        scores_two = _drive_game_to_completion(
            client,
            table_code=table_code_two,
            player_secret=player_secret_two,
        )

    assert scores_one == scores_two

    table = manager.get_table(table_code)
    assert table.record_path is not None
    replayed = replay_jsonl(table.record_path)
    assert len(replayed) == 1
    _, replayed_state = replayed[0]
    assert {str(player): score for player, score in replayed_state.scores.items()} == scores_one
