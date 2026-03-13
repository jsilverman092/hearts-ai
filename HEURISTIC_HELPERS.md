# Heuristic Bot Helpers

Reference file for helper methods and module-level helper functions in
`src/hearts_ai/bots/heuristic_bot.py`.

Purpose:
- make ownership clearer while the heuristic bots are being refactored
- provide a single place to review naming consistency
- leave a blank `New name` field for any helpers that should be renamed later

Notes:
- `Versions` describes which bot versions currently rely on the helper
- `Scope` distinguishes class methods from module-level helpers
- blank `New name` cells are intentional

## Base Class Helper Methods

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_peek_last_pass_reason` | `_HeuristicScoringBotBase` method | `v2`, `v3` | Returns the cached pass explanation payload for debug/UI use. |  |
| `_peek_last_play_reason` | `_HeuristicScoringBotBase` method | `v2`, `v3` | Returns the cached play explanation payload for debug/UI use. |  |
| `_score_lead_candidate` | `_HeuristicScoringBotBase` method | `v2`, `v3` | Abstract lead-scoring hook implemented by each bot version. |  |
| `_score_play_candidate` | `_HeuristicScoringBotBase` method | `v2`, `v3` | Dispatches one candidate into the lead/follow/discard scoring path. |  |
| `_score_follow_candidate` | `_HeuristicScoringBotBase` method | `v2`, `v3` | Shared follow-scoring hook that currently routes to `v2` follow logic. |  |
| `_score_discard_candidate` | `_HeuristicScoringBotBase` method | `v2`, `v3` | Abstract discard-scoring hook implemented by each bot version. |  |

## Version-Specific Class Helper Methods

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_score_lead_candidate` | `HeuristicBotV2` method | `v2` | `v2` lead hook that routes to the `v2` lead scoring function. |  |
| `_score_discard_candidate` | `HeuristicBotV2` method | `v2` | `v2` discard hook that routes to the `v2` discard scoring function. |  |
| `_score_lead_candidate` | `HeuristicBotV3` method | `v3` | `v3` lead hook that routes to the richer public-info lead scoring function. |  |
| `_score_discard_candidate` | `HeuristicBotV3` method | `v3` | `v3` discard hook that routes to the richer public-info discard scoring function. |  |

## Scripted v1 Helper Mechanics

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_choose_lead` | module-level | `v1` | Picks the scripted lead for the simple heuristic bot. |  |
| `_choose_follow_or_discard` | module-level | `v1` | Chooses whether the scripted bot should follow suit or discard. |  |
| `_choose_follow` | module-level | `v1` | Picks the scripted follow-suit play for the simple heuristic bot. |  |
| `_low_key` | module-level | shared | Low-card sort key used by the scripted bot and some tie logic. |  |

## Pass Scoring Helpers

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_pass_priority` | module-level | `v1`, `v2` | Simple card-only pass ranking used by the legacy heuristic pass logic. |  |
| `_pass_priority_v3` | module-level | `v3` | Hand-aware pass ranking used by the `v3` pass logic. |  |

## Shared Play-Selection Plumbing

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_play_mode` | module-level | `v2`, `v3` | Determines whether a legal move is being scored as lead, follow, or discard. |  |
| `_moon_defense_target` | module-level | `v2`, `v3` | Detects whether one opponent currently looks like a live moon threat. |  |
| `_choose_play_with_reason` | module-level | `v2`, `v3` | Shared play loop that scores candidates, applies rollout, orders them, and builds the reason payload. |  |
| `_move_tiebreak` | module-level | `v2`, `v3` | Provides deterministic tie-breaking when candidate totals match. |  |
| `_full_deck` | module-level | `v2`, `v3` | Returns the cached full deck tuple for rollout sampling. |  |

## Lead Scoring Helpers

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_score_lead_v2` | module-level | `v2`, base of `v3` | Core lead heuristic used directly by `v2` and as the starting point for `v3`. |  |
| `_score_lead_v3` | module-level | `v3` | Extends `v2` lead scoring with public card tracking and spade-shape refinements. |  |

## Discard Scoring Helpers

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_score_discard_priority_v2` | module-level | `v1`, `v2`, tie-breaks in `v2`/`v3` | Legacy discard-priority buckets used for scripted shedding, `v2` discard base scoring, and non-lead tie-break ordering. |  |
| `_score_discard_v2` | module-level | `v2`, base of `v3` | Core discard heuristic used directly by `v2` and as the starting point for `v3`. |  |
| `_score_discard_v3` | module-level | `v3` | Extends `v2` discard scoring with public card tracking and moon-defense stopper logic. |  |

## Follow Scoring Helpers

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_score_follow_v2` | module-level | `v2`, `v3` | Shared follow-suit heuristic for both scoring-based heuristic bots. |  |

## v3 Public-Info Helpers

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_build_public_info_v3` | module-level | `v3` | Builds the public-info snapshot used by `v3` lead/discard scoring. |  |
| `_all_public_tricks` | module-level | `v3` | Collects completed public tricks plus the current trick-in-progress. |  |
| `_infer_void_suits_by_player` | module-level | `v3` | Infers player voids from past public trick play. |  |
| `_outside_rank_counts_for_card` | module-level | `v3` | Counts lower and higher unseen outside cards for a candidate card. |  |
| `_void_count_in_players` | module-level | `v3` | Counts how many specified players are publicly known to be void in a suit. |  |

## Rollout Helpers

| Current name | Scope | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_rollout_score_v2` | module-level | `v2`, `v3` | Samples completions of the current trick to adjust candidate scores. |  |
| `_evaluate_rollout_trick` | module-level | `v2`, `v3` | Scores one fully specified trick outcome for rollout purposes. |  |
| `_skip_rollout_for_follow_candidate` | module-level | `v2`, `v3` | Skips rollout in guaranteed-losing follow spots where rollout adds only noise. |  |
| `_shared_rollout_sample_seeds` | module-level | `v2`, `v3` | Generates shared sample seeds so candidates see the same sampled futures. |  |
| `_remaining_players_after` | module-level | `v2`, `v3` | Computes which players still need to act in the current trick. |  |
| `_sample_unknown_card_for_trick` | module-level | `v2`, `v3` | Samples one plausible unknown card for the remainder of a rollout trick. |  |
