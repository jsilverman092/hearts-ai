# Heuristic Bot Tag Glossary

This file documents the debug tags currently emitted by the heuristic bots.

## Package Map

- `src/hearts_ai/bots/heuristic/scoring.py`: all current tags are emitted here.
- `src/hearts_ai/bots/heuristic/public_info.py`: builds the public-card / void snapshot used by several `heuristic_v3` tags, but emits no tags directly.
- `src/hearts_ai/bots/heuristic/shared.py`: assembles `PlayDecisionReason` payloads, but emits no tags directly.
- `src/hearts_ai/bots/heuristic/rollout.py`: contributes `rollout_score`, not tags.
- `src/hearts_ai/bots/heuristic/models.py`: defines the reason payload types that carry tags to the UI/debug layer.

## Notes

- Tags are grouped by scoring-helper ownership, which matches the current heuristic package structure.
- `Applies to` indicates which bot versions can emit the tags in that section.
- `v3_` tags are overlays specific to `heuristic_v3`.
- The `Impact` column shows the direct additive base-score effect attached to the tag in current code.
- Final play choice also includes `rollout_score` and deterministic tie-breaks, so `Impact` is not the entire decision.
- Some scoring helpers also have untagged terms; those are listed under the relevant section when useful.
- In impact formulas, `rank` means `int(card.rank)`, using `2-14` for `2` through `A` (`J=11`, `Q=12`, `K=13`, `A=14`).
- Pass decisions currently expose score tuples, not tags.
- Examples are illustrative, not exhaustive. They describe the kind of spot where a tag may appear.
- "Cleaner name" is a suggested future rename for UI/debug readability. It is not implemented yet.

## `scoring.py`: `_score_lead_base`

Applies to: `heuristic_v2`, `heuristic_v3`

Untagged terms in this helper:
- legal heart lead before hearts are broken: `-2.5`
- legal heart lead after hearts are broken baseline: `-0.5`
- all lead candidates: `-rank * 0.12`

| Current Tag | Meaning | Impact | Example | Cleaner Name |
| --- | --- | --- | --- | --- |
| `lead_non_heart` | Leading a non-heart is preferred over leading hearts. | `+2.0` | Hearts are not especially attractive, so a club or diamond lead gets a bonus. | `non_heart_lead` |
| `low_heart_escape_lead` | A low heart can be a good escape lead once hearts are broken. | `+1.9` | Hearts are broken and leading `3H` is safer than burning `KS`. | `low_heart_escape` |
| `avoid_high_heart_lead` | A high heart lead is risky. | `-0.9` | Hearts are broken, but leading `QH` is more dangerous than leading `4H`. | `high_heart_lead_risk` |
| `avoid_qs_lead` | Do not casually lead `QS`. | `-4.0` with a lower legal spade available, else `-2.2` | You hold `QS` and another spade, so opening `QS` is strongly discouraged. | `dont_lead_qs` |
| `avoid_high_spade_lead` | Do not casually lead `AS` or `KS`. | `-2.6` with a lower legal spade available, else `-1.4` | You can lead `5S` or `KS`; the high spade gets penalized. | `dont_lead_high_spade` |
| `prefer_low_heart_over_high_spade` | If a low heart is available, prefer it over spending a dangerous high spade. | `-1.6` | Hearts are broken and you have both `3H` and `KS`; the bot prefers `3H`. | `low_heart_over_high_spade` |
| `avoid_qs_after_hearts_broken` | Leading `QS` is even worse once hearts are live. | `-0.5` | Hearts are already broken, making a `QS` lead especially unattractive. | `dont_lead_qs_after_break` |
| `forced_spade_lead_prefer_low` | If the bot is effectively forced to lead spades, it prefers the lower spade. | `-rank * 0.04` | The entire legal lead set is spades, so `4S` is preferred over `9S`. | `forced_spade_lead_low` |

## `scoring.py`: `_score_lead_v3` with `public_info.py`

