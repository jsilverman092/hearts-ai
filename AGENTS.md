# Codex Tasks: Hearts AI (v0)

This repo is a Python `src/`-layout project for a Hearts game engine that will later support strong search-based/RL bots and a UI. Implement an initial, correct, testable core first.

## Ground Rules

- Target Python: 3.11+ (Windows-first, but keep code portable).
- Keep dependencies minimal for v0 (stdlib only). No ML deps in core.
- Preserve `src/` layout: all runtime code goes under `src/hearts_ai/`.
- Tests use `pytest` and must pass from repo root: `python -m pytest`.
- Prefer deterministic behavior in tests: inject `random.Random` or seed explicitly.
- Do not build UI yet beyond a minimal CLI; avoid network/server frameworks in v0.
- Avoid premature optimization; prioritize correctness and clear state transitions.
- Prefer a mutable `GameState` for v0; all state changes should go through explicit functions in `engine/game.py`.

## Definition Of Done (v0)

- A playable 4-player Hearts engine (pass + play + score) with enforced legal moves.
- A bot interface + at least one baseline bot (random-legal).
- A CLI to run a full game simulation and print results.
- Unit tests covering rules/scoring and a smoke test that runs a full game deterministically.
- Game ends when a player reaches >= 50 points (configurable); lowest score wins.

## Implementation Plan

### 1) Engine Data Model

Create core types and helpers:

- `src/hearts_ai/engine/cards.py`
  - `Suit`, `Rank`, `Card` (hashable, comparable), `make_deck()`.
- `src/hearts_ai/engine/types.py`
  - Player ids (0..3), `Trick`, `Hand`, `Deal`, lightweight aliases.
- `src/hearts_ai/engine/errors.py`
  - `IllegalMoveError`, `InvalidStateError`.

### 2) Rules And Legal Moves

- `src/hearts_ai/engine/rules.py`
  - Enforce standard Hearts constraints:
    - Must follow suit if possible.
    - Cannot lead hearts until broken (unless only hearts remain).
    - First trick: no point cards may be played unless forced.
    - First trick lead is 2 of Clubs (standard).
  - Provide `legal_moves(state, player_id) -> list[Card]`.

Keep rules configurable where it is easy (feature flags), but do not over-generalize.

### 3) Game State And Transitions

- `src/hearts_ai/engine/state.py`
  - `GameConfig` (pass direction cycle, rules toggles, target_score=50).
  - `GameState` (hands, trick-in-progress, taken tricks, scores, hearts_broken, turn).
- `src/hearts_ai/engine/game.py`
  - `new_game(rng)`, `deal(state, rng)`, `apply_pass(state, pass_map)`.
  - `play_card(state, player_id, card)` (mutates with clear invariants).
  - `is_hand_over(state)`, `is_game_over(state)`.

Prefer a small set of explicit transitions rather than lots of ad-hoc mutation.

### 4) Scoring

- `src/hearts_ai/engine/scoring.py`
  - Standard scoring: each heart = 1, Queen of Spades = 13.
  - "Shoot the moon": if a player takes all points, they score 0 and others +26 (standard).

### 5) Bots

- `src/hearts_ai/bots/base.py`
  - `Bot` protocol/interface: `choose_pass(hand, state, rng)` and `choose_play(state, rng)`.
- `src/hearts_ai/bots/random_bot.py`
  - Select uniformly from legal moves (and a simple pass policy).

Bots must never return illegal actions; validate in engine and raise on illegal actions.

### 6) CLI (Minimal)

- `src/hearts_ai/cli.py` and `src/hearts_ai/__main__.py`
  - `python -m hearts_ai play --seed 1 --games 1 --target-score 50`
  - Print per-hand and final scores; keep output stable for tests.

Use `argparse` (stdlib). Do not add `typer`/`click` yet.

### 7) Tests

Add tests under `tests/`:

- Deck integrity: 52 unique cards.
- Trick winner logic (highest of led suit).
- Legal move enforcement (follow suit, hearts broken).
- First trick restrictions + 2 of Clubs lead.
- Scoring (including shoot-the-moon).
- End-to-end deterministic game simulation with a fixed seed and random bots.

## Suggested File Layout (v0)

- `src/hearts_ai/engine/`: rules, state, game loop, scoring
- `src/hearts_ai/bots/`: bot APIs and baselines
- `src/hearts_ai/ui/`: keep empty for now
- `tests/`: unit tests

## Commands

- Install dev deps: `python -m pip install -e ".[dev]"`
- Run tests: `python -m pytest`
- Run CLI: `python -m hearts_ai play --seed 1 --games 1 --target-score 50`
