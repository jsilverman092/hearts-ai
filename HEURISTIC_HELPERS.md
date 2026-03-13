# Heuristic Bot Helpers

Reference map for helper methods and module-level helper functions in:
- `src/hearts_ai/bots/heuristic/`
- compatibility entrypoint: `src/hearts_ai/bots/heuristic_bot.py`

Purpose:
- make ownership clear after the Phase 4.6 module split
- provide one place to review naming consistency
- leave a blank `New name` field for any helpers you want to rename later

Notes:
- `Versions` describes which bot versions currently rely on the helper
- `Location` is the current module or class owner
- blank `New name` cells are intentional
- naming convention: use neutral names for shared foundations and reserve `_v` suffixes for genuinely version-owned helper variants

## Package Map

| Module | Role |
| --- | --- |
| `heuristic/bots.py` | Bot classes and class-owned helper methods |
| `heuristic/scoring.py` | Scripted v1 helpers and pass/lead/follow/discard scoring helpers |
| `heuristic/shared.py` | Shared play-loop plumbing (`mode`, moon target, candidate assembly, tie-break) |
| `heuristic/public_info.py` | v3 public-card/void inference helpers |
| `heuristic/rollout.py` | Rollout simulation helpers |
| `heuristic/models.py` | Reason payload dataclasses and shared card constants |
| `heuristic_bot.py` | Compatibility re-export module |

## Class Methods

| Current name | Location | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_peek_last_pass_reason` | `_HeuristicScoringBotBase` (`heuristic/bots.py`) | `v2`, `v3` | Returns cached pass explanation payload. |  |
| `_peek_last_play_reason` | `_HeuristicScoringBotBase` (`heuristic/bots.py`) | `v2`, `v3` | Returns cached play explanation payload. |  |
| `_score_play_candidate` | `_HeuristicScoringBotBase` (`heuristic/bots.py`) | `v2`, `v3` | Dispatches one candidate to lead/follow/discard scoring. |  |
| `_score_follow_candidate` | `_HeuristicScoringBotBase` (`heuristic/bots.py`) | `v2`, `v3` | Shared follow scoring hook (routes to `_score_follow_base`). |  |
| `_score_lead_candidate` | `_HeuristicScoringBotBase` (`heuristic/bots.py`) | `v2`, `v3` | Abstract lead-scoring hook implemented by versioned bots. |  |
| `_score_discard_candidate` | `_HeuristicScoringBotBase` (`heuristic/bots.py`) | `v2`, `v3` | Abstract discard-scoring hook implemented by versioned bots. |  |
| `_score_lead_candidate` | `HeuristicBotV2` (`heuristic/bots.py`) | `v2` | v2 lead hook (`_score_lead_base`). |  |
| `_score_discard_candidate` | `HeuristicBotV2` (`heuristic/bots.py`) | `v2` | v2 discard hook (`_score_discard_base`). |  |
| `_score_lead_candidate` | `HeuristicBotV3` (`heuristic/bots.py`) | `v3` | v3 lead hook (`_score_lead_v3`). |  |
| `_score_discard_candidate` | `HeuristicBotV3` (`heuristic/bots.py`) | `v3` | v3 discard hook (`_score_discard_v3`). |  |

## Scripted v1 Helpers

| Current name | Location | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_choose_lead` | `heuristic/scoring.py` | `v1` | Scripted lead choice for simple heuristic bot. |  |
| `_choose_follow_or_discard` | `heuristic/scoring.py` | `v1` | Scripted branch between follow and discard. |  |
| `_choose_follow` | `heuristic/scoring.py` | `v1` | Scripted follow-suit decision. |  |
| `_low_key` | `heuristic/scoring.py` | shared | Low-card sort key used by scripted helpers. |  |

## Pass Helpers

| Current name | Location | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_score_pass_base` | `heuristic/scoring.py` | `v1`, `v2` | Shared card-only pass priority foundation for v1/v2. |  |
| `_score_pass_v3` | `heuristic/scoring.py` | `v3` | Hand-aware pass priority for v3. |  |

## Shared Play Plumbing

| Current name | Location | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_play_mode` | `heuristic/shared.py` | `v2`, `v3` | Determines lead/follow/discard scoring mode. |  |
| `_moon_defense_target` | `heuristic/shared.py` | `v2`, `v3` | Detects active moon threat target. |  |
| `_choose_play_with_reason` | `heuristic/shared.py` | `v2`, `v3` | Shared scoring play loop and reason payload assembly. |  |
| `_move_tiebreak` | `heuristic/shared.py` | `v2`, `v3` | Deterministic tie-break among equal total scores. |  |

## Lead, Follow, Discard Scoring

| Current name | Location | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_score_lead_base` | `heuristic/scoring.py` | `v2`, base of `v3` | Shared lead scoring foundation. |  |
| `_score_lead_v3` | `heuristic/scoring.py` | `v3` | v3 lead refinements over shared lead base. |  |
| `_score_follow_base` | `heuristic/scoring.py` | `v2`, `v3` | Shared follow scoring system (with explicit second-seat/later-seat branch). |  |
| `_score_discard_priority_base` | `heuristic/scoring.py` | `v1`, `v2`, tie-break in `v2`/`v3` | Discard priority buckets for scripted shedding, discard base scoring, and non-lead tie-breaks. |  |
| `_score_discard_base` | `heuristic/scoring.py` | `v2`, base of `v3` | Shared discard scoring foundation. |  |
| `_score_discard_v3` | `heuristic/scoring.py` | `v3` | v3 discard refinements over shared discard base. |  |

## v3 Public-Info Helpers

| Current name | Location | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_build_public_info` | `heuristic/public_info.py` | `v3` | Builds shared public-info snapshot for heuristic scoring. |  |
| `_all_public_tricks` | `heuristic/public_info.py` | `v3` | Collects public trick history + current trick. |  |
| `_infer_void_suits_by_player` | `heuristic/public_info.py` | `v3` | Infers player void suits from public play. |  |
| `_outside_rank_counts_for_card` | `heuristic/public_info.py` | `v3` | Counts outside lower/higher unseen ranks for candidate card. |  |
| `_void_count_in_players` | `heuristic/public_info.py` | `v3` | Counts known voids for a suit among target players. |  |

## Rollout Helpers

| Current name | Location | Versions | Description | New name |
| --- | --- | --- | --- | --- |
| `_rollout_score_base` | `heuristic/rollout.py` | `v2`, `v3` | Samples continuation cards for rest-of-trick rollout score. |  |
| `_evaluate_rollout_trick` | `heuristic/rollout.py` | `v2`, `v3` | Scores one fully resolved trick outcome. |  |
| `_skip_rollout_for_follow_candidate` | `heuristic/rollout.py` | `v2`, `v3` | Skips rollout for guaranteed-losing non-point follows. |  |
| `_shared_rollout_sample_seeds` | `heuristic/rollout.py` | `v2`, `v3` | Generates shared sample seeds per decision. |  |
| `_remaining_players_after` | `heuristic/rollout.py` | `v2`, `v3` | Computes remaining players to act in current trick. |  |
| `_sample_unknown_card_for_trick` | `heuristic/rollout.py` | `v2`, `v3` | Samples plausible unknown card for trick completion. |  |
| `_full_deck` | `heuristic/rollout.py` | `v2`, `v3` | Returns full deck tuple used by rollout sampling. |  |
