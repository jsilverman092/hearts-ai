# Hearts AI Roadmap

## Purpose

This file tracks the longer-term bot and product direction for the project.

Use `AGENTS_v3.md` for the current implementation checklist.
Use this roadmap for sequencing what comes after the current heuristic-baseline phase.

## Current State

- Core Hearts engine is in place and playable.
- CLI benchmarking and UI bot-selection plumbing exist.
- `HeuristicBot` v1 remains as the simple deterministic baseline.
- `HeuristicBotV2` remains available as an intermediate comparison bot.
- `HeuristicBotV3` is the current main handcrafted baseline.
- Heuristic debug reasons/tags are exposed in the UI and documented.
- Benchmarking is repeatable enough to compare heuristic iterations credibly.

## Guiding Principles

- Prefer measurable progress over speculative complexity.
- Keep bots deterministic when given the same game state and RNG seed.
- Do not jump to RL before evaluation infrastructure is trustworthy.
- Use stronger baselines to make later search or learning work interpretable.
- Add statefulness and inference only when they clearly improve play or debugging value.

## Near-Term Priorities

### 1. Freeze HeuristicBot v3 As The Main Handcrafted Baseline

Goal:
- Treat `heuristic_v3` as the reference handcrafted bot unless a clearly justified tactical fix appears.

Focus areas:
- Keep only targeted heuristic fixes for obviously bad behavior.
- Avoid broad weight retuning without a clear evaluation target.
- Preserve `heuristic`, `heuristic_v2`, and `heuristic_v3` for benchmarking and UI comparison.
- Keep reason payloads and tag docs aligned with actual code behavior.

Exit criteria:
- `heuristic_v3` remains tactically sane in normal play.
- Determinism and legality tests remain green.
- Mixed-field benchmark remains stably ahead of `heuristic_v2`, `heuristic`, and `random`.

### 2. Strengthen Evaluation

Goal:
- Make bot comparisons credible, repeatable, and useful for both aggregate and tactical review.

Focus areas:
- Standard benchmark command sets and seed ranges.
- Summary metrics: win rate, average score, finishing rank.
- Mixed-field comparisons, not just single seat-order runs.
- Lightweight benchmark notes or saved reports.
- Curated scenario/regression positions for recurring Hearts concepts.

Scenario suite candidates:
- `QS` handling and spade-control spots.
- Moon defense / stopper preservation.
- Fourth-seat safe-win decisions.
- Lead-inventory preservation.
- Late-hand endgame card-counting spots.

Exit criteria:
- We can answer "is this bot better?" with both aggregate data and scenario evidence.
- Benchmark runs are easy enough to use during normal iteration.

### 3. Improve Comparison / Explanation Tooling

Goal:
- Make bot reasoning easy to inspect, compare, and challenge.

Focus areas:
- Keep heuristic reason payloads stable and readable.
- Improve UI debug mode presentation when needed.
- Show chosen move, main rationale tags, top alternatives, and rollout contribution.
- Prepare for search-bot comparison views, not just single-bot explanations.
- Distinguish recommendation from explanation:
  - recommended move
  - why it was preferred
  - why the human move lost
  - how confident the bot is in the recommendation
- Keep room for both:
  - heuristic scores/reasons
  - stronger search-bot recommendation overlays on top of those heuristic baselines

Future extension:
- "Why this move over that move?" comparison output.
- "Why the bot disagreed with the human move" output.
- Candidate-ranking views with confidence or value estimates instead of only one recommended move.
- Hybrid feedback panels where a stronger bot recommends the move but a simpler bot still exposes legible heuristic scores.

Exit criteria:
- A developer can inspect why a bot chose a move without reading logs or stepping through code.
- The same tooling can later support search-bot explanation overlays.

## Mid-Term Bot Progression

### 4. Search Support Layers

Goal:
- Build the state and evaluation support needed for a useful search bot before writing deeper search logic.

Focus areas:
- Public-card inference beyond simple proven voids.
- Suit exhaustion by counting.
- Likely suit-length / suit-pressure inference where justified.
- Private-memory features that matter strategically, such as remembering own pass.
- Scenario-friendly hooks for inspecting inferred hidden-information state.

Important examples:
- Knowing no outside cards remain in a suit from counts, not just void evidence.
- Remembering when `QS` was passed right or across.
- Recognizing when a known passed danger is likely to be behind or ahead in seat order.

