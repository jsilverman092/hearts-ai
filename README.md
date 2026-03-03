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

Record and replay:

```bash
python -m hearts_ai play --seed 1 --games 1 --record records\\sample.jsonl
python -m hearts_ai replay records\\sample.jsonl
```

Run live server UI:

```bash
python -m hearts_ai serve --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000` on desktop.
- `http://<laptop-lan-ip>:8000` on phone (same network) when using `--host 0.0.0.0`.

Server games are recorded while they run:

- Per-game event log JSONL files in `records/`
- Game summaries in `records/summaries.jsonl`
