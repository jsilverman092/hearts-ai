# Hearts AI Plan (AGENTS_V4: Search Support And search_v1)

## Purpose

This document proposes the next implementation phase after the frozen `heuristic_v3` baseline:

- a clean search-support layer
- a first deterministic search-based bot
- testing and benchmark work to validate it
- explanation/debug extensions so search remains inspectable

It is based on the current repo state as of 2026-03-14 and is intended to be the implementation plan before coding begins.

## Current Repo Constraints That Matter

These are the main realities from the current codebase that should shape the next phase:

1. `heuristic_v3` is the main handcrafted baseline and should stay frozen except for obvious tactical bugs.

2. Current public inference exists, but it is heuristic-owned.
   - `src/hearts_ai/bots/heuristic/public_info.py` already tracks:
     - `QS` live/dead
     - seen-card counts by suit
     - remaining unseen ranks
     - void inference from failure to follow suit
   - This is useful, but it is not yet a neutral search-support layer.

3. Current rollout logic is not a real hidden-information search layer.
   - `heuristic_v2` / `heuristic_v3` rollout only samples the rest of the current trick.
   - It does not sample full hidden hands or evaluate whole-hand futures across determinized worlds.

4. The engine still exposes full-information `GameState` to bots.
   - `state.hands` contains every player's full hand.
   - `heuristic_v3` behaves honorably by mostly using only its own hand plus public history.
   - A search bot cannot rely on that convention. It needs an explicit hidden-information-safe view.

5. Server bot instances are not persistent today.
   - CLI game simulation creates bots once per game, so per-bot memory can survive within that game.
   - The server path recreates a bot instance on each bot action in `src/hearts_ai/server/tables.py`.
   - That means any private-memory feature such as "remember what I passed" will not survive across actions unless the runtime model changes.

6. Debug/recommendation plumbing already exists and should be preserved.
   - `debug_last_bot_decision`
   - `debug_viewer_recommendation`
   - viewer advisory bot selection
   - current UI rendering of candidate lists, scores, and tags

7. Benchmarking exists, but mixed-field rotation is still mostly procedural rather than codified.
   - The CLI `benchmark` command is useful.
   - The mixed-field and seat-rotated workflow from the benchmark report should be preserved and made easier to repeat for search work.

## Goals

The next phase should achieve the following:

1. Build a neutral search-support layer that does not depend on `heuristic_v3` internals.
2. Introduce a first search bot that is deterministic under fixed seeds.
3. Keep `heuristic_v3` as the rollout/baseline comparison anchor, not as something to replace immediately.
4. Preserve or improve the current explanation/debug workflow.
5. Add scenario-style regression testing alongside aggregate benchmarks.
6. Avoid deep or complex search at first.

## Explicit Non-Goals

This phase should not try to do the following:

1. Start RL work.
2. Build deep MCTS / ISMCTS immediately.
3. Broadly retune or refactor `heuristic_v3` strategy.
4. Add speculative opponent modeling beyond hard card-counting / pass-memory / constraint-based inference.
5. Hide search logic inside the `heuristic` package.

## Recommended Architecture

### 1. Add A Neutral `search/` Package

Create a new top-level package under `src/hearts_ai/search/`.

Reason:
- the search-support layer is broader than one bot class
- it should support sampled-world generation, explanation, and later comparison tooling
- it should not be forced into `bots/heuristic/`

Recommended layout:

- `src/hearts_ai/search/models.py`
  - search-facing dataclasses and reason payload types
- `src/hearts_ai/search/view.py`
  - hidden-information-safe player view built from full `GameState`
- `src/hearts_ai/search/knowledge.py`
  - public knowledge snapshot plus seat-specific private knowledge
- `src/hearts_ai/search/memory.py`
  - private bot memory structures, starting with own-pass memory
- `src/hearts_ai/search/sampler.py`
  - determinized hidden-hand sampling consistent with hard constraints
- `src/hearts_ai/search/simulate.py`
  - cloned-state simulation utilities and whole-hand rollout support
- `src/hearts_ai/search/evaluate.py`
  - move evaluation across sampled worlds
- `src/hearts_ai/search/explain.py`
  - search reason payload assembly and comparison summaries

Then add a thin runtime bot adapter:

- `src/hearts_ai/bots/search_bot.py`
  - exposes `SearchBotV1`
  - keeps `bots/factory.py` and UI/CLI bot selection simple

