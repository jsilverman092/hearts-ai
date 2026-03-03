# Codex Tasks: Hearts AI (v2) - Playability UX + Human-Paced Table Flow

This repo already has a correct v0 engine and a working v1 multiplayer web table. v2 focuses on making gameplay
feel readable, paced, and pleasant, especially for single-player (human vs bots), while keeping multiplayer support.

Keep `AGENTS.md` as v0 scope and `AGENTS_V1.md` as the multiplayer baseline. This file defines v2 priorities.
When this file conflicts with v1 behavior, this v2 file takes precedence.

## Product Goals (v2)

- Single-player vs bots is the primary experience.
- Multiplayer and spectating remain supported (no regressions).
- Gameplay is human-paced by default, with configurable speed controls.
- Card play is visually clear: each play is visible, tricks are readable, winners are understandable.
- Score context is visible at seat level:
  - Running game score.
  - Points taken so far in the current hand (updated after each trick).

## Non-Goals (v2)

- New authentication model, ranking/ladder, matchmaking, or hosted infrastructure work.
- Overhauling core Hearts rules/scoring semantics.
- Replacing the stack with a JS build system.
- Pixel-perfect animation system or heavy graphics library.

## Ground Rules (v2)

- Preserve engine correctness and deterministic behavior.
- Server remains authoritative for legal moves and state transitions.
- Keep no-build static UI (`index.html`, `app.js`, `styles.css`) unless explicitly required otherwise.
- Keep single-process local-hosting model.
- Keep changes incremental and testable.
- Avoid timing-fragile tests; use deterministic progression controls.
- In multiplayer tables, pacing control authority is host/seat-0 by default.

## Definition Of Done (v2)

- A single-player table (1 human + 3 bots) is playable end-to-end with default human pacing.
- A quick-start solo action exists that claims one human seat and fills remaining seats with bots.
- UI includes pace controls:
  - Pause/Play autoplay.
  - Step action (advance one server action).
  - Speed slider (slow to fast).
  - Optional "Fast-forward to my turn".
- Bot cards appear one-by-one (not instant full-trick jumps).
- Current trick remains visible until all 4 cards are present, then clears with a visible transition.
- Cards are rendered as visual card faces (not plain alphanumeric chips).
- Table layout is seat-oriented around a center play area.
- Seat UI shows both:
  - Total game score.
  - Points taken so far in the current hand, updated after each completed trick.
- Multiplayer tables still function with humans and bots in mixed seats.
- Existing replay/record behavior remains valid.
- `python -m pytest` passes.

## Core Product Decisions (locked for v2)

- Primary mode: single-player vs bots.
- Hand score visibility: show points taken so far in current hand (live update each trick).
- Default pacing: human pace, configurable by UI controls.
- Multiplayer pacing authority: host/seat-0 controls pace settings and stepping.

## Recommended Architecture Changes

### 1) Progression Model For Pacing

Current v1 table logic auto-advances bots to the next human action in a tight loop. That blocks per-card pacing.
Introduce explicit step-based progression in server table flow.

- Add a deterministic "advance one action" path on `Table`/`TableManager`.
- Treat one action as one of:
  - bot pass submission
  - pass application
  - single card play
  - hand scoring transition
  - next-hand deal transition
  - game-over transition
- Keep legal validation and state mutation server-side.
- Allow client-controlled pace by calling advance on a timer.
- API contract:
  - `POST /tables/{table_code}/advance` performs exactly one deterministic action.
  - Request includes `player_secret` for authorization.
  - Response includes updated snapshot and whether another immediate advance is available.

### 2) Table Snapshot Enrichment

Expose minimal extra fields needed by UI playability:

- `seat_hand_points`: per seat points captured so far in current hand.
- `last_trick` summary:
  - trick cards
  - winner
  - trick points
  - `trick_seq` integer for animation resets
- Existing fields remain stable for backward compatibility where possible.
- Field contracts:
  - `seat_hand_points` is `dict[str, int]`, keys `"0"`..`"3"`, resets to zeros on each new hand.
  - `last_trick` is `null` when no completed trick in current hand; otherwise includes winner, cards, points, and `trick_seq`.

### 3) UI Rendering Model

- Render a table-centered layout with four fixed seat anchors (N/E/S/W).
- Render each played card in positional trick slots by seat.
- Keep trick cards visible after 4th card, then run clear animation.
- Track transient UI animation state independently from authoritative snapshot state.
- Render card faces via HTML/CSS components (rank + suit), including backs for hidden cards.
- On reconnect or any snapshot jump, authoritative snapshot wins and stale client animations are canceled.

### 4) Pace Controls

- Add controls in UI:
  - autoplay toggle
  - step button
  - speed slider
  - fast-forward to human turn toggle
- Default autoplay enabled at conservative human pace.
- Spectator mode may use faster defaults but must remain configurable.
- Default timing values:
  - default card cadence: `900ms`
  - slider range: `200ms` to `2000ms`
  - completed-trick hold before clear: `1500ms`

## Implementation Plan (v2)

### 1) Server Step API

- Add table manager methods that perform one deterministic progression step.
- Add REST endpoint(s) for client-driven stepping in active tables.
- Ensure authorization rules are respected (table-scoped, secret-aware where needed).

### 2) State View Extensions

- Add per-hand points by seat to state snapshot.
- Add last-trick metadata for winner/points/animation.
- Keep hidden-information guarantees (no leaking private hands).

### 3) UI Layout Refactor

- Replace chip-centric trick/hand presentation with card components.
- Introduce seat-around-table play surface.
- Add per-seat score panel showing total and current-hand points.

### 4) UI Pace + Animation

- Implement client scheduler for autoplay/step/speed.
- Animate card arrival and trick clear in deterministic sequence.
- Handle reconnect/resync cleanly without animation glitches.

### 5) Single-Player First UX Polish

- Add a clear flow for "quick start solo table" (human seat + fill bots).
- Keep existing create/join/table code flow for multiplayer.

### 6) Tests

- Table progression step tests (deterministic step behavior).
- Snapshot tests for new fields (`seat_hand_points`, last trick metadata).
- Server integration test validating paced progression in single-player setup.
- Existing multiplayer tests continue to pass.
- Frontend animation tests are smoke-level only; do not assert fragile frame/timing details.

## Compatibility + Migration Notes

- Preserve current endpoints used by v1 clients when practical.
- Add new fields/endpoints incrementally.
- If breaking API shape is unavoidable, bump protocol schema version and update tests accordingly.

## Commands (v2)

- Install dev + server: `python -m pip install -e ".[dev,server]"`
- Install test extras: `python -m pip install -e ".[dev,server,server-test]"`
- Run tests: `python -m pytest`
- Run server: `python -m hearts_ai serve`
