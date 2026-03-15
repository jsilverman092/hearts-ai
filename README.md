# hearts-ai
Hearts game engine, bots, record/replay tooling, and a live local multiplayer web UI.

## Quickstart

Install with development and server extras:

```bash
python -m pip install -e ".[dev,server]"
```

Run tests:

```bash
python -m pytest
```

Run simulation CLI:

```bash
python -m hearts_ai play --seed 1 --games 1 --target-score 50
```

Run deterministic benchmarks:

```bash
python -m hearts_ai benchmark --seed 1 --games 20 --target-score 30 --bots heuristic_v3
python -m hearts_ai benchmark-search --seed 1 --games 10 --target-score 30 --preset mixed_search_field --world-counts 1,2,4,8
```

Default `benchmark-search` presets:

- `mixed_search_field`: `search_v1,heuristic_v3,heuristic_v2,random`
- `all_search_v1`: `search_v1,search_v1,search_v1,search_v1`

Record and replay:

```bash
python -m hearts_ai play --seed 1 --games 1 --record records\\sample.jsonl
python -m hearts_ai replay records\\sample.jsonl
```

Run live server UI:

```bash
python -m hearts_ai serve --host 127.0.0.1 --port 8000
```

Run live server UI with auto-reload during local iteration:

```bash
.\.venv\Scripts\python.exe -m uvicorn hearts_ai.server.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Then open:

- `http://127.0.0.1:8000` on desktop.
- `http://<laptop-lan-ip>:8000` on phone (same network) when using `--host 0.0.0.0`.

Server games are recorded while they run:

- Per-game event log JSONL files in `records/`
- Game summaries in `records/summaries.jsonl`