### 2. Add A Hidden-Information-Safe Player View

This is the most important architectural correction before search work.

Recommended object:
- `SearchPlayerView`

It should expose:
- acting `player_id`
- own hand
- legal moves
- current trick
- taken tricks
- scores
- turn
- hand number / trick number / hearts broken / pass direction
- public knowledge snapshot
- seat-private memory snapshot

It should not expose:
- opponent hidden hands
- true unseen-card assignment from live `GameState`

Reason:
- the current full-information `GameState` is acceptable for the engine
- it is not acceptable as the direct search input
- this boundary also makes anti-cheating tests possible

### 3. Add A Persistent Bot Runtime / Memory Layer

Because the server currently recreates bot instances per action, private-memory features will otherwise be broken.

Recommended change:
- introduce a small runtime/session layer for bots outside the engine

Possible shape:
- `src/hearts_ai/bots/runtime.py`

Responsibilities:
- keep persistent bot instances per seat for CLI and server flows
- reset bot-hand memory when a new hand starts
- allow bots to store seat-private memory such as:
  - cards this seat passed away
  - exact recipient of those cards
  - optional received-pass metadata later

Important recommendation:
- do not put seat-private memory inside `GameState`
- keep engine state public/game-true
- keep seat-private knowledge in bot/runtime/search memory

## Search-Support Layer Plan

### 1. Public Knowledge Snapshot

Build a neutral public knowledge object from `GameState`.

This should generalize the useful parts of current `heuristic/public_info.py`:
- seen cards
- unplayed cards
- `QS` live/dead
- void suits by player
- suit exhaustion counts
- remaining rank sets by suit
- cards remaining per opponent

Recommended naming:
- `PublicKnowledge`

This layer should also support search-facing helpers such as:
- which suits are fully exhausted outside our hand
- which players are known void in the led suit
- remaining card-count constraints by opponent
- floor / trap / boss classification if it proves useful for explanation tags

Important constraint:
- extract only neutral helpers here
- do not refactor `heuristic_v3` aggressively around the new package in the same change set
- it is acceptable for search to borrow logic first and deduplicate later if needed

### 2. Private Knowledge / Memory

Start private memory narrowly.

Recommended first private-memory feature:
- remember exactly which cards the bot itself passed, and to which recipient seat

Why:
- it is strategically important
- it is hard information, not speculation
- it is explicitly called out in the roadmap and literature notes

Recommended naming:
- `SeatPrivateMemory`

First version should support:
- `passed_cards_by_recipient`
- helper queries such as:
  - "did I pass `QS` right?"
  - "is a still-unseen known-passed danger seated before or after me?"

Do not add yet:
- speculative shape modeling
- inferred psychology
- broad soft-probability opponent profiles

### 3. Determinization / Sampled-World Generator

Add a world sampler that generates full hidden-hand assignments consistent with:

- own hand
- all played cards
- current trick
- known void constraints
- remaining hand sizes
- hard private-memory facts such as exact passed-card recipient

Recommended naming:
- `sample_worlds(...)`
- outputs a list of determinized full states or a `DeterminizedWorld` dataclass

Requirements:
- deterministic under fixed seed
- shared world set across all candidate moves in a decision
- hard-constraint honoring
- no use of the true hidden hands from the live `GameState`

Important recommendation:
- use common random numbers across candidate moves
- the same sampled worlds should be reused for each legal move in a decision
- this reduces search noise and later supports move-vs-move explanation

### 4. Whole-Hand Simulation Harness

The first search bot does not need a deep tree. It does need a clean whole-hand simulator from a determinized world.

Recommended behavior:
- clone determinized state
- apply one root move candidate
- simulate the rest of the hand to completion using fixed policies

Recommended rollout policy:
- use `heuristic_v3` as the default playout policy
- instantiate it in a deterministic low-noise mode, ideally with `rollout_samples=0`

Why:
- it reuses the strongest handcrafted baseline
- it keeps runtime practical
- it avoids stacking Monte Carlo noise inside Monte Carlo search
- it makes explanation easier because the fallback policy is already documented

Important recommendation:
- do not let the first search bot recursively search its own future turns
- root search plus heuristic playout is the right initial complexity level

### 5. Utility Function

The first search bot should optimize a simple, defensible utility.

