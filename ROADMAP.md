# Hearts AI Roadmap

## Purpose

This file tracks the longer-term bot and product direction for the project.

Use `AGENTS_v3.md` for the current implementation checklist.
Use this roadmap for sequencing what comes after the current heuristic-first phase.

## Current State

- Core Hearts engine is in place and playable.
- CLI benchmarking and UI bot-selection plumbing exist.
- `HeuristicBot` v1 is implemented as a deterministic rule-based baseline.
- `HeuristicBotV2` exists as an early risk-aware upgrade with internal reason-payload hooks.
- UI can select different bot policies, including `heuristic_v2`.

## Guiding Principles

- Prefer measurable progress over speculative complexity.
- Keep bots deterministic when given the same game state and RNG seed.
- Do not jump to RL before evaluation infrastructure is trustworthy.
- Use stronger baselines to make later search or learning work interpretable.

## Near-Term Priorities

### 1. Stabilize HeuristicBot v2

Goal:
- Make `heuristic_v2` strategically coherent before adding a more complex bot class.

Focus areas:
- Remove obviously bad context-free rules.
- Make risk-shedding logic situational rather than universal.
- Improve lead logic so dangerous cards are not dumped into bad spots.
- Tighten moon-defense behavior so it helps more often than it hurts.

Exit criteria:
- No glaring tactical self-owns in normal play.
- Determinism and legality tests remain green.
- Benchmark results show v2 at least consistently ahead of random and preferably ahead of v1.

### 2. Strengthen Evaluation

Goal:
- Make bot comparisons credible and easy to rerun.

Focus areas:
- Standard benchmark command sets and seed ranges.
- Summary metrics: win rate, average score, finishing rank.
- Head-to-head comparisons: `random` vs `heuristic`, `heuristic` vs `heuristic_v2`.
- Save benchmark notes or outputs in a lightweight, repeatable format.

Exit criteria:
- We can answer "is this bot better?" with data instead of anecdotes.
- Benchmark runs are easy enough to use during normal iteration.

### 3. Add Explanation Hooks To UI

Goal:
- Surface bot reasoning for debugging and design validation.

Focus areas:
- Expose existing internal reason payloads from `HeuristicBotV2`.
- Add an optional debug/explain mode in the UI.
- Show chosen move, main rationale tags, and top alternatives.

Exit criteria:
- A developer can inspect why a bot chose a move without reading logs or stepping through code.

## Mid-Term Bot Progression

### 4. HeuristicBot v2.5 or v3

Goal:
- Add a small number of context-aware improvements without turning the bot into an unmaintainable rule pile.

Candidates:
- Better opening-lead selection.
- Safer queen-of-spades handling.
- More precise end-of-trick logic when points are impossible.
- Better handling of voids, short suits, and controlled dumps.

Constraint:
- If improvements start requiring many special cases, stop and move effort toward search instead.

### 5. Search-Based Bot Prototype

Goal:
- Introduce a stronger decision layer without needing full RL infrastructure.

Likely direction:
- Shallow hidden-information search.
- Determinized sampling from unseen cards.
- 1-ply or limited-depth move evaluation using heuristic scoring.

Why this comes before RL:
- Easier to validate.
- Easier to debug.
- Builds on the current engine and evaluation tooling.

Exit criteria:
- Search bot is legal, deterministic under fixed sampling seed, and measurably competitive with the best heuristic bot.

## RL Readiness Criteria

Do not start reinforcement learning until most of the following are true:

- The rules engine is stable and trusted.
- Bot evaluation is automated and repeatable.
- At least one strong heuristic or search baseline exists.
- State/action interfaces are clean and well defined.
- Self-play simulation throughput is known and acceptable.
- Reward design is explicit and not obviously flawed.
- We have a clear success target beyond "see what happens."

## RL Phase

Once the project is ready, the first RL phase should be narrow:

- Keep the environment headless and simulation-first.
- Start with self-play experiments, not UI features.
- Compare learned agents against `random`, `heuristic`, and the best search/heuristic bot.
- Treat explanation/debug tooling as mandatory, not optional.

Good first goals:
- Beat random reliably.
- Match or beat heuristic baselines over a meaningful benchmark set.

Bad first goals:
- End-to-end production deployment.
- Large model complexity before evaluation is stable.
- Replacing interpretable bots too early.

## Product / UX Follow-Ons

These are useful, but secondary to bot quality:

- Better animation and card-motion polish.
- Friend-sharing via real deployment rather than local tunneling.
- Bot explanation mode in the live table UI.
- Saved match records and replay tools.
- Stronger spectating and debugging features.

## Decision Rules

Use these rules to choose the next major step:

- If bot behavior is still making obvious tactical mistakes, keep improving heuristics.
- If heuristics are getting harder to extend cleanly, start a search prototype.
- If search and evaluation are both stable, then RL becomes a serious option.
- If a feature does not improve play quality, measurability, or debugging, deprioritize it.
