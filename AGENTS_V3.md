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
  - first trick refinement: if forced to win a club-follow, shed the highest club; if able to lose, play highest losing club
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
- Add internal decision-reason payload hooks:
  - capture chosen move rationale, top alternatives, and rollout summary data
  - keep hooks internal in Phase 3 (no UI exposure yet)

Constraints:
- Keep runtime practical for CLI simulations.
- Keep behavior deterministic with explicit RNG usage.
- Keep explanation payload generation lightweight and side-effect-free.

Acceptance criteria:
- v2 outperforms v1 on benchmark suite.
- No regressions in legality and determinism tests.
- Internal reason payload data is available for future debug/UI explanation mode integration.

## Phase 3.5: HeuristicBot v2 Stabilization

Scope:
- Treat the initial `heuristic_v2` implementation as a first pass, not a finished upgrade.
- Fix strategically incoherent behaviors before moving on to search-oriented work.
- Prioritize removing obviously bad tactics over adding more cleverness.

Focus areas:
- Opening leads:
  - remove context-free "shed spade risk" bonuses on opening leads
  - prevent `Q♠` from being treated as a generally good lead
  - refine lead scoring so dangerous high cards are only shed in defensible spots
  - once hearts are broken, treat very low hearts as valid escape leads rather than blindly preferring high spades
- High-spade handling:
  - separate "dangerous to keep" from "safe to unload now"
  - only reward unloading `Q♠` / `K♠` / `A♠` when trick context makes it plausibly safe
  - penalize `K♠` / `A♠` leads when a cheaper low lead is available that is more likely to get the bot out of the lead
- Rollout / base-score interaction:
  - ensure rollout does not silently skip the exact situations where lead safety matters most
  - rebalance base heuristics so unsupported bonuses cannot dominate obvious tactical risk
  - skip rollout for guaranteed-losing, non-point follow cards when rollout cannot change whether the card wins the current trick
  - preserve deterministic "highest losing follow" behavior in those spots instead of letting rollout noise break ties between equally safe losing cards
  - use shared rollout samples per decision so outcome-equivalent candidates are evaluated against the same sampled futures
  - avoid candidate-by-candidate RNG drift creating fake tactical differences between cards with identical rest-of-trick risk
- Moon-defense cleanup:
  - keep moon-blocking logic from distorting normal, non-moon play too aggressively

Testing additions:
- Add regression tests for clearly bad v2 choices:
  - do not lead `Q♠` when a safer low spade lead exists
  - do not overvalue dangerous high-spade opening leads without supporting context
  - once hearts are broken, do not lead `K♠` over a low heart escape lead like `3H`
- Add scenario tests covering:
  - safe vs unsafe spade unload spots
  - opening-lead comparisons across low cards vs dangerous honors
  - broken-hearts lead comparisons across low hearts vs dangerous high spades
  - guaranteed-losing non-point follow choices where rollout should not override the base highest-losing-card heuristic
  - outcome-equivalent follow choices where shared rollout samples should prevent random preference flips
  - moon-defense behavior not overriding obvious local safety

Acceptance criteria:
- `heuristic_v2` no longer makes obvious tactical self-owns in normal play.
- Regression tests cover the known high-spade lead failure mode.
- Regression tests cover the broken-hearts low-heart-vs-high-spade lead case.
- Rollout no longer introduces noise into guaranteed-losing, non-point follow decisions.
- Rollout no longer invents differences between outcome-equivalent candidates purely because they saw different sampled futures.
- Benchmark results remain at least competitive with v1 and clearly above random.
- Phase 3 reason payload hooks remain intact for future UI explanation mode.

## Phase 3.6: HeuristicBot v2 Debug Explanations

Scope:
- Expose existing internal `heuristic_v2` decision-reason payloads for debugging.
- Keep this phase developer-facing and lightweight, not polished end-user UX.
- Limit explanation support to `heuristic_v2`; do not backfill `heuristic` v1 unless it is nearly free.