Applies to: `heuristic_v3`

This helper adds only tagged overlay terms. It relies on `public_info.py` for `qs_live`, void counts, and floor / trap / boss card classification.

| Current Tag | Meaning | Impact | Example | Cleaner Name |
| --- | --- | --- | --- | --- |
| `v3_floor_card_lead_safe` | This lead is a floor card: no lower outside cards remain, so it is relatively safe. | `+0.45` | In diamonds, your `7D` is the lowest unseen diamond still outside your hand. | `lead_floor_safe` |
| `v3_boss_card_lead_risk` | This lead is a boss card: no higher outside cards remain, so it risks taking control. | `-0.78` | You lead `AD` when no unseen diamond above it exists. | `lead_boss_risk` |
| `v3_trap_card_lead_risk` | This lead is a trap card: only a few higher outside cards remain, but some lower cards do too. | `-(0.5 + 0.2 * (2 - outside_higher_count))` | Leading `10D` when only `QD` and `KD` are above it but many lower diamonds remain. | `lead_trap_risk` |
| `v3_lead_owned_suit_control_risk` | You hold all remaining cards in the suit, so leading it guarantees control stays with you. | `-0.9` | All unseen clubs are in your hand; any club lead keeps you in charge of the suit. | `lead_owned_suit_risk` |
| `v3_avoid_high_lead_with_voids_ahead` | High leads get worse if players still to act may be void and can discard freely. | `-0.22 * voids_ahead` | A player ahead has shown void in diamonds, so leading a high diamond is more dangerous. | `high_lead_void_risk` |
| `v3_lead_void_amplifies_control_risk` | Existing lead-control risk is amplified because players ahead may be void. | `-0.14 * voids_ahead` | A boss or trap lead becomes even less attractive when one or more opponents can slough. | `voids_raise_lead_risk` |
| `v3_avoid_mid_offsuit_when_qs_live` | Mid/high off-suit leads can win awkward queen-dump tricks while `QS` is still out. | `-0.35` | You could lead `10C` or `JS`; the club lead is penalized because it may win a `QS` trick. | `offsuit_win_risk_qs_live` |
| `v3_extra_offsuit_win_risk` | Extra penalty because the off-suit lead is especially high. | `-0.15` | `KC` gets an added penalty beyond the generic mid/high off-suit risk. | `high_offsuit_win_risk` |
| `v3_avoid_short_qs_shape_spade_lead` | With short spade length and `QS`, do not flush spades early unless needed. | `-2.1` | You hold `QS`, `7S`, `4S`, plus side suits; a non-spade lead is preferred. | `short_qs_shape_no_spade_lead` |
| `v3_avoid_qs_flush_lead` | Stronger penalty on actually leading `QS` in that short-queen shape. | extra `-1.4` | Same hand as above, but specifically on the `QS` candidate. | `dont_flush_qs` |
| `v3_preserve_spade_protection_shape` | Preserve a fragile `AS`/`KS` protection shape when spades are short. | `-1.5` | You hold `AS`, `KS`, `5S`, and no queen; side-suit leads are preferred. | `keep_spade_protection_shape` |
| `v3_avoid_exposing_high_spade_protection` | Avoid spending the actual `AS` or `KS` from that fragile protection shape. | extra `-1.3` | `KS` gets an extra penalty beyond the generic short-shape penalty. | `dont_expose_spade_protection` |

## `scoring.py`: `_score_follow_base`

Applies to: `heuristic_v2`, `heuristic_v3`

Second-seat and later-seat branches are explicit in code, but currently use the same weights.

