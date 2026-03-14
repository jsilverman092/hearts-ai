# Hearts AI Literature Notes

## Purpose

This file captures the most relevant high-level takeaways from the limited public Hearts-AI literature reviewed so far.

It is not meant to be a full academic survey.
It is meant to answer:
- what prior work suggests about building a strong Hearts bot
- what ideas are worth borrowing next
- what ideas are probably premature for this project right now

## Bottom Line

The literature points in one clear direction:

- strong Hearts play is not just a heuristic problem
- it is also not a clean "just do AlphaGo" problem
- the practical path is likely:
  - strong handcrafted baseline
  - better inference / memory / hidden-information handling
  - shallow search over determinized worlds
  - possibly learned value/policy components later

That lines up well with the current project direction.

## Paper 1: AlphaHearts Zero (Yale, 2022)

Source:
- <https://csec.yale.edu/senior-essays/spring-2022/alphahearts-zero-implementing-alphazero-techniques-imperfect-information>

Simple summary:
- AlphaZero-style methods work well in perfect-information games.
- Hearts is harder because hidden cards mean the bot does not know the true game state.
- This project used:
  - PIMC (Perfect Information Monte Carlo)
  - MCTS
  - a DQN trained by self-play RL
- The reported result was roughly human-level play, ahead of baseline agents, and approaching "cheating" agents.

Main takeaway:
- A direct AlphaZero port is not the right mental model for Hearts.
- Hidden-information handling needs to be explicit.
- Search and learning can help, but only after the information problem is addressed.

What matters for this repo:
- The current plan to move from heuristic baseline -> search support -> search bot is well supported.
- Better hidden-hand inference is likely to matter a lot.

## Paper 2: A Monte-Carlo Hearts Engine (Princeton, 2025)

Source:
- <https://theses-dissertations.princeton.edu/entities/publication/f605fb05-be3c-412d-8a28-c100ce37111c>

Simple summary:
- Hearts is difficult because it combines:
  - hidden information
  - randomness
  - 4 players
  - non-zero-sum scoring
  - sequential decision-making
- Standard MCTS is not enough on its own.
- The project adapted search ideas for multiplayer imperfect-information Hearts, including maxn and Monte Carlo sampling.
- The reported result was a bot that beat baseline agents, prior Hearts engines, and advanced human players.

Main takeaway:
- Multiplayer / non-zero-sum structure is not a minor detail. It changes the search problem.
- Hearts is not just a smaller Go-like game with hidden cards.

What matters for this repo:
- Search is the right next major step.
- The search bot should not be framed too narrowly as two-player minimax logic.
- Evaluation against mixed opponents remains important.

## Paper 3: Valet (arXiv, 2026)

Source:
- <https://arxiv.org/abs/2603.03252>

Simple summary:
- Imperfect-information card-game AI is hard to compare fairly.
- Valet proposes a standardized testbed across many traditional imperfect-information card games, including Hearts.
- The point is not just to produce another bot, but to make comparisons more credible and repeatable.

Main takeaway:
- Benchmarking quality is part of the research problem.
- Seat order, variance, and game-specific quirks can make bad evaluations look convincing if the setup is weak.

What matters for this repo:
- Mixed-field benchmarks were worthwhile.
- Scenario/regression suites are worth adding as a complement to aggregate benchmark numbers.
- Later search / RL work should be judged with real evaluation discipline.

## Cross-Paper Synthesis

Across the reviewed literature, the most consistent themes are:

1. Hearts is a hybrid difficulty problem.
- hidden information
- randomness
- multiplayer interactions
- non-zero-sum scoring
- long-horizon lead / tempo management

2. Strong Hearts bots appear to be hybrid systems.
- determinization or hidden-information sampling
- search
- inference
- sometimes learned evaluation

3. Better inference is repeatedly important.
- not just legality
- not just public void tracking
- but also suit exhaustion, likely suit shape, and other card-distribution reasoning

4. Evaluation matters almost as much as the policy itself.
- weak benchmark setups can easily hide regressions or overstate improvements

## What We Should Borrow

These are the ideas that look most worth borrowing into the next phase of this repo.