Implementation targets:
- Server/API:
  - include latest `heuristic_v2` pass/play reason payload in a debug-safe snapshot field or dedicated debug endpoint
  - keep payload optional so non-`heuristic_v2` seats do not need explanation data
  - avoid changing gameplay behavior or pacing
- UI:
  - add a toggleable debug inspector for the latest bot decision
  - show chosen card, play mode, top candidate alternatives, and score components
  - render rationale tags directly from payload (for example: `avoid_qs_lead`, `low_heart_escape_lead`)
- Reuse:
  - preserve payload shape so later search-bot explanations can use the same or similar presentation

Constraints:
- Do not generate natural-language prose explanations in this phase.
- Do not expose explanation data by default in a noisy way during normal play.
- Keep payload generation side-effect-free and cheap enough for normal simulations.

Acceptance criteria:
- A developer can inspect the latest `heuristic_v2` decision in the UI without reading logs.
- Exposed data clearly separates chosen move, alternatives, base score, rollout score, and tags.
- Non-`heuristic_v2` seats continue to work without explanation payloads.
- Existing tests remain green; add focused server/UI coverage only where useful.

## Phase 4: HeuristicBot v3 (Hand-Structure-Aware Upgrade)

Scope:
- Keep `heuristic_v2` intact as the stabilized benchmarked baseline.
- Implement `heuristic_v3` as a new bot with stronger hand-structure-aware pass logic and targeted follow-on play refinements.
- Focus on fixing remaining obviously bad pass judgments exposed by the debug inspector before moving to search.

Implementation targets:
- Bot/versioning:
  - add `HeuristicBotV3` alongside `HeuristicBotV2`
  - expose `heuristic_v3` through bot factory, CLI, server, and UI bot selectors
  - preserve v2 reason/debug hooks as the reference baseline
- Pass heuristics:
  - replace flat card-only pass ordering with suit-sensitive low-card preservation
  - preserve truly safe low cards aggressively:
    - clubs: `2C-4C`
    - diamonds/spades: `2-3`
    - hearts: `2H-4H` usually preserved
  - treat next-band cards as context-sensitive rather than auto-safe:
    - `5C`
    - `4D/4S`
    - `5H`
    - `6H`
  - treat higher hearts as normal pass candidates by default
  - rank dangerous clubs/diamonds honors above tiny hearts when appropriate
- Spade-structure logic:
  - add `Q♠` pass exceptions based on total spade length
  - with `4 or fewer` total spades, usually pass `Q♠`
  - with `5 or more` total spades, often keep `Q♠`
  - add `A♠` / `K♠` protection logic so they are not blindly passed when they function as cover
  - never pass low spades in normal v3 logic
- Lead-play refinements:
  - avoid leading spades when holding `Q♠` with short-ish spade length unless materially forced
  - specifically, when holding `Q♠` and `4 or fewer` total spades, prefer a reasonable non-spade lead over flushing spades early
  - avoid leading spades when not holding `Q♠` but holding `A♠` and/or `K♠` with fragile short spade shape
  - specifically, when holding `A♠` / `K♠` without `Q♠` and only a small amount of low-spade cover, prefer a reasonable non-spade lead over exposing protection cards
  - do not treat `J♠` as a true "high spade" in the same danger class as `Q♠` / `K♠` / `A♠`
  - distinguish dangerous spade-control leads (`Q♠` / `K♠` / `A♠`) from safer sub-queen spade leads
  - when `Q♠` is still live, allow `J♠` or lower spade leads to outrank riskier mid and mid-high off-suit leads that can win awkward queen-dump tricks
  - implement these as strong context-sensitive penalties rather than absolute bans so forced-spade cases still behave sensibly
