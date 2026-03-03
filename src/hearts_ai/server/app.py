from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hearts_ai.protocol.messages import SCHEMA_VERSION, dumps_message, loads_message
from hearts_ai.server.state_views import table_snapshot
from hearts_ai.server.tables import (
    InvalidTableActionError,
    TableError,
    TableManager,
    TableNotFoundError,
    UnauthorizedError,
)

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
except ImportError as exc:  # pragma: no cover - exercised only when optional deps missing.
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    WebSocket = Any  # type: ignore[assignment,misc]
    WebSocketDisconnect = Exception  # type: ignore[assignment]
    _FASTAPI_IMPORT_ERROR = exc
else:
    _FASTAPI_IMPORT_ERROR = None


@dataclass(slots=True)
class WebSocketHub:
    table_connections: dict[str, dict[Any, str | None]] = field(default_factory=dict)

    async def subscribe(self, *, table_code: str, websocket: Any, viewer_secret: str | None) -> None:
        table_key = table_code.upper()
        connections = self.table_connections.setdefault(table_key, {})
        connections[websocket] = viewer_secret

    async def unsubscribe(self, *, table_code: str, websocket: Any) -> None:
        table_key = table_code.upper()
        connections = self.table_connections.get(table_key)
        if connections is None:
            return
        connections.pop(websocket, None)
        if not connections:
            self.table_connections.pop(table_key, None)

    async def broadcast_snapshot(self, *, table_code: str, manager: TableManager) -> None:
        table_key = table_code.upper()
        table = manager.get_table(table_key)
        connections = self.table_connections.get(table_key, {})
        stale: list[Any] = []

        for websocket, viewer_secret in list(connections.items()):
            payload = table_snapshot(table, viewer_secret=viewer_secret)
            message = {
                "schema_version": SCHEMA_VERSION,
                "type": "state_snapshot",
                "table_code": table.table_code,
                "phase": table.phase,
                "payload": payload,
            }
            try:
                await websocket.send_text(dumps_message(message))
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            connections.pop(websocket, None)


