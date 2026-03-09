# Step 8 Benchmark Report (Heuristic v2 vs v1/random)

Date: 2026-03-09  
Scope: Phase 3.5 stabilization validation and Step 8 comparison

## Method

Benchmarks were run via:

```powershell
.\.venv\Scripts\python.exe -m hearts_ai benchmark --seed <N> --games <G> --target-score 50 --bots <spec>
```

Primary comparison used seat-rotated head-to-head runs:
- `heuristic_v2` vs three `heuristic` seats (4 seat positions, 300 games each).
- `heuristic_v2` vs three `random` seats (4 seat positions, 200 games each).
- `heuristic` vs three `random` seats (4 seat positions, 200 games each).

## Baseline Self-Play Snapshots

### All random (300 games, seed 1000)

- P0 win rate `0.268`, avg points `35.157`, avg rank `2.452`
- P1 win rate `0.277`, avg points `33.983`, avg rank `2.427`
- P2 win rate `0.212`, avg points `36.370`, avg rank `2.623`
- P3 win rate `0.243`, avg points `35.323`, avg rank `2.498`

### All heuristic v1 (300 games, seed 1000)

- P0 win rate `0.263`, avg points `34.217`, avg rank `2.468`
- P1 win rate `0.196`, avg points `35.590`, avg rank `2.615`
- P2 win rate `0.309`, avg points `33.153`, avg rank `2.400`
- P3 win rate `0.231`, avg points `34.407`, avg rank `2.517`

### All heuristic v2 (300 games, seed 1000)

- P0 win rate `0.242`, avg points `36.293`, avg rank `2.578`
- P1 win rate `0.300`, avg points `32.810`, avg rank `2.363`
- P2 win rate `0.222`, avg points `35.247`, avg rank `2.567`
- P3 win rate `0.237`, avg points `34.317`, avg rank `2.492`

Note: all-same-policy self-play snapshots are mainly sanity checks. Seat effects and sampling noise make these less informative than mixed-policy head-to-head.

## Head-to-Head Results

### `heuristic_v2` vs `heuristic` (4 x 300 games, seat-rotated)

Aggregate for the single `heuristic_v2` seat across all 1200 games:
- Win rate: `0.291`
- Avg points: `31.719`
- Avg rank: `2.342`

Aggregate for `heuristic` opponents (combined across 12 seat-runs):
- Win rate: `0.236`
- Avg points: `35.490`
- Avg rank: `2.552`

Conclusion: `heuristic_v2` outperformed `heuristic` in this Step 8 comparison.

### `heuristic_v2` vs `random` (4 x 200 games, seat-rotated)

Aggregate for `heuristic_v2`:
- Win rate: `0.806`
- Avg points: `11.420`
- Avg rank: `1.240`

### `heuristic` vs `random` (4 x 200 games, seat-rotated)

Aggregate for `heuristic`:
- Win rate: `0.788`
- Avg points: `11.653`
- Avg rank: `1.252`

Conclusion: both heuristic bots crush random; v2 has a modest edge over v1 in this setup.

## What We Learned

- Phase 3.5 adjustments appear to have removed the most obvious tactical failures while preserving strength.
- `heuristic_v2` is now a credible upgraded baseline over `heuristic v1` in direct comparison.
- Remaining gaps versus strong human play are expected and do not block moving past Step 8.

## Recommended Decision

Mark Step 8 complete and treat `heuristic_v2` as the current baseline for next-phase bot work.