Recommended initial utility:
- primary: minimize projected hand points from the current hand
- secondary: projected post-hand total score / rank tie-break

Why this is a good first cut:
- whole-game multi-hand search is not the right first step
- most tactical value in Hearts comes from current-hand consequences
- total-score tie-break keeps the bot from ignoring game context entirely

Recommended output metrics per candidate:
- mean utility across worlds
- mean projected hand points
- min / max utility
- optional spread or variance
- paired delta vs baseline heuristic choice

## First Search Bot Plan

## Recommended Name

- `search_v1`

This fits the existing naming style:
- `heuristic`
- `heuristic_v2`
- `heuristic_v3`
- `search_v1`

## Scope

`search_v1` should search play decisions only.

Pass policy:
- reuse `heuristic_v3` pass logic initially
- record private pass-memory facts during that step

Reason:
- play search is the high-value next step
- pass search is a separate problem and can come later
- using `heuristic_v3` pass logic keeps the first search bot smaller and easier to benchmark

## Decision Algorithm

For each play decision:

1. Build `SearchPlayerView` from the current state plus seat-private memory.
2. Generate `N` sampled worlds consistent with public and private knowledge.
3. Enumerate all legal root moves.
4. For each move, evaluate that move across the same sampled worlds.
5. In each sampled world:
   - instantiate a determinized full state
   - apply the candidate move
   - roll the rest of the hand forward using deterministic `heuristic_v3` playout bots
   - compute projected utility
6. Aggregate world results.
7. Choose the best move with deterministic tie-breaks.

## Recommended Initial Defaults

These are good first-cut defaults, not permanent tuning rules:

- world samples: `16-32`
- evaluate all legal moves at the root
- rollout policy: deterministic `heuristic_v3` with rollout disabled
- tie-break order:
  1. highest mean utility
  2. best paired delta vs baseline heuristic move
  3. lower spread if still tied
  4. deterministic card-order tie-break

Recommendation:
- start with evaluating all legal moves
- add heuristic-based candidate pruning only if runtime proves too slow

## Determinism Rules

The search bot should follow strict determinism rules:

1. World seeds are derived once per decision from the provided RNG.
2. The same world set is reused for all legal moves in that decision.
3. Rollout policy is deterministic.
4. Final tie-breaks are explicit and stable.

This should hold for:
- CLI simulations
- benchmark runs
- server bot turns
- viewer recommendation mode

## Explanation / Debug Plan

The current explanation system is a project strength and should be extended, not replaced.

### 1. Generalize Reason Serialization

Current server helpers are effectively heuristic-specific:
- `_serialize_heuristic_v2_pass_reason`
- `_serialize_heuristic_v2_play_reason`

That is already stretched because it is used for both `heuristic_v2` and `heuristic_v3`.

Recommended next step:
- introduce a generic bot-reason serialization layer
- avoid expanding bot-name `if/else` branches in `server/tables.py`

### 2. Add Search-Specific Reason Payloads

Do not overload heuristic fields like `rollout_score` to mean search statistics.

Recommended play payload family:
- `SearchPlayDecisionReason`
- `SearchPlayCandidateReason`

Recommended fields:
- chosen card
- legal move mode
- sampled world count
- candidate list
- per candidate:
  - mean utility
  - projected hand-point average
  - projected post-hand total average
  - utility spread or min/max
  - paired delta vs baseline heuristic move
  - summary tags
- baseline heuristic reference:
  - `heuristic_v3` chosen move
  - whether search agreed or disagreed

### 3. Preserve Move Comparison Value

The reason payload should be shaped so later tooling can answer:

- why search preferred move A over move B
- why search disagreed with `heuristic_v3`
- why search disagreed with the human move

Recommended first-cut support:
- include paired world-by-world comparison summaries between:
  - chosen search move
  - baseline heuristic move
  - optionally top alternative

This does not require dumping every sampled world into the normal UI.

Recommended compact comparison metrics:
- mean delta vs baseline
- number of worlds where search move beat baseline
- worst-case loss vs baseline
- best-case gain vs baseline

### 4. Carry Forward Existing Tag Discipline

Search explanations should still use compact tags and structured facts.

Good search-era tag examples:
- `known_passed_qs_right`
- `void_ahead_in_led_suit`
- `suit_exhausted_outside_hand`
- `candidate_stable_across_worlds`
- `baseline_move_high_variance`

