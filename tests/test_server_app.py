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
    assert 'id="quickSoloBtn"' in response.text
    assert 'id="botType"' in response.text
    assert 'id="autoplayBtn"' in response.text
    assert 'id="stepBtn"' in response.text
    assert 'id="paceRange"' in response.text


def test_create_table_rejects_non_boolean_auto_advance() -> None:
    app = create_app(table_manager=TableManager())
    with TestClient(app) as client:
        response = client.post(
            "/tables",
            json={
                "display_name": "Host",
                "target_score": 20,
                "seed": 13,
                "auto_advance": "true",
            },
        )
    assert response.status_code == 400
    assert "auto_advance" in response.json()["detail"]


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


def test_rest_set_viewer_advisory_bot_broadcasts_snapshot() -> None:
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
                f"/tables/{table.table_code}/viewer-advisory-bot",
                json={"player_secret": player_secret, "bot_name": "heuristic_v2"},
            )
            assert response.status_code == 200

            broadcast = ws.receive_json()
            assert broadcast["type"] == "state_snapshot"
            assert broadcast["payload"]["viewer_advisory_bot_name"] == "heuristic_v2"


def _drive_game_to_completion(client: TestClient, *, table_code: str, player_secret: str) -> dict[str, int]:
    max_steps = 3000
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
                response = client.post(
                    f"/tables/{table_code}/advance",
                    json={"player_secret": player_secret},
                )
                assert response.status_code == 200
                continue
            pass_count = int(snapshot["pass_count"])
            cards = sorted(snapshot["viewer_hand"])[:pass_count]
            response = client.post(
                f"/tables/{table_code}/pass",
                json={"player_secret": player_secret, "cards": cards},
            )
            assert response.status_code == 200
            continue

        if phase == "playing":
            if snapshot["turn"] == snapshot["viewer_seat"]:
                legal = snapshot["viewer_legal_moves"]
                if not legal:
                    response = client.post(
                        f"/tables/{table_code}/advance",
                        json={"player_secret": player_secret},
                    )
                    assert response.status_code == 200
                    continue
                response = client.post(
                    f"/tables/{table_code}/play",
                    json={"player_secret": player_secret, "card": legal[0]},
                )
                assert response.status_code == 200
                continue
            response = client.post(
                f"/tables/{table_code}/advance",
                json={"player_secret": player_secret},
            )
            assert response.status_code == 200
            continue

        if phase == "hand_scoring":
            response = client.post(
                f"/tables/{table_code}/advance",
                json={"player_secret": player_secret},
            )
            assert response.status_code == 200
            continue

    raise AssertionError(f"Game did not complete within {max_steps} steps.")


def _setup_single_player_table(client: TestClient, *, seed: int, bot_name: str = "random") -> tuple[str, str]:
    created = client.post(
        "/tables",
        json={"display_name": "Host", "target_score": 20, "seed": seed},
    ).json()
    table_code = created["table_code"]
    player_secret = created["player_secret"]
    assert client.post(
        f"/tables/{table_code}/seats/0",
        json={"player_secret": player_secret},
    ).status_code == 200
    assert client.post(f"/tables/{table_code}/bots/1", json={"bot_name": bot_name}).status_code == 200
    assert client.post(f"/tables/{table_code}/bots/2", json={"bot_name": bot_name}).status_code == 200
    assert client.post(f"/tables/{table_code}/bots/3", json={"bot_name": bot_name}).status_code == 200
    return table_code, player_secret


def test_advance_endpoint_waits_for_human_pass() -> None:
    manager = TableManager()
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        table_code, player_secret = _setup_single_player_table(client, seed=41)

        for _ in range(20):
            snapshot = client.get(
                f"/tables/{table_code}",
                params={"player_secret": player_secret},
            ).json()
            submissions = snapshot["pass_submissions"]
            if snapshot["phase"] == "passing" and all(submissions.get(str(seat)) for seat in (1, 2, 3)):
                break
            response = client.post(
                f"/tables/{table_code}/advance",
                json={"player_secret": player_secret},
            )
            assert response.status_code == 200
            assert response.json()["advanced"] is True
        else:
            raise AssertionError("Did not reach waiting-on-human pass state.")

        response = client.post(
            f"/tables/{table_code}/advance",
            json={"player_secret": player_secret},
        )
        payload = response.json()

        assert response.status_code == 200
        assert payload["advanced"] is False
        assert payload["action"] is None
        assert payload["can_advance"] is False
        assert payload["snapshot"]["phase"] == "passing"
        assert payload["snapshot"]["pass_submissions"]["0"] is False


def test_advance_endpoint_waits_for_human_play() -> None:
    manager = TableManager()
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        table_code, player_secret = _setup_single_player_table(client, seed=43)

        for _ in range(20):
            snapshot = client.get(
                f"/tables/{table_code}",
                params={"player_secret": player_secret},
            ).json()
            submissions = snapshot["pass_submissions"]
            if snapshot["phase"] == "passing" and all(submissions.get(str(seat)) for seat in (1, 2, 3)):
                break
            response = client.post(
                f"/tables/{table_code}/advance",
                json={"player_secret": player_secret},
            )
            assert response.status_code == 200
            assert response.json()["advanced"] is True
        else:
            raise AssertionError("Did not reach waiting-on-human pass state.")

        waiting_snapshot = client.get(
            f"/tables/{table_code}",
            params={"player_secret": player_secret},
        ).json()
        pass_count = int(waiting_snapshot["pass_count"])
        cards = sorted(waiting_snapshot["viewer_hand"])[:pass_count]
        response = client.post(
            f"/tables/{table_code}/pass",
            json={"player_secret": player_secret, "cards": cards},
        )
        assert response.status_code == 200

        response = client.post(
            f"/tables/{table_code}/advance",
            json={"player_secret": player_secret},
        )
        assert response.status_code == 200
        assert response.json()["action"] == "pass_applied"

        for _ in range(80):
            snapshot = client.get(
                f"/tables/{table_code}",
                params={"player_secret": player_secret},
            ).json()
            if snapshot["phase"] == "playing" and snapshot["turn"] == snapshot["viewer_seat"]:
                break
            response = client.post(
                f"/tables/{table_code}/advance",
                json={"player_secret": player_secret},
            )
            assert response.status_code == 200
            assert response.json()["advanced"] is True
        else:
            raise AssertionError("Did not reach waiting-on-human play state.")

        response = client.post(
            f"/tables/{table_code}/advance",
            json={"player_secret": player_secret},
        )
        payload = response.json()

        assert response.status_code == 200
        assert payload["advanced"] is False
        assert payload["action"] is None
        assert payload["can_advance"] is False
        assert payload["snapshot"]["phase"] == "playing"
        assert payload["snapshot"]["turn"] == payload["snapshot"]["viewer_seat"]


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


