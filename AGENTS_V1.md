# Codex Tasks: Hearts AI (v1) - Live Real-Time Multiplayer + Web UI

This repo already has a correct v0 engine (rules + scoring + bots + CLI + tests). v1 adds a live real-time,
phone-friendly UI and a multiplayer server so humans can play with/against bots and friends, with full game
recording for replay and debugging.

Keep `AGENTS.md` as the v0 definition of done. This file is the v1 scope and constraints.

## Product Goals (v1)

- Live real-time Hearts tables (4 seats), playable from iPhone Safari and desktop browsers.
- Mix humans and bots in the same table.
- Spectate a table (read-only).
- Persist a complete game record (event log) for replay and analysis.
- Provide a small local-hosting experience: run server, open a URL, share a table code.

## Non-Goals (v1)

- App Store packaging, push notifications, payments, ranking/ladder, anti-cheat, or strong authentication.
- Internet-scale hosting concerns (k8s, sharding). v1 is single-process, single-host.
- Fancy visuals. Prefer clarity and debuggability.

## Ground Rules (v1)

- Target Python: 3.11+.
- Keep the **engine core dependency-free** (stdlib only) under `src/hearts_ai/engine/`.
- Server/UI may add minimal dependencies; keep them optional extras in `pyproject.toml`.
- Preserve `src/` layout. Runtime Python code stays in `src/hearts_ai/`.
- Tests must pass from repo root: `python -m pytest`.
- Determinism matters: store seeds / deck order in records; tests should not rely on timing.
- The server is authoritative: clients send intents; server validates and applies moves.
- RNG determinism must be explicit: each table/game gets a reproducible RNG seed chain, and bot decisions
  must be derived from that chain (not global random state).

## Definition Of Done (v1)

- `python -m hearts_ai serve` starts a local server and prints a URL.
- From a mobile browser, a human can:
  - Create or join a table with a short code.
  - Sit in a seat (or spectate).
  - Complete pass selection.
  - Play legal cards with clear turn indication.
  - Finish a full game to target score.
- Bot seats auto-play immediately on their turns.
- Turn timers and disconnect behavior are enforced and visible in the UI.
- Table lifecycle is explicit and enforced: `lobby -> passing -> playing -> hand_scoring -> game_over`.
- Every finished hand/game writes a replayable record (JSONL) and a compact summary.
- `python -m hearts_ai replay <record>` replays the record and verifies invariants.
- Add at least one integration test that exercises a table end-to-end deterministically (no real network).

## Recommended Architecture

### 1) Event-Sourced Game Records (shared foundation)

Represent all gameplay as an append-only stream of small events, sufficient to reconstruct:

- `GameCreated(config, seed, game_id)`
- `HandDealt(hand_index, deck_order or hands)`
- `PassCommitted(player_id, cards)`
- `CardPlayed(player_id, card)`
- `TrickTaken(trick_index, winner_id, trick_cards)`
- `HandScored(hand_index, delta_scores, shoot_moon?)`
- `GameEnded(final_scores, winner_id)`

Rules:

- The server produces events only after validation.
- Records are deterministic and replayable.
- Keep events JSON-serializable and stable (version the schema).
- Every event must include a standard envelope:
  - `event_id` (monotonic per game)
  - `ts` (UTC timestamp)
  - `schema_version`
  - `table_id`
  - `game_id`
  - `hand_index` (where applicable)
  - `actor` (`server`, `player:<id>`, or `bot:<id>`)

### 2) Authoritative Server (WebSocket)

Use a single FastAPI app with:

- REST endpoints for basic table management (create/join/status).
- WebSocket endpoint for live updates and user actions.
- In-memory table manager for active tables.
- On-disk record writer for each table/game.

Server responsibilities:

- Maintain canonical `GameState` per table.
- Validate every requested action (`pass`, `play`) against engine `legal_moves`.
- Broadcast state snapshots or incremental events to all connected clients.
- Run bot turns synchronously after human actions (and after deal/pass completion).
- Handle disconnect/reconnect with a simple secret token per player.
- Enforce table lifecycle transitions so invalid phase actions are rejected.
- Enforce turn timeout behavior with explicit config:
  - `play_timeout_seconds`
  - `pass_timeout_seconds`
  - Timeout action policy (`auto_play_lowest_legal` or `bot_takeover`)
- Enforce reconnect grace behavior with explicit config:
  - `disconnect_grace_seconds`
  - Action after grace (`bot_takeover` for seated human who has not returned)

### 3) Web UI (no-build-step v1)

Prefer a zero-build, static UI served by the Python server:

- `index.html`, `app.js`, `styles.css` in a package static directory.
- Vanilla JS (or very light modular JS) to connect via WebSocket and render state.
- Mobile-first layout: large tap targets for cards, clear "Your turn" indicator.
- Store `table_code` and `player_secret` in `localStorage` for refresh/reconnect.

Rationale: avoids Node/tooling initially; easier to run on Windows; still iPhone friendly.

## Implementation Plan (v1)

### 1) Protocol + Serialization

Create a small protocol package:

- `src/hearts_ai/protocol/messages.py`
  - Define `ClientMsg` / `ServerMsg` types and JSON (de)serialization.
  - Include `schema_version`.
  - Keep payloads small and explicit (avoid dumping entire Python objects).
  - Include explicit table phases and server-declared action availability (what this client can do now).

### 2) Record/Replay

Add:

- `src/hearts_ai/engine/record.py`
  - `GameRecorder` that appends JSONL events.
  - `replay(events) -> GameState` that re-applies via engine transitions and asserts invariants.
- CLI:
  - `python -m hearts_ai replay <path>`

### 3) Server

Add:

- `src/hearts_ai/server/app.py`
  - FastAPI app, routes, WebSocket handler.
- `src/hearts_ai/server/tables.py`
  - `TableManager`, `Table`, seat assignment, reconnection tokens.
- `src/hearts_ai/server/persistence.py`
  - Record paths, JSONL writer, and summary writer.
- `src/hearts_ai/server/state_views.py`
  - Convert internal state to a client-facing snapshot (hands are private per player).
- CLI:
  - `python -m hearts_ai serve --host 127.0.0.1 --port 8000`

Important:

- Never send other players' hands to a client.
- A spectating client gets public info only.
- `player_secret` is bearer-style seat control for v1 local-hosting; each action must be authorized against
  seat ownership server-side.

### 4) UI

Add:

- `src/hearts_ai/server/static/index.html`
- `src/hearts_ai/server/static/app.js`
- `src/hearts_ai/server/static/styles.css`

UI minimum screens:

- Home: create table, join by code.
- Table: seat selection, show players and connection status.
- Pass: pick 3 cards, submit.
- Play: show hand, current trick, taken points, scores, whose turn.

### 5) Tracking + Bench (optional but high-leverage)

- `python -m hearts_ai bench --seeds 1..200 --bots random,random --out results.jsonl`
- Persist per-game summary rows to JSONL for easy plotting later.

### 6) Tests

Add:

- Record/replay roundtrip tests.
- Protocol serialization tests.
- Server integration smoke test using the ASGI test client to open a WebSocket, join a table,
  seat a human, fill remaining seats with bots, and run a deterministic game to completion.
- Timeout and reconnect policy tests (at least one path each).

Tests should skip with a clear message if server optional deps are not installed.

## Dependencies (v1)

Add optional extras in `pyproject.toml`:

- `server`: `fastapi`, `uvicorn[standard]`
- `server-test`: `httpx`, `pytest-asyncio`

Do not add server deps to core `project.dependencies`.

## Commands (v1)

- Install dev + server: `python -m pip install -e ".[dev,server]"`
- Install dev + server + server-test: `python -m pip install -e ".[dev,server,server-test]"`
- Run tests: `python -m pytest`
- Run server: `python -m hearts_ai serve`
- Replay record: `python -m hearts_ai replay path\\to\\game.jsonl`