| Current Tag | Meaning | Impact | Example | Cleaner Name |
| --- | --- | --- | --- | --- |
| `prefer_high_losing_follow` | If you can lose safely while following suit, dump the highest such card. | `+3.0 + rank * 0.08` | Clubs were led and `9C` loses while `4C` also loses; `9C` is preferred. | `highest_safe_follow` |
| `forced_win_follow` | This play is currently winning the trick if played now. | `-2.0` | You must follow suit and every legal card beats the current leader. | `currently_winning_follow` |
| `avoid_point_capture` | Losing a point trick is good. | `+1.2` | Hearts are already on the trick and your card loses, so that gets rewarded. | `duck_point_trick` |
| `point_trick_win_penalty` | Winning a point trick is bad. | `-7.5` | Hearts or `QS` are already on the trick and your card would take it. | `taking_points_bad` |
| `first_trick_forced_win_shed_high` | On the first trick, if you must win, shed the highest club you can. | `+rank * 0.22` | First trick starts `2C`, a higher club is already out, and you cannot duck. | `first_trick_win_high` |
| `moon_target_still_wins` | This play still leaves the current moon target winning the trick. | `-5.0` | A moon threat is live and your follow card does not overtake them. | `moon_target_still_ahead` |
| `block_moon_target` | This play takes the current trick lead away from the moon target. | `+2.4` | A moon threat is live and your follow card now becomes the projected winner. | `currently_block_moon` |

## `scoring.py`: `_score_discard_base`

Applies to: `heuristic_v2`, `heuristic_v3`

Priority buckets from `_score_discard_priority_base`:
- `QS = 6`
- `AS = 5`
- `KS = 4`
- any heart = `3`
- clubs / diamonds = `2`
- sub-queen spades = `1`

| Current Tag | Meaning | Impact | Example | Cleaner Name |
| --- | --- | --- | --- | --- |
| `discard_priority` | Generic base discard score from the older heuristic ordering. | `+1.8 * priority_bucket + 0.04 * rank` | `QS` or a high heart ranks above a small safe card even before v3 refinements. | `base_discard_risk` |
| `avoid_feeding_moon_target` | Do not dump point cards onto a trick currently being won by the moon target. | `-4.5` | A moon target is winning a heart trick and you are deciding whether to slough `QH`. | `dont_feed_moon_target` |

## `scoring.py`: `_score_discard_v3` with `public_info.py`

Applies to: `heuristic_v3`

This helper relies on `public_info.py` for `qs_live`, floor / trap / boss classification, and opponent void counts.

| Current Tag | Meaning | Impact | Example | Cleaner Name |
| --- | --- | --- | --- | --- |
| `v3_preserve_subqueen_spade_while_qs_live` | Keep `2S` through `JS` while `QS` is still unplayed. | `-1.8` | You are void in the led suit and can dump `JS` or `QC`; `JS` gets preserved. | `keep_low_spades_qs_live` |
| `v3_qs_dead_subqueen_spade_as_black_suit` | Once `QS` is gone, low spades are treated like ordinary black-suit cards again. | `+1.8` | `QS` has already been played, so dumping `7S` is no longer specially discouraged. | `low_spades_normal_after_qs` |
| `v3_qs_dead_reduce_ak_spade_dump_premium` | Once `QS` is gone, `AS` and `KS` lose most of their special dump urgency. | `-1.8 * max(priority_bucket - 2, 0)` | The queen is dead, so `KS` is no longer treated as an emergency unload. | `less_ak_spade_risk_after_qs` |
| `v3_floor_card_keep_safe` | A floor card is usually a useful safe escape card, so keep it. | `-0.75` | `3C` is the lowest outside club left and is better kept than dumped. | `keep_floor_card` |
| `v3_boss_card_dump_risk` | A boss card is dangerous control, so it is a strong dump candidate. | `+0.85` | `AC` is now the top remaining club and is expensive to keep. | `dump_boss_card` |
| `v3_trap_card_dump_risk` | A trap card is dangerous because only a few higher cards remain. | `+(0.55 + 0.2 * (2 - outside_higher_count))` | `QC` may still win ugly tricks but is not a true floor card. | `dump_trap_card` |
| `v3_discard_void_pressure` | Opponent voids make dumping this dangerous control card even more attractive. | `+0.3 + 0.12 * (voids_in_opponents - 2)` | Many players are void in clubs, so dumping a boss/trap club gets extra value. | `voids_raise_dump_value` |
| `v3_floor_card_void_keep` | Opponent voids make a floor card even more worth keeping. | `-0.2` | Players are void in diamonds, which increases the value of retaining your safest low diamond. | `voids_strengthen_floor` |