- Public-info tracking refinements:
  - add lightweight card-tracking helpers based only on public information already visible in trick history
  - track whether `Q♠` is still live, how many cards in each suit have already been played, and the current lowest unseen ranks by suit where practical
  - infer player voids from prior failure-to-follow-suit and make that information available to v3 lead/discard heuristics
  - use these signals to avoid obviously bad "safe lead" assumptions, especially when a mid off-suit lead is more likely to win because several lower cards are already gone or nearby players are void
  - keep this phase to hard public-info inference only; do not add speculative opponent-reading or pass-memory logic yet
- Optional small hand-shape adjustments:
  - short-suit honors become riskier pass candidates
  - lower cover beneath a card makes it safer to keep

Constraints:
- Keep the logic heuristic and testable; do not turn v3 into a large exception pile.
- Prefer general structural rules over player-style-specific one-offs.
- Reuse the same debug explanation pattern where practical so v2 vs v3 can be inspected consistently.

Acceptance criteria:
- `heuristic_v3` no longer makes obviously bad low-heart / low-card pass decisions like passing `3H` over `JC` / `JD` in ordinary hands.
- `heuristic_v3` avoids structurally wrong high-spade passes in long-spade hands.
- `heuristic_v3` avoids short-spade opening leads that prematurely flush a suit containing `Q♠` or fragile `A♠` / `K♠` protection when a sane non-spade lead exists.
- `heuristic_v3` no longer penalizes `J♠`-type leads as if they were `Q♠` / `K♠` / `A♠`, and can prefer sub-queen spade leads over riskier mid off-suit leads when `Q♠` is still out.
- `heuristic_v3` can use public trick history to recognize basic void information and suit depletion when evaluating lead safety.
- v3 remains deterministic and legal.
- v3 can be benchmarked cleanly against `heuristic_v2`, `heuristic`, and `random`.

## Test Plan

Update/add tests:
- `tests/test_bots.py`:
  - pass-priority scenarios (`Q♠`, high spades, high hearts)
  - play-choice scenarios for lead/follow/off-suit
  - `heuristic_v2` regression scenarios for dangerous opening leads, broken-hearts low-heart escape leads, and unsafe high-spade dumps
  - `heuristic_v3` pass-structure scenarios for low-heart preservation, dangerous offsuit honors, and long-spade `Q♠` / `A♠` / `K♠` exceptions
  - `heuristic_v3` lead-choice scenarios for short-spade `Q♠` avoidance and fragile `A♠` / `K♠` protection leads
  - `heuristic_v3` lead-choice scenarios distinguishing `J♠` / sub-queen spades from true dangerous spade-control leads
  - `heuristic_v3` public-info scenarios for suit depletion and inferred player voids affecting lead/discard choices
- integration/smoke:
  - deterministic full-game runs with heuristic bots
  - legal-move invariants remain enforced
- server/UI path:
  - bot seat type selection and persistence in table state
  - deterministic auto-advance behavior when seats use `heuristic`
  - optional debug payload exposure for `heuristic_v2` decisions

Do not make benchmark win-rate assertions brittle in CI:
- Keep strict assertions for determinism/legality.
- Keep performance summaries as diagnostics/local benchmark outputs.

## Move-to-Complex Trigger

Start complex methods (determinized search) only after:
- Heuristic v2 is stable and well-tested.
- Benchmark harness is automated and trusted.
- Heuristic bot has a clear margin over random across enough games/seeds.
- Heuristic v2 debug explanations are available for fast behavior inspection.
- We have decided whether `heuristic_v3` is worth keeping as the stronger scripted baseline before search.

## Suggested Implementation Order

1. Phase 1 benchmark + bot-selection plumbing
2. Phase 2 HeuristicBot v1
3. Phase 2 test coverage
4. Phase 2.5 server/UI bot-selection plumbing
5. Phase 2.6 UI gameplay polish
6. Phase 3 HeuristicBot v2
7. Phase 3.5 HeuristicBot v2 stabilization
8. Phase 3.6 HeuristicBot v2 debug explanations
9. Phase 4 HeuristicBot v3
10. Compare v2/v3 and decide on search transition