Constraint:
- Do not turn this into speculative opponent modeling without evidence that it improves decisions.

Exit criteria:
- Search code can query a clean inference/memory layer instead of rebuilding logic ad hoc.
- The inference layer is testable in isolation.

### 5. Search-Based Bot Prototype

Goal:
- Introduce a stronger decision layer without needing full RL infrastructure.

Likely direction:
- Shallow hidden-information search.
- Determinized sampling from unseen cards.
- 1-ply or limited-depth move evaluation using heuristic scoring as a prior.
- Better move comparison over multiple plausible hidden-card worlds.

Important implementation note:
- For the first search bot, it is acceptable to use `heuristic_v3` as a bootstrap rollout / continuation policy after the root move.
- That does not mean `heuristic_v3` should remain the long-term internal search policy.
- Over time, the project should separate:
  - `heuristic_v3` as the frozen handcrafted baseline for comparison and UI/debug context
  - a dedicated rollout policy used to project future play inside search
- That separation matters because otherwise changes to the baseline also change the search bot's internal evaluation behavior.

Why this comes before RL:
- Easier to validate.
- Easier to debug.
- Easier to compare against the current heuristic baseline.
- Builds directly on the current engine and evaluation tooling.

Exit criteria:
- Search bot is legal, deterministic under fixed sampling seed, and measurably competitive with or stronger than `heuristic_v3`.
- Search decisions are inspectable enough to debug surprising plays.

### 6. Search Comparison And Human-Learning Mode

Goal:
- Make the stronger bot useful for actual player learning, not just benchmark wins.

Focus areas:
- Compare heuristic move vs search move on the same position.
- Expose the main inferred risks behind the search preference.
- Support a UI mode that helps a human understand why a move is stronger.
- Show recommendation quality in a way that is honest about uncertainty:
  - relative move values
  - high/medium/low confidence
  - later, calibrated percentages only if they prove trustworthy

Examples:
- "Search preferred keeping this floor card because your future lead inventory is thin."
- "Search spent `KS` safely because `QS` risk was still live and this was a zero-point cashout."
- "Heuristic preferred `4C`, but search preferred `QC` because it safely shed future control across most sampled worlds."

Exit criteria:
- The project can teach, not just play.
- Users can inspect disagreements between their move and the bot's move in a compact way.

## RL Readiness Criteria

Do not start reinforcement learning until most of the following are true:

- The rules engine is stable and trusted.
- Bot evaluation is automated and repeatable.
- At least one strong heuristic or search baseline exists.
- State/action interfaces are clean and well defined.
- Self-play simulation throughput is known and acceptable.
- Reward design is explicit and not obviously flawed.
- We have a clear success target beyond "see what happens."
- Search or heuristic explanation tooling is strong enough to diagnose regressions.

## RL Phase

Once the project is ready, the first RL phase should be narrow:

- Keep the environment headless and simulation-first.
- Start with self-play experiments, not UI features.
- Compare learned agents against `random`, `heuristic`, `heuristic_v2`, `heuristic_v3`, and the best search bot.
- Treat explanation/debug tooling as mandatory, not optional.

Good first goals:
- Beat random reliably.
- Match or beat heuristic baselines over a meaningful benchmark set.
- Become competitive with the first search bot.

Bad first goals:
- End-to-end production deployment.
- Large model complexity before evaluation is stable.
- Replacing interpretable bots too early.

## Product / UX Follow-Ons

These are useful, but secondary to bot quality:

- Better animation and card-motion polish.
- Friend-sharing via real deployment rather than local tunneling.
- Richer bot explanation mode in the live table UI.
- Recommendation panels with confidence/value display and top-3 candidate moves.
- Hybrid feedback mode where search recommendations can still expose heuristic score context.
- Saved match records and replay tools.
- Stronger spectating and debugging features.
- Human-vs-bot post-hand review tools.

## Decision Rules

Use these rules to choose the next major step:

- If bot behavior is still making obvious tactical mistakes, keep improving heuristics, but only with targeted fixes.
- If heuristic improvements start requiring more memory, inference, or future-trick planning, move effort toward search support and search prototypes.
- If search and evaluation are both stable, then RL becomes a serious option.
- If a feature does not improve play quality, measurability, debugging, or human learning value, deprioritize it.