### 1. Determinized hidden-information search

Why:
- This is the clearest bridge from the current heuristic bot to a stronger bot class.
- It fits Hearts better than a direct AlphaZero-style jump.

Practical version for this repo:
- sample plausible unseen-card worlds
- evaluate candidate moves across those worlds
- keep it shallow first

### 2. Public inference + counting support layer

Why:
- The papers and our own heuristic work both point to this as a major source of strength.

Practical version for this repo:
- suit exhaustion by counting
- stronger void inference
- likely suit-length / pressure inference where justified
- clean reusable APIs for search and debug tooling

### 3. Limited private-memory features

Why:
- Hearts strategy can materially depend on what you personally know from the pass.

Practical version for this repo:
- remember your own pass
- remember known passed dangers like `QS`
- keep this separate from public inference

### 4. Stronger evaluation discipline

Why:
- The literature supports what we already observed: benchmark quality matters.

Practical version for this repo:
- keep mixed-field benchmark rotation
- add curated scenario/regression tests
- compare search against `heuristic_v3`, not just against weak bots

### 5. Explanation tooling as a first-class support layer

Why:
- Search and learning methods are harder to debug than heuristics.

Practical version for this repo:
- preserve reason payloads
- support "why this move over that move?"
- support search-vs-heuristic comparison views later

## What We Should Ignore For Now

These ideas may matter later, but they are not the right next move for this project.

### 1. Jumping straight to RL

Why not now:
- the literature does not suggest this is the easiest or cleanest first path
- evaluation and search support are not the bottlenecks yet

### 2. Large model complexity

Why not now:
- Hearts-specific public literature is small
- the immediate gains likely come from better inference and shallow search, not giant model design

### 3. Blindly copying AlphaZero structure

Why not now:
- Hearts is imperfect-information and multiplayer
- the clean AlphaZero recipe does not map directly

### 4. Endless heuristic weight tuning

Why not now:
- `heuristic_v3` is already a strong handcrafted baseline
- remaining important gaps are increasingly about memory, inference, and future-trick planning

### 5. Fancy opponent modeling without evidence

Why not now:
- there is value in inference, but speculative psychological modeling is easy to overfit
- better to start with card-counting, void inference, and pass-memory facts

## Implications For Current Project State

The work already done in this repo was worthwhile because it established:

- a strong handcrafted baseline (`heuristic_v3`)
- benchmarking and comparison discipline
- explanation/debug vocabulary
- a clearer picture of what heuristics still cannot do well

The remaining gaps now look less like "find better weights" and more like:

- pass memory
- better public/private inference
- future-trick planning
- multiplayer hidden-information search

That is a strong signal that the next phase should be search-oriented, not more heuristic tuning.

## Recommended Next Step

Do next:
- plan and build the search-support layer
- then build the first shallow search bot

Do not do next:
- broad `heuristic_v4` retuning
- RL experiments
- deep search immediately

## Notes On DeepResearch

Would a dedicated DeepResearch pass be worthwhile?

Short answer:
- not necessary for the immediate next step
- potentially worthwhile later for broader method research

Why not necessary now:
- the Hearts-specific literature signal already points in a clear direction
- the next bottleneck is implementation, not lack of papers

Why it could be useful later:
- not for Hearts papers alone
- but for related topics such as:
  - ISMCTS
  - PIMC pitfalls
  - multiplayer search methods
  - trick-taking AI
  - imperfect-information evaluation methodology

## References

1. Yale CSEC senior essay: "AlphaHearts Zero: Implementing AlphaZero Techniques in an Imperfect Information Card Game"
   - <https://csec.yale.edu/senior-essays/spring-2022/alphahearts-zero-implementing-alphazero-techniques-imperfect-information>

2. Princeton thesis: "A Monte-Carlo Hearts Engine"
   - <https://theses-dissertations.princeton.edu/entities/publication/f605fb05-be3c-412d-8a28-c100ce37111c>

3. arXiv: "Valet: A Standardized Testbed of Traditional Imperfect-Information Card Games"
   - <https://arxiv.org/abs/2603.03252>