Important recommendation:
- keep search tags about inference facts and comparison outcomes
- do not generate vague natural-language prose in the first cut

### 5. UI Recommendation Path

The current UI already has two useful debug panels:
- viewer recommendation
- opponent explanation

Recommendation:
- extend those paths to support `search_v1`
- do not create a separate third recommendation system

Viewer recommendation should show:
- advisory bot name
- search choice
- baseline heuristic choice
- top 3 candidates with values
- search-vs-heuristic disagreement summary

Opponent explanation should show:
- the same kind of payload when a search bot acts

## Testing Plan

Search work should add three test layers:

1. low-level deterministic/inference tests
2. scenario regression tests
3. integration and benchmark validation

### 1. Low-Level Search Support Tests

Add focused tests for:

- hidden-information-safe player view
- public knowledge extraction
- void inference
- suit exhaustion recognition
- private own-pass memory
- determinized world sampling
- sampled worlds honoring hard constraints
- deterministic world generation under fixed seed

Critical anti-cheating test:
- create two full `GameState` objects with the same public information and same acting player's hand, but different hidden opponent hand assignments
- under the same seed and same private memory, `search_v1` must make the same decision

That test is important because the live engine state still contains true hidden hands.

### 2. Scenario Regression Tests

Add curated search-specific scenarios in addition to existing heuristic scenarios.

High-value first scenarios:

1. Known passed `QS`
   - bot passed `QS` right or across
   - card is still unseen
   - decision should reflect that exact hidden danger location

2. Suit exhaustion / late-hand counting
   - no outside cards remain in a suit
   - search should understand that a "safe" card is actually owned-suit control or future escape inventory

3. Void pressure
   - players ahead are known void
   - search should avoid leads that are only superficially safe

4. Moon-defense stopper preservation
   - search should preserve a real stopper when sampled worlds show it matters later in the hand

5. Search-vs-heuristic disagreement cases
   - positions where `heuristic_v3` prefers one move but sampled-world evaluation prefers another
   - these should become stable regression scenarios once discovered

Recommendation:
- keep these as explicit scenario tests, not only benchmark notes

### 3. Integration Tests

Add integration coverage for:

- deterministic full-game self-play with `search_v1`
- deterministic mixed games with `search_v1` and heuristic bots
- server snapshot exposure of search decision payloads
- viewer recommendation support for `search_v1`
- persistent private-memory behavior across server actions within a hand

### 4. CI Discipline

Do not make aggregate performance brittle in CI.

Keep strict assertions for:
- legality
- determinism
- anti-cheating invariance
- hard scenario expectations
- payload shape

Keep benchmark strength assertions out of CI hard gates.

## Benchmark Plan

Mixed benchmarking should continue and should be easier to run.

### 1. Keep Existing Metrics

Continue reporting:
- win rate
- average points
- average rank

### 2. Standardize Search Comparisons

Recommended first benchmark set:

1. `search_v1` vs three `heuristic_v3` seats
   - four seat rotations
   - fixed seed schedule

2. `search_v1` mixed field
   - one seat each of:
     - `search_v1`
     - `heuristic_v3`
     - `heuristic_v2`
     - `random`
   - four seat rotations

3. sanity runs
   - all `search_v1`
   - `search_v1` vs three `random`

### 3. Codify The Benchmark Workflow

Current mixed-field practice is good, but it should not remain only a report convention.

Recommended follow-up:
- add a standard benchmark matrix runner, either:
  - a thin new CLI mode
  - or a dedicated `tools/` script

It should:
- run seat-rotated matchups
- emit stable summaries
- make local report generation easier

### 4. Track Runtime Separately

Search adds a second important metric:
- decision cost

Track as diagnostics:
- average decision time
- total benchmark runtime
- average worlds evaluated per move

Do not bake runtime thresholds into CI immediately.

## Suggested Implementation Order

### Phase 0: Runtime and Interface Foundations

1. Add hidden-information-safe search view.
   - Sub-step 1: define the search-side types and boundary
     - `SearchPlayerView`
     - `PublicKnowledge` placeholder shape
     - view-construction API from `GameState`
   - Sub-step 2: implement the minimal hidden-information-safe view
     - own hand
     - public trick / taken-trick state
     - legal moves
     - no opponent hidden hands
   - Sub-step 3: add hard boundary tests
     - view does not expose opponent hands
     - same public state plus same own hand yields the same derived view
     - anti-cheating fixtures / tests
   - Sub-step 4: add one thin consumer
     - not the full search bot
     - just enough to prove the interface is usable
