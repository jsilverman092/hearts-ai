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

## Addendum: 2026-03-13 Heuristic v3 Head-to-Head

Scope:
- seat-rotated head-to-head validation for `heuristic_v3`
- compare against `heuristic_v2` and `heuristic` v1

Method:
- four seat rotations, `300` games each, `1200` total candidate-seat games per matchup
- `heuristic_v3` vs `heuristic_v2` seeds: `5000`, `5300`, `5600`, `5900`
- `heuristic_v3` vs `heuristic` seeds: `7000`, `7300`, `7600`, `7900`

### `heuristic_v3` vs `heuristic_v2` (4 x 300 games, seat-rotated)

Aggregate for the single `heuristic_v3` seat across all `1200` games:
- win rate `0.432`
- avg points `27.031`
- avg rank `2.009`

Aggregate for `heuristic_v2` opponents:
- win rate `0.189`
- avg points `36.598`
- avg rank `2.663`

Conclusion:
- `heuristic_v3` materially outperformed `heuristic_v2` in this comparison.

### `heuristic_v3` vs `heuristic` (4 x 300 games, seat-rotated)

Aggregate for the single `heuristic_v3` seat across all `1200` games:
- win rate `0.488`
- avg points `23.110`
- avg rank `1.782`

Aggregate for `heuristic` opponents:
- win rate `0.171`
- avg points `37.732`
- avg rank `2.739`

Conclusion:
- `heuristic_v3` decisively outperformed `heuristic` v1 in this comparison.

## Addendum: 2026-03-13 Mixed-Field Quick Check

Scope:
- quick seat-rotated mixed-field comparison after `heuristic_v3` updates
- one seat each of `heuristic_v3`, `heuristic_v2`, `heuristic`, and `random`

Method:
- four seat rotations, `200` games each, `800` total games per bot
- benchmark specs:
  - `heuristic_v3,heuristic_v2,heuristic,random`
  - `heuristic_v2,heuristic,random,heuristic_v3`
  - `heuristic,random,heuristic_v3,heuristic_v2`
  - `random,heuristic_v3,heuristic_v2,heuristic`
- seeds: `9000`, `9200`, `9400`, `9600`

Aggregate results:
- `heuristic_v3`: win rate `0.463`, avg points `16.692`, avg rank `1.743`
- `heuristic_v2`: win rate `0.314`, avg points `21.567`, avg rank `2.129`
- `heuristic`: win rate `0.162`, avg points `25.724`, avg rank `2.464`
- `random`: win rate `0.061`, avg points `53.926`, avg rank `3.663`

Conclusion:
- `heuristic_v3` finished clearly ahead in this quick mixed-field check.
- ordering was stable and sensible: `heuristic_v3` first, `heuristic_v2` second, `heuristic` third, `random` last.
- this mixed-field result is consistent with the current head-to-head checks showing `heuristic_v3` materially ahead of both earlier heuristic bots.

## Addendum: 2026-03-14 Final Mixed-Field Recheck

Scope:
- final seat-rotated mixed-field validation after the last `heuristic_v3` follow and lead refinements, including the owned-suit lead veto
- one seat each of `heuristic_v3`, `heuristic_v2`, `heuristic`, and `random`

Method:
- four seat rotations, `200` games each, `800` total games per bot
- benchmark specs:
  - `heuristic_v3,heuristic_v2,heuristic,random`
  - `heuristic_v2,heuristic,random,heuristic_v3`
  - `heuristic,random,heuristic_v3,heuristic_v2`
  - `random,heuristic_v3,heuristic_v2,heuristic`
- seeds: `9000`, `9200`, `9400`, `9600`

Aggregate results:
- `heuristic_v3`: win rate `0.525`, avg points `15.672`, avg rank `1.671`
- `heuristic_v2`: win rate `0.224`, avg points `21.910`, avg rank `2.237`
- `heuristic`: win rate `0.191`, avg points `24.728`, avg rank `2.423`
- `random`: win rate `0.061`, avg points `54.072`, avg rank `3.669`

Conclusion:
- `heuristic_v3` remained clearly first in the mixed field after the final heuristic cleanup pass.
- ordering stayed stable: `heuristic_v3` first, `heuristic_v2` second, `heuristic` third, `random` last.
- compared with the earlier 2026-03-13 mixed-field check, `heuristic_v3` improved further on all three summary metrics.
- compared with the prior 2026-03-14 mixed-field recheck, the owned-suit lead fix improved `heuristic_v3` again on win rate, average points, and average rank.

## Addendum: 2026-03-14 First-Trick Third-Seat Follow Recheck

Scope:
- seat-rotated mixed-field validation after adding the `heuristic_v3` first-trick third-seat zero-point follow overlay
- one seat each of `heuristic_v3`, `heuristic_v2`, `heuristic`, and `random`

Method:
- four seat rotations, `200` games each, `800` total games per bot
- benchmark specs:
  - `heuristic_v3,heuristic_v2,heuristic,random`
  - `heuristic_v2,heuristic,random,heuristic_v3`
  - `heuristic,random,heuristic_v3,heuristic_v2`
  - `random,heuristic_v3,heuristic_v2,heuristic`
- seeds: `9000`, `9200`, `9400`, `9600`

Aggregate results:
- `heuristic_v3`: win rate `0.529`, avg points `15.214`, avg rank `1.660`
- `heuristic_v2`: win rate `0.230`, avg points `21.223`, avg rank `2.213`
- `heuristic`: win rate `0.184`, avg points `24.766`, avg rank `2.440`
- `random`: win rate `0.057`, avg points `54.108`, avg rank `3.687`

Conclusion:
- `heuristic_v3` remained clearly first in the mixed field after the first-trick third-seat follow adjustment.
- compared with the prior 2026-03-14 final mixed-field recheck, `heuristic_v3` improved on all three summary metrics.
- this supports the judgment that the previous first-trick follow logic was too duck-heavy on third seat against weak mixed-field opposition.