def test_advance_endpoint_returns_snapshot_and_can_advance() -> None:
    manager = TableManager()
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        created = client.post(
            "/tables",
            json={"display_name": "Host", "target_score": 20, "seed": 19},
        ).json()
        table_code = created["table_code"]
        player_secret = created["player_secret"]

        assert client.post(
            f"/tables/{table_code}/seats/0",
            json={"player_secret": player_secret},
        ).status_code == 200
        assert client.post(f"/tables/{table_code}/bots/1").status_code == 200
        assert client.post(f"/tables/{table_code}/bots/2").status_code == 200
        assert client.post(f"/tables/{table_code}/bots/3").status_code == 200

        response = client.post(
            f"/tables/{table_code}/advance",
            json={"player_secret": player_secret},
        )
        payload = response.json()

        assert response.status_code == 200
        assert payload["ok"] is True
        assert payload["advanced"] is True
        assert payload["action"] in {"bot_pass_submitted", "pass_applied", "bot_card_played"}
        assert isinstance(payload["can_advance"], bool)
        assert isinstance(payload["snapshot"], dict)
        assert "seat_hand_points" in payload["snapshot"]
        assert "last_trick" in payload["snapshot"]


def test_add_bot_endpoint_accepts_bot_name() -> None:
    manager = TableManager()
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        created = client.post(
            "/tables",
            json={"display_name": "Host", "target_score": 20, "seed": 19},
        ).json()
        table_code = created["table_code"]

        response = client.post(f"/tables/{table_code}/bots/1", json={"bot_name": "heuristic"})
        assert response.status_code == 200

        snapshot = client.get(f"/tables/{table_code}").json()
        seat_one = [seat for seat in snapshot["seats"] if seat["seat"] == 1][0]
        assert seat_one["kind"] == "bot"
        assert seat_one["bot_name"] == "heuristic"


def test_add_bot_endpoint_updates_existing_bot_type() -> None:
    manager = TableManager()
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        created = client.post(
            "/tables",
            json={"display_name": "Host", "target_score": 20, "seed": 19},
        ).json()
        table_code = created["table_code"]

        first = client.post(f"/tables/{table_code}/bots/1", json={"bot_name": "random"})
        assert first.status_code == 200
        second = client.post(f"/tables/{table_code}/bots/1", json={"bot_name": "heuristic"})
        assert second.status_code == 200

        snapshot = client.get(f"/tables/{table_code}").json()
        seat_one = [seat for seat in snapshot["seats"] if seat["seat"] == 1][0]
        assert seat_one["bot_name"] == "heuristic"


def test_add_bot_endpoint_rejects_non_string_bot_name() -> None:
    manager = TableManager()
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        created = client.post(
            "/tables",
            json={"display_name": "Host", "target_score": 20, "seed": 19},
        ).json()
        table_code = created["table_code"]

        response = client.post(f"/tables/{table_code}/bots/1", json={"bot_name": 123})
        assert response.status_code == 400
        assert "bot_name" in response.json()["detail"]


def test_add_bot_endpoint_rejects_configuration_after_start() -> None:
    manager = TableManager()
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        created = client.post(
            "/tables",
            json={"display_name": "Host", "target_score": 20, "seed": 19},
        ).json()
        table_code = created["table_code"]
        player_secret = created["player_secret"]

        assert client.post(
            f"/tables/{table_code}/seats/0",
            json={"player_secret": player_secret},
        ).status_code == 200
        assert client.post(f"/tables/{table_code}/bots/1", json={"bot_name": "random"}).status_code == 200
        assert client.post(f"/tables/{table_code}/bots/2", json={"bot_name": "random"}).status_code == 200
        assert client.post(f"/tables/{table_code}/bots/3", json={"bot_name": "random"}).status_code == 200

        response = client.post(f"/tables/{table_code}/bots/1", json={"bot_name": "heuristic"})
        assert response.status_code == 400
        assert "lobby" in response.json()["detail"].lower()


def test_server_integration_full_game_deterministic_with_websocket_heuristic_bots(tmp_path) -> None:
    manager = TableManager.with_persistence(records_dir=tmp_path)
    app = create_app(table_manager=manager)

    with TestClient(app) as client:
        table_code, player_secret = _setup_single_player_table(client, seed=223, bot_name="heuristic")
        scores_one = _drive_game_to_completion(
            client,
            table_code=table_code,
            player_secret=player_secret,
        )

        table_code_two, player_secret_two = _setup_single_player_table(client, seed=223, bot_name="heuristic")
        scores_two = _drive_game_to_completion(
            client,
            table_code=table_code_two,
            player_secret=player_secret_two,
        )

    assert scores_one == scores_two