2. Add persistent bot runtime/session support for server and CLI.
   - Sub-step 1: audit current bot lifecycle differences
     - CLI bot instances persist within a simulated game
     - server bot instances are recreated per action
   - Sub-step 2: define the runtime/session abstraction
     - persistent bot instances by seat
     - reset hooks for new hand / new game
     - no search-specific behavior yet
   - Sub-step 3: wire CLI through the runtime layer
     - behavior-preserving first
     - determinism must remain unchanged
   - Sub-step 4: wire server `Table` through the runtime layer
     - persistent per-seat bot instances
     - preserve current gameplay flow and pacing behavior
   - Sub-step 5: add lifecycle and determinism tests
     - memory persists within a hand
     - runtime resets correctly between hands / games
     - determinism remains unchanged
3. Add generic reason serialization hooks so search payloads have a place to go.
   - Sub-step 1: define a generic decision-reason interface / serializer boundary
     - pass reason path
     - play reason path
     - unsupported-bot fallback behavior
   - Sub-step 2: adapt heuristic bots to the generic boundary without changing payload shape
     - preserve current `heuristic_v2` / `heuristic_v3` output
   - Sub-step 3: refactor server snapshot capture to use the generic serialization path
     - opponent debug decisions
     - viewer recommendation path
   - Sub-step 4: add serialization-path tests
     - heuristic payloads stay unchanged
     - unsupported bots remain explicit
     - viewer recommendation path still works

### Phase 1: Search Support Layer

1. Add public knowledge extraction.
   - Sub-step 1: define the neutral `PublicKnowledge` surface
     - card-seen / unplayed tracking
     - `QS` live / dead
     - per-suit remaining structure
     - remaining cards by seat
   - Sub-step 2: implement deterministic extraction from `GameState`
     - current trick
     - taken tricks
     - public suit-follow history
   - Sub-step 3: add negative-information helpers
     - void suits by player
     - suit exhaustion outside own hand
     - remaining-card constraints by opponent
   - Sub-step 4: add focused regression tests
     - stable extraction under fixed public state
     - invariance to hidden opponent-hand assignment
     - exact void / exhaustion fixtures
2. Add private own-pass memory.
   - Sub-step 1: define `SeatPrivateMemory`
     - passed cards by recipient
     - hand-scoped reset semantics
     - query helpers for known passed dangers
   - Sub-step 2: wire pass-memory capture into bot/runtime lifecycle
     - record on pass choice
     - preserve across later actions in the same hand / game
   - Sub-step 3: surface private memory into `SearchPlayerView`
     - read-only search-facing snapshot
     - no leakage into engine state
   - Sub-step 4: add focused tests
     - memory recorded correctly
     - memory resets on new hand / game
     - known-passed-card queries behave deterministically
3. Add determinized world sampling.
   - Sub-step 1: define sampled-world types and sampler API
     - `DeterminizedWorld`
     - sampled hidden-hand assignment shape
     - seed / replay contract
   - Sub-step 2: implement constrained world generation
     - own hand excluded from opponent allocation
     - played cards / current trick respected
     - remaining hand sizes respected
     - void constraints respected
     - private known-pass facts respected
   - Sub-step 3: make candidate evaluation reuse a shared world set
     - common random numbers across root moves
     - deterministic world ordering
   - Sub-step 4: add hard sampler tests
     - legality / conservation of cards
     - fixed-seed determinism
     - anti-cheating invariance against true hidden live hands
     - explicit impossible-world rejection fixtures
4. Add whole-hand simulation harness with deterministic heuristic playouts.
   - Sub-step 1: define simulation entrypoints
     - clone determinized state
     - apply root candidate
     - roll hand to completion
   - Sub-step 2: wire deterministic playout bots
     - `heuristic_v3` policy reuse
     - rollout-disabled / low-noise configuration
   - Sub-step 3: define rollout result summary
     - projected hand points
     - projected total score delta
     - utility output for later aggregation
   - Sub-step 4: add harness tests
     - deterministic repeated simulation under fixed seed
     - legal completion from sampled worlds
     - no mutation of source world / source state

### Phase 2: `search_v1`

