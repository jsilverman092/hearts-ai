import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

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
