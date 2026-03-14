We’re starting fresh from the current repo state in `C:\Users\JasonSilverman\Documents\GitHub\hearts-ai`.

Before doing anything, read these files and use them as the source of truth for current status and next-phase direction:
- `ROADMAP.md`
- `AGENTS_V3.md`
- `AGENTS_V3_BENCHMARK_REPORT.md`

Current project state:
- `heuristic` v1, `heuristic_v2`, and `heuristic_v3` all exist
- `heuristic_v3` is now the main handcrafted baseline and should be treated as frozen except for obvious tactical bugs
- heuristic explanation/debug tags and helper docs already exist
- mixed benchmarking is in place and should continue to be used for validation
- we are not moving to RL yet

What I want next:
- move into the next phase: search-support layers and the first search-based bot
- keep the bot deterministic under fixed seeds
- keep explanation/debuggability important
- prefer a clean, maintainable structure over a rushed prototype

Important themes to consider in the plan:
- determinized hidden-information search
- shallow search first, not deep/complex search immediately
- support layers for public inference and card counting
- possible private-memory features that matter strategically, like remembering your own pass
- scenario-style regression testing in addition to aggregate benchmarks
- comparison tooling that will later help explain why search preferred one move over another

Please:
1. inspect the current codebase and docs
2. propose the cleanest implementation plan for:
   - the search-support layer
   - the first search bot
   - how to test and benchmark it
3. write that plan to a new markdown file before implementing anything
4. then stop and wait for approval before coding