def create_app(*, table_manager: TableManager | None = None) -> Any:
    if FastAPI is None:
        raise RuntimeError(
            "Server dependencies are not installed. Install with: "
            'python -m pip install -e ".[server]"'
        ) from _FASTAPI_IMPORT_ERROR

    manager = table_manager or TableManager()
    hub = WebSocketHub()
    app = FastAPI(title="hearts-ai server", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/tables")
    def create_table(payload: dict[str, Any]) -> dict[str, Any]:
        display_name = str(payload.get("display_name", "")).strip()
        target_score = int(payload.get("target_score", 50))
        seed_raw = payload.get("seed")
        seed = int(seed_raw) if seed_raw is not None else None
        table, player_secret = manager.create_table(
            display_name=display_name,
            target_score=target_score,
            seed=seed,
        )
        return {
            "table_code": table.table_code,
            "player_secret": player_secret,
            "phase": table.phase,
        }

    @app.post("/tables/{table_code}/join")
    def join_table(table_code: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            player_secret = manager.join_table(table_code, display_name=str(payload.get("display_name", "")))
            table = manager.get_table(table_code)
        except TableNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"table_code": table.table_code, "player_secret": player_secret}

    @app.get("/tables/{table_code}")
    def get_table(table_code: str, player_secret: str | None = None) -> dict[str, Any]:
        try:
            table = manager.get_table(table_code)
        except TableNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return table_snapshot(table, viewer_secret=player_secret)

    @app.post("/tables/{table_code}/seats/{seat}")
    def claim_seat(table_code: str, seat: int, payload: dict[str, Any]) -> dict[str, bool]:
        try:
            manager.claim_seat(table_code, player_secret=str(payload.get("player_secret", "")), seat=seat)
        except TableNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except UnauthorizedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except TableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/tables/{table_code}/bots/{seat}")
    def add_bot(table_code: str, seat: int) -> dict[str, bool]:
        try:
            manager.add_bot(table_code, seat=seat)
        except TableNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/tables/{table_code}/pass")
    def submit_pass(table_code: str, payload: dict[str, Any]) -> dict[str, bool]:
        cards_raw = payload.get("cards")
        if not isinstance(cards_raw, list) or any(not isinstance(card, str) for card in cards_raw):
            raise HTTPException(status_code=400, detail="Field 'cards' must be a list of card strings.")
        try:
            manager.submit_pass(
                table_code,
                player_secret=str(payload.get("player_secret", "")),
                cards=list(cards_raw),
            )
        except TableNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except UnauthorizedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except TableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/tables/{table_code}/play")
    def submit_play(table_code: str, payload: dict[str, Any]) -> dict[str, bool]:
        try:
            manager.play_card(
                table_code,
                player_secret=str(payload.get("player_secret", "")),
                card=str(payload.get("card", "")),
            )
        except TableNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except UnauthorizedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except TableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: Any) -> None:
        await websocket.accept()
        table_code: str | None = None
        viewer_secret: str | None = None

        try:
            while True:
                raw_message = await websocket.receive_text()
                try:
                    message = loads_message(raw_message)
                except Exception as exc:
                    await websocket.send_text(
                        dumps_message(
                            {
                                "schema_version": SCHEMA_VERSION,
                                "type": "error",
                                "code": "invalid_message",
                                "message": str(exc),
                            }
                        )
                    )
                    continue

                msg_type = str(message.get("type"))
                try:
                    if msg_type == "ping":
                        await websocket.send_text(
                            dumps_message(
                                {
                                    "schema_version": SCHEMA_VERSION,
                                    "type": "pong",
                                    "nonce": str(message.get("nonce", "")),
                                }
                            )
                        )
                        continue

                    if msg_type == "join_table":
                        table_code = str(message.get("table_code", "")).upper()
                        display_name = str(message.get("display_name", "Player"))
                        viewer_secret = manager.join_table(table_code, display_name=display_name)
                        await hub.subscribe(
                            table_code=table_code,
                            websocket=websocket,
                            viewer_secret=viewer_secret,
                        )
                        table = manager.get_table(table_code)
                        await websocket.send_text(
                            dumps_message(
                                {
                                    "schema_version": SCHEMA_VERSION,
                                    "type": "table_joined",
                                    "table_code": table.table_code,
                                    "player_secret": viewer_secret,
                                    "seat": None,
                                }
                            )
                        )
                        await websocket.send_text(
                            dumps_message(
                                {
                                    "schema_version": SCHEMA_VERSION,
                                    "type": "state_snapshot",
                                    "table_code": table.table_code,
                                    "phase": table.phase,
                                    "payload": table_snapshot(table, viewer_secret=viewer_secret),
                                }
                            )
                        )
                        continue

                    if msg_type == "sit_seat":
                        if table_code is None:
                            raise InvalidTableActionError("Must join a table before claiming a seat.")
                        manager.claim_seat(
                            table_code,
                            player_secret=str(message.get("player_secret", "")),
                            seat=int(message.get("seat", -1)),
                        )
                        await hub.broadcast_snapshot(table_code=table_code, manager=manager)
                        continue

                    if msg_type == "submit_pass":
                        if table_code is None:
                            raise InvalidTableActionError("Must join a table before submitting passes.")
                        cards = message.get("cards", [])
                        if not isinstance(cards, list) or any(not isinstance(card, str) for card in cards):
                            raise InvalidTableActionError("Field 'cards' must be a list of card strings.")
                        manager.submit_pass(
                            table_code,
                            player_secret=str(message.get("player_secret", "")),
                            cards=list(cards),
                        )
                        await hub.broadcast_snapshot(table_code=table_code, manager=manager)
                        continue

                    if msg_type == "play_card":
                        if table_code is None:
                            raise InvalidTableActionError("Must join a table before playing a card.")
                        manager.play_card(
                            table_code,
                            player_secret=str(message.get("player_secret", "")),
                            card=str(message.get("card", "")),
                        )
                        await hub.broadcast_snapshot(table_code=table_code, manager=manager)
                        continue

                    raise InvalidTableActionError(f"Unsupported websocket message type: {msg_type!r}.")
                except TableError as exc:
                    await websocket.send_text(
                        dumps_message(
                            {
                                "schema_version": SCHEMA_VERSION,
                                "type": "error",
                                "code": "table_error",
                                "message": str(exc),
                            }
                        )
                    )
        except WebSocketDisconnect:
            pass
        finally:
            if table_code is not None:
                await hub.unsubscribe(table_code=table_code, websocket=websocket)

    return app


def run_server(*, host: str = "127.0.0.1", port: int = 8000) -> None:
    if _FASTAPI_IMPORT_ERROR is not None:
        raise RuntimeError(
            "Server dependencies are not installed. Install with: "
            'python -m pip install -e ".[server]"'
        ) from _FASTAPI_IMPORT_ERROR

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised only when optional deps missing.
        raise RuntimeError(
            "Uvicorn is not installed. Install server extras with: "
            'python -m pip install -e ".[server]"'
        ) from exc

    app = create_app()
    print(f"Serving hearts-ai at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


__all__ = ["create_app", "run_server"]