## `scoring.py`: `_score_discard_v3` moon-defense overlays

Applies to: `heuristic_v3`

These penalties can stack with the base `v3` discard overlays above.

| Current Tag | Meaning | Impact | Example | Cleaner Name |
| --- | --- | --- | --- | --- |
| `v3_moon_defense_keep_suit_stopper` | Keep this card because it may stop a moon run later. | base `-3.0`, plus `-1.0` if `outside_count >= 8`, plus `-0.6` if the card is a boss stopper | A sole moon threat is live and dumping `AC` would give up your likely future club stopper. | `keep_moon_stopper` |
| `v3_moon_defense_no_backup_stopper` | Keep it even more strongly because it is your only stopper in that suit. | extra `-1.6` | You hold `AC` but no other club stopper, so the preservation penalty is stronger. | `only_moon_stopper` |

## `shared.py`: play-selection tie-breaks

Applies to: `heuristic_v2`, `heuristic_v3`

These are only used when two candidates have the same `total_score` after base scoring plus weighted rollout.

- Lead mode:
  - prefer lower rank first
  - if still tied, prefer lower suit enum (`CLUBS=0`, `DIAMONDS=1`, `HEARTS=2`, `SPADES=3`)
- Follow / discard mode:
  - prefer higher `_score_discard_priority_base` bucket first
  - if still tied, prefer higher rank
  - if still tied, prefer higher suit enum

Notes:
- These tie-breaks come from `_move_tiebreak()` in `src/hearts_ai/bots/heuristic/shared.py`.
- Pass decisions do not use this tie-break helper; they are ordered directly by their pass-score tuples.

## Pass debug tuples

Pass decisions do not emit string tags. Instead, the debug UI shows each candidate card with its pass-score tuple.

General rule:
- pass tuples are sorted descending
- first number is the dominant priority
- second number breaks ties by rank
- third number breaks ties by suit enum (`CLUBS=0`, `DIAMONDS=1`, `HEARTS=2`, `SPADES=3`)

### `scoring.py`: `_score_pass_base`

Applies to: `heuristic`, `heuristic_v2`

Tuple shape:
- `(priority_bucket, rank, suit)`

Priority buckets:
- `QS = 6`
- `AS = 5`
- `KS = 4`
- any heart = `3`
- clubs / diamonds = `2`
- sub-queen spades = `1`

Example:
- `QS` -> `(6, 12, 3)`
- `KH` -> `(3, 13, 2)`
- `TD` -> `(2, 10, 1)`

### `scoring.py`: `_score_pass_v3`

Applies to: `heuristic_v3`

Tuple shape:
- `(primary, rank, suit)`

Notes:
- `primary` is a hand-aware score, not a fixed bucket.
- it depends on context such as total spade length, whether `QS` is present, low-spade cover, suit length, and card category.
- the same card can therefore receive different first-number values in different hands.

Example interpretation:
- if two cards have tuples `(720, 14, 3)` and `(690, 13, 3)`, the first is passed first because `720 > 690`
- if two cards tie on the first number, the higher rank wins
- if both first and second numbers tie, the higher suit enum wins

Hand-aware scoring factors:

| Card Category | Base `primary` | Conditional Adjustments | Notes |
| --- | --- | --- | --- |
| `QS` | `980` if `spade_count <= 3`; `920` if `spade_count == 4`; `350` if `spade_count == 5`; `260` otherwise | `-40` if `low_spade_cover >= 3` | Short-spade `QS` shapes are treated as urgent passes; long-spade `QS` shapes are less urgent. |
| `AS` | `720` | `-220` if `spade_count >= 5`; `-140` if `not has_qs and spade_count >= 3`; `-70` if `low_spade_cover >= 3`; if both `AS` and `KS` are present: `+30` if `low_spade_cover < 3`, else `-30`; `+70` if `lower_cover_for_card == 0`, else `-60` if `lower_cover_for_card >= 2` | Starts as a high-priority pass, then gets discounted when the hand has enough spade shape/protection to justify keeping it. |
| `KS` | `690` | `-220` if `spade_count >= 5`; `-140` if `not has_qs and spade_count >= 3`; `-70` if `low_spade_cover >= 3`; if both `AS` and `KS` are present: `+80` if `low_spade_cover < 3`, else `-30`; `+70` if `lower_cover_for_card == 0`, else `-60` if `lower_cover_for_card >= 2` | Similar to `AS`, but with a slightly lower base and a larger paired `AS+KS` penalty/boost swing. |
| sub-queen spade (`2S-JS`) | `-220 + rank` | `+80` if `spade_count >= 7`; `+50` if `spade_count >= 6` | These are intentionally preserved in most hands; even long-spade adjustments usually leave them far below normal pass candidates. |
| heart `2H-4H` | `70 + 2 * rank` | `-30` if `suit_count >= 5 and rank <= 6`; `+30` if `suit_count <= 2 and rank >= 10` | Very low hearts are usually kept. |
| `5H` | `220` | `-30` if `suit_count >= 5`; `+30` if `suit_count <= 2` does not apply here because rank is below `10` | Transitional heart risk. |
| `6H` | `320` | `-30` if `suit_count >= 5`; `+30` if `suit_count <= 2` does not apply here because rank is below `10` | Slightly more passable than `5H`. |
| heart `7H-AH` | `460 + 40 * (rank - 7)` | `+30` if `suit_count <= 2 and rank >= 10` | High hearts climb quickly in pass priority, especially in short suits. |
| club `2C-4C` | `60` | `-30` if `suit_count >= 5 and rank <= 5`; `+45` if `rank >= 11 and suit_count <= 2` does not apply here | Very low clubs are usually kept. |
| `5C` | `180` | `-30` if `suit_count >= 5`; no short-suit honor bonus | Transitional club risk. |
| club `6C-9C` | `250 + 25 * (rank - 6)` | no long-suit low-card discount; no short-suit honor bonus | Mid clubs ramp gradually. |
| club `JC-AC` | `520 + 45 * (rank - 11)` | `+45` if `suit_count <= 2` | High clubs in short suits become strong pass candidates. |
| diamond `2D-3D` | `55` | `-30` if `suit_count >= 5 and rank <= 5`; `+45` if `rank >= 11 and suit_count <= 2` does not apply here | Very low diamonds are usually kept. |
| `4D` | `175` | `-30` if `suit_count >= 5 and rank <= 5` | Transitional diamond risk. |
| diamond `5D-9D` | `245 + 24 * (rank - 5)` | `-30` if `suit_count >= 5 and rank <= 5` only applies at `5D`; no short-suit honor bonus | Mid diamonds ramp gradually. |
| diamond `JD-AD` | `515 + 45 * (rank - 11)` | `+45` if `suit_count <= 2` | High diamonds in short suits become strong pass candidates. |

Definitions:
- `spade_count`: total spades in hand.
- `has_qs`, `has_ks`, `has_as`: whether the hand contains those specific spades.
- `low_spade_cover`: number of spades in hand with rank `<= 9`.
- `suit_count`: number of cards in the candidate card's suit.
- `lower_cover_for_card`: number of same-suit spades in hand below the candidate spade.

## Likely Cleanup Candidates

These are still documented because they exist in code now, but they are the most likely cleanup candidates:

- `discard_priority`
- `lead_non_heart`

Reason:
- they are broader and noisier than the newer `heuristic_v3` structural tags
- in some cases they reflect older scoring ideas that have been narrowed or partially superseded