1. Add bot shell and factory registration.
   - Sub-step 1: define `search_v1` configuration dataclass
     - world count
     - playout seed rules
     - fallback behavior toggles
   - Sub-step 2: add bot class skeleton and factory registration
     - bot name wiring
     - constructor defaults
     - no search logic yet
   - Sub-step 3: delegate pass policy to `heuristic_v3`
     - preserve current pass/debug behavior where practical
   - Sub-step 4: add bot construction and pass-policy smoke tests
2. Add root-only sampled-world play evaluation.
   - Sub-step 1: build `SearchPlayerView` and root candidates
   - Sub-step 2: sample one shared `DeterminizedWorldSet` per decision
     - common random numbers across root moves
   - Sub-step 3: simulate each candidate across the shared world set
   - Sub-step 4: aggregate rollout summaries into candidate scores
     - average projected hand points
     - average projected score delta
     - utility summary for final choice
3. Add final move selection and determinism rules.
   - Sub-step 1: define deterministic aggregation and tie-break order
   - Sub-step 2: choose final play and store a structured reason payload
   - Sub-step 3: add fixed-seed determinism tests
   - Sub-step 4: add anti-cheating invariance tests against true hidden live hands
4. Add baseline safeguards and defaults.
   - Sub-step 1: fallback behavior for impossible sampling or empty world sets
   - Sub-step 2: set safe default configuration values
   - Sub-step 3: add targeted regression tests versus `heuristic_v3`
   - Sub-step 4: leave hooks for later benchmark/config wiring

### Phase 3: Explanation and Comparison

1. Refine search reason payloads.
   - Sub-step 1: review the current `SearchPlayDecisionReason` against viewer/debug needs
   - Sub-step 2: add any missing stable explanation fields needed for comparison and display
   - Sub-step 3: keep payload shape serializer-backed and deterministic
   - Sub-step 4: add focused payload/serialization tests
2. Add baseline-heuristic comparison inside search explanations.
   - Sub-step 1: define comparison model/types for `search_v1` vs `heuristic_v3`
   - Sub-step 2: evaluate baseline `heuristic_v3` alongside the search choice on the same live decision
   - Sub-step 3: attach comparison summaries to the search reason payload
   - Sub-step 4: add agreement/disagreement regression tests
3. Extend server snapshot serialization.
   - Sub-step 1: verify the generic reason boundary is sufficient or extend it minimally
   - Sub-step 2: ensure table snapshot/debug capture carries search payloads cleanly
   - Sub-step 3: preserve current heuristic viewer/debug behavior
   - Sub-step 4: add focused server tests for search recommendation/debug capture
4. Extend UI rendering for search recommendation/explanation panels.
   - Sub-step 1: render search payloads without breaking heuristic payload rendering
   - Sub-step 2: add comparison-specific lines for search vs baseline explanations
   - Sub-step 3: keep the panel concise and readable for normal use
   - Sub-step 4: add lightweight UI-facing regression coverage where practical

### Phase 4: Tests and Benchmark Tooling

1. Add low-level support tests.
   - Sub-step 1: add sampler constraint edge-case tests
     - impossible allocation fixtures
     - void-respecting assignment fixtures
     - own-pass-memory constraint fixtures
   - Sub-step 2: add rollout summary edge-case tests
     - moon scoring projection checks
     - raw-vs-scored projection checks
     - fixed-seed per-world summary checks
   - Sub-step 3: add search-view and runtime integration edge-case tests
     - private-memory reset/visibility cases
     - hidden-information invariance edge cases
   - Sub-step 4: keep these tests narrow, deterministic, and fixture-driven
2. Add scenario regression suite.
   - Sub-step 1: define reusable scenario fixture helpers/builders
     - concise state constructors
     - deterministic seat/hand setup helpers
   - Sub-step 2: add early high-spade lead regressions
     - suspicious early `QS` lead fixtures
     - suspicious early `KS` lead fixtures
     - frame these as strategic regression checks, not rules bugs
   - Sub-step 3: add at least one late-hand counting case
     - known remaining-card fixture
     - public-inference-sensitive decision
   - Sub-step 4: add search-vs-heuristic disagreement fixtures
     - agreement case
     - disagreement case with expected preferred move
