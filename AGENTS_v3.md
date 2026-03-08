# Hearts AI Bot Improvement Plan (Heuristic-First)

## Recommendation

Start with simple heuristics before moving to complex search methods.

Reasoning:
- A strong heuristic baseline is easier to validate and debug.
- Hidden-information search (e.g., determinized MCTS) is harder to tune without a baseline evaluator.
- You can measure concrete gains early and avoid over-engineering.

## Goals

- Improve on `RandomBot` with deterministic, legal, and testable behavior.
- Keep the implementation stdlib-only and aligned with current engine APIs.
- Build a benchmark path so each bot iteration is measurable.

## Phase 1: Benchmark and Bot Selection Plumbing

Scope:
- Add CLI bot selection so seats can run `random` or `heuristic`.
- Add a repeatable benchmark mode (fixed seed range, many games).
- Report summary metrics:
  - win rate
  - average final points
  - average finishing rank

Implementation targets:
- `src/hearts_ai/cli.py`:
  - add bot-config flags
  - instantiate bots by policy name
- optional helper:
  - `src/hearts_ai/bots/factory.py`

Acceptance criteria:
- Deterministic output for fixed seeds.
- Existing tests remain green.

## Phase 2: HeuristicBot v1 (Rule-Based Baseline)

Create:
- `src/hearts_ai/bots/heuristic_bot.py`

Pass heuristics:
- Prefer passing `Q♠`.
- Then high spades (`A♠`, `K♠`).
- Then high hearts.
- Then highest remaining risky cards.

Play heuristics:
- Lead:
  - prefer low non-hearts
  - avoid leading hearts unless forced
- Following suit:
  - if trick currently contains points, prefer losing safely
  - if no points, shed dangerous high cards when reasonable
- Off-suit:
  - dump `Q♠` first when safe
  - then shed high hearts / high-risk losers

Determinism:
- Stable tie-breaks via sorted card ordering.

Acceptance criteria:
- Bot never returns illegal moves.
- Bot is deterministic given state + seed.
- Bot outperforms random in benchmark aggregate (target threshold defined in Phase 1 harness).

## Phase 2.5: Server/UI Bot Selection Plumbing

Scope:
- Ensure UI table bots can use the same bot policies as CLI (`random`, `heuristic`).
- Keep this phase plumbing-only (no new heuristic logic).
- Preserve fast flow for Quick Solo while allowing seat-level control in lobby.

Implementation targets:
- `src/hearts_ai/server/tables.py`:
  - store bot type per bot seat
  - instantiate bot via bot factory during pass/play auto-advance
  - enforce lobby-only bot configuration
- `src/hearts_ai/server/app.py` and UI API contracts:
  - allow bot type to be set when adding a bot seat (default `random`)
  - allow updating an existing bot seat type during lobby
- reuse:
  - `src/hearts_ai/bots/factory.py`
- `src/hearts_ai/server/static/` UI behavior:
  - top-level Bot Type acts as default
  - Quick Solo applies top-level Bot Type to all bot seats at creation
  - Create Table supports seat-level bot type selection in lobby
  - existing bot seats can be changed in lobby
  - seat bot controls are hidden after lobby

Acceptance criteria:
- UI bot seats are configurable by bot name during lobby.
- Quick Solo uses top-level Bot Type for all bot seats.
- Create Table supports mixed bot-seat setups in lobby.
- Bot configuration cannot be changed after game start.
- Deterministic behavior remains reproducible with fixed seed.
- Existing server integration tests remain green with new bot-selection coverage.

## Phase 2.6: UI Gameplay Polish

Scope:
- Improve hand-flow readability without changing game rules or engine behavior.
- Keep this phase UI/interaction-only.
- Prioritize stable, clear feedback over flashy effects.

Implementation targets:
- Pass flow timing:
  - minimize wait after pass submission
  - add explicit `Begin Hand` gate after pass resolution so viewer can review received cards before play starts
- Pass-result visibility:
  - highlight newly received cards in viewer hand at hand start
  - surface "new from pass" context in hand/status messaging
- Seat score hierarchy:
  - display Hand points as a large value alongside seat name line
  - keep Total points as the smaller persistent pill
- Table readability polish:
  - tighten seat/table spacing so seat info sits closer to trick action
  - disable old trick card entry flash animation (future card-flight animation can replace it)

Acceptance criteria:
- Pass phase advances quickly once submissions are complete.
- Viewer must explicitly click `Begin Hand` before normal play highlighting/auto-advance resumes at hand start.
- Newly received pass cards are clearly distinguishable at hand start.
- Hand points are more prominent than Total points in each seat panel.
- Trick card placement updates without the previous flash/jump effect.
- No gameplay/engine rule changes.
- Existing tests remain green with targeted UI/server coverage updates as needed.

## Phase 3: HeuristicBot v2 (Risk-Aware Upgrade)

Enhancements:
- Add simple trick-risk scoring:
  - estimate whether later players can overtake if current card is played
- Add moon-defense mode:
  - when one opponent accumulates points quickly, prioritize blocking moon
- Add optional shallow rollout evaluator:
  - 1-ply move scoring with small sampled continuations

Constraints:
- Keep runtime practical for CLI simulations.
- Keep behavior deterministic with explicit RNG usage.

Acceptance criteria:
- v2 outperforms v1 on benchmark suite.
- No regressions in legality and determinism tests.

## Test Plan

Update/add tests:
- `tests/test_bots.py`:
  - pass-priority scenarios (`Q♠`, high spades, high hearts)
  - play-choice scenarios for lead/follow/off-suit
- integration/smoke:
  - deterministic full-game runs with heuristic bots
  - legal-move invariants remain enforced
- server/UI path:
  - bot seat type selection and persistence in table state
  - deterministic auto-advance behavior when seats use `heuristic`

Do not make benchmark win-rate assertions brittle in CI:
- Keep strict assertions for determinism/legality.
- Keep performance summaries as diagnostics/local benchmark outputs.

## Move-to-Complex Trigger

Start complex methods (determinized search) only after:
- Heuristic v2 is stable and well-tested.
- Benchmark harness is automated and trusted.
- Heuristic bot has a clear margin over random across enough games/seeds.

## Suggested Implementation Order

1. Phase 1 benchmark + bot-selection plumbing
2. Phase 2 HeuristicBot v1
3. Phase 2 test coverage
4. Phase 2.5 server/UI bot-selection plumbing
5. Phase 2.6 UI gameplay polish
6. Phase 3 HeuristicBot v2
7. Compare v1/v2 and decide on search transition