3. Add deterministic integration tests.
   - Sub-step 1: add fixed-seed end-to-end `search_v1` table/game runs
   - Sub-step 2: add repeated-run equality checks for the same seed/config
   - Sub-step 3: add mixed-field deterministic checks
     - `search_v1` vs `heuristic_v3`
     - `search_v1` vs mixed opponents
   - Sub-step 4: keep runtime bounded so these stay practical in CI/dev loops
4. Add codified benchmark runner or CLI extension with parameter sweep support.
   - Sub-step 1: define stable benchmark matrix inputs
     - bot lineup presets
     - seed sets
     - target score / game count presets
   - Sub-step 2: add explicit `world_count` sweep support
     - at minimum `1, 2, 4, 8`
     - optionally `16` for slower comparison runs
   - Sub-step 3: keep output stable and comparable
     - per-bot score summaries
     - rank/win summaries
     - runtime summary
   - Sub-step 4: use the tooling for disciplined parameter tuning
     - first focus on `world_count`
     - avoid tuning multiple secondary knobs at once unless clearly justified

### UI Follow-Up: Live Table Layout and Controls

This should stay scoped as a focused UX cleanup, not a redesign of the whole app.

1. Compact always-visible live controls.
   - Sub-step 1: replace the large `Play/Pause` and `Step` buttons with compact icon controls
   - Sub-step 2: add keyboard shortcuts for `Step` and `Play/Pause`
   - Sub-step 3: keep tooltips and accessible labels so icon-only controls remain clear
2. Collapse secondary controls behind toggles or drawers.
   - Sub-step 1: make `Pace` collapsible by default during normal play
   - Sub-step 2: make `Bot Debug` collapsible by default but easy to reopen and pin
   - Sub-step 3: avoid modal popups; prefer inline disclosure, drawer, or side-panel behavior
3. Reorganize desktop layout to use horizontal space better.
   - Sub-step 1: keep the table and hand/pass area as the primary visual focus
   - Sub-step 2: move secondary controls/debug into side or auxiliary regions on wider screens
   - Sub-step 3: reduce the need to zoom out just to see the live table and hand together
4. Preserve the current table score/point presentation.
   - Sub-step 1: keep seat totals and current hand points where they already work well
   - Sub-step 2: do not move that scoring information into a separate meta panel unless there is a clear gain

### Phase 4.5: Benchmark Execution and Tuning

With Phase 4 tooling in place, the next work should be disciplined benchmark execution rather than more implementation churn.

1. Run codified `benchmark-search` sweeps.
   - run `mixed_search_field`
   - run `all_search_v1`
   - start with `world_count = 1, 2, 4, 8`
   - optionally add `16` as a slower comparison point if needed
2. Summarize runtime and strength tradeoffs.
   - compare win rate, average points, and average rank
   - compare runtime cost per sweep setting
   - look for diminishing returns past the lower world counts
3. Decide whether to raise the default `search_v1.world_count`.
   - prefer a benchmark-backed change, not an intuition-only change
   - keep usability/runtime in view alongside strength
4. Write results to a dedicated benchmark report.
   - create `AGENTS_V4_BENCHMARK_REPORT.md`
   - include benchmark matrix, outputs, observations, and recommendation
5. Only after the benchmark report, decide whether follow-up tuning is warranted.
   - if needed, add 1-2 more scenario fixtures for behaviors exposed by the benchmark runs
   - avoid tuning multiple secondary knobs at once unless the report justifies it

## Acceptance Criteria For This Phase

This phase should count as complete when all of the following are true:

1. `search_v1` exists and is selectable like the other bots.
2. `search_v1` is deterministic under fixed seeds.
3. `search_v1` does not depend on true hidden opponent hands from live state.
4. Server and CLI paths preserve any required private search memory within a hand.
5. Search decision payloads are inspectable in the current recommendation/debug workflow.
6. Scenario tests cover:
   - determinization constraints
   - own-pass memory
   - search-vs-heuristic disagreement cases
   - at least one late-hand counting case
7. Mixed-field benchmark workflow remains usable and codified.
8. `heuristic_v3` remains intact as the frozen handcrafted baseline.

## Recommended First Implementation Decision

If implementation starts, the cleanest first coding step is:

1. create the hidden-information-safe search view
2. add persistent bot/runtime memory support
3. only then build the sampler and `search_v1`

That order matters because otherwise the search bot risks being built on top of:
- accidental hidden-information leakage
- non-persistent server memory
- heuristic-only debug plumbing
