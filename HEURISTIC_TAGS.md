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
- `v3_` tags are overlays specific to `heuristic_v3`.
- Examples are illustrative, not exhaustive. They describe the kind of spot where a tag may appear.
- "Cleaner name" is a suggested future rename for UI/debug readability. It is not implemented yet.
- Pure rules-only constraints are intentionally omitted if they do not emit a tag.

## `scoring.py`: `_score_lead_base`

| Current Tag | Meaning | Example | Cleaner Name |
| --- | --- | --- | --- |
| `lead_non_heart` | Leading a non-heart is preferred over leading hearts. | Hearts are not especially attractive, so a club or diamond lead gets a bonus. | `non_heart_lead` |
| `low_heart_escape_lead` | A low heart can be a good escape lead once hearts are broken. | Hearts are broken and leading `3H` is safer than burning `KS`. | `low_heart_escape` |
| `avoid_high_heart_lead` | A high heart lead is risky. | Hearts are broken, but leading `QH` is more dangerous than leading `4H`. | `high_heart_lead_risk` |
| `avoid_qs_lead` | Do not casually lead `QS`. | You hold `QS` and another spade, so opening `QS` is strongly discouraged. | `dont_lead_qs` |
| `avoid_high_spade_lead` | Do not casually lead `AS` or `KS`. | You can lead `5S` or `KS`; the high spade gets penalized. | `dont_lead_high_spade` |
| `cautious_high_spade_lead` | Broad caution against leading higher spades. | A `JS` or higher spade lead gets a general risk penalty. | `high_spade_lead_risk` |
| `prefer_low_heart_over_high_spade` | If a low heart is available, prefer it over spending a dangerous high spade. | Hearts are broken and you have both `3H` and `KS`; the bot prefers `3H`. | `low_heart_over_high_spade` |
| `first_trick_conservative_lead` | First-trick leads should be especially low/conservative. | On the opening lead, lower cards get a small extra preference. | `first_trick_play_low` |
| `avoid_qs_after_hearts_broken` | Leading `QS` is even worse once hearts are live. | Hearts are already broken, making a `QS` lead especially unattractive. | `dont_lead_qs_after_break` |
| `forced_spade_lead_prefer_low` | If the bot is effectively forced to lead spades, it prefers the lower spade. | The entire legal lead set is spades, so `4S` is preferred over `9S`. | `forced_spade_lead_low` |

## `scoring.py`: `_score_lead_v3` with `public_info.py`

| Current Tag | Meaning | Example | Cleaner Name |
| --- | --- | --- | --- |
| `v3_floor_card_lead_safe` | This lead is a floor card: no lower outside cards remain, so it is relatively safe. | In diamonds, your `7D` is the lowest unseen diamond still outside your hand. | `lead_floor_safe` |
| `v3_boss_card_lead_risk` | This lead is a boss card: no higher outside cards remain, so it risks taking control. | You lead `AD` when no unseen diamond above it exists. | `lead_boss_risk` |
| `v3_trap_card_lead_risk` | This lead is a trap card: only a few higher outside cards remain, but some lower cards do too. | Leading `10D` when only `QD` and `KD` are above it but many lower diamonds remain. | `lead_trap_risk` |
| `v3_lead_owned_suit_control_risk` | You hold all remaining cards in the suit, so leading it guarantees control stays with you. | All unseen clubs are in your hand; any club lead keeps you in charge of the suit. | `lead_owned_suit_risk` |
| `v3_avoid_high_lead_with_voids_ahead` | High leads get worse if players still to act may be void and can discard freely. | A player ahead has shown void in diamonds, so leading a high diamond is more dangerous. | `high_lead_void_risk` |
| `v3_lead_void_amplifies_control_risk` | Existing lead-control risk is amplified because players ahead may be void. | A boss or trap lead becomes even less attractive when one or more opponents can slough. | `voids_raise_lead_risk` |
| `v3_avoid_mid_offsuit_when_qs_live` | Mid/high off-suit leads can win awkward queen-dump tricks while `QS` is still out. | You could lead `10C` or `JS`; the club lead is penalized because it may win a `QS` trick. | `offsuit_win_risk_qs_live` |
| `v3_extra_offsuit_win_risk` | Extra penalty because the off-suit lead is especially high. | `KC` gets an added penalty beyond the generic mid/high off-suit risk. | `high_offsuit_win_risk` |
| `v3_jack_spade_not_high_control` | `JS` is not treated like `QS`, `KS`, or `AS`. | `JS` gets some relief relative to `10C` or `KS` as an opening lead. | `js_not_high_spade` |
| `v3_avoid_short_qs_shape_spade_lead` | With short spade length and `QS`, do not flush spades early unless needed. | You hold `QS`, `7S`, `4S`, plus side suits; a non-spade lead is preferred. | `short_qs_shape_no_spade_lead` |
| `v3_avoid_qs_flush_lead` | Stronger penalty on actually leading `QS` in that short-queen shape. | Same hand as above, but specifically on the `QS` candidate. | `dont_flush_qs` |
| `v3_preserve_spade_protection_shape` | Preserve a fragile `AS`/`KS` protection shape when spades are short. | You hold `AS`, `KS`, `5S`, and no queen; side-suit leads are preferred. | `keep_spade_protection_shape` |
| `v3_avoid_exposing_high_spade_protection` | Avoid spending the actual `AS` or `KS` from that fragile protection shape. | `KS` gets an extra penalty beyond the generic short-shape penalty. | `dont_expose_spade_protection` |

## `scoring.py`: `_score_follow_base`

| Current Tag | Meaning | Example | Cleaner Name |
| --- | --- | --- | --- |
| `prefer_high_losing_follow` | If you can lose safely while following suit, dump the highest such card. | Clubs were led and `9C` loses while `4C` also loses; `9C` is preferred. | `highest_safe_follow` |
| `forced_win_follow` | This play is currently winning the trick if played now. | You must follow suit and every legal card beats the current leader. | `currently_winning_follow` |
| `avoid_point_capture` | Losing a point trick is good. | Hearts are already on the trick and your card loses, so that gets rewarded. | `duck_point_trick` |
| `point_trick_win_penalty` | Winning a point trick is bad. | Hearts or `QS` are already on the trick and your card would take it. | `taking_points_bad` |
| `first_trick_forced_win_shed_high` | On the first trick, if you must win, shed the highest club you can. | First trick starts `2C`, a higher club is already out, and you cannot duck. | `first_trick_win_high` |
| `moon_target_still_wins` | This play still leaves the current moon target winning the trick. | A moon threat is live and your follow card does not overtake them. | `moon_target_still_ahead` |
| `block_moon_target` | This play takes the current trick lead away from the moon target. | A moon threat is live and your follow card now becomes the projected winner. | `currently_block_moon` |

## `scoring.py`: `_score_discard_base`

| Current Tag | Meaning | Example | Cleaner Name |
| --- | --- | --- | --- |
| `discard_priority` | Generic base discard score from the older heuristic ordering. | `QS` or a high heart ranks above a small safe card even before v3 refinements. | `base_discard_risk` |
| `avoid_feeding_moon_target` | Do not dump point cards onto a trick currently being won by the moon target. | A moon target is winning a heart trick and you are deciding whether to slough `QH`. | `dont_feed_moon_target` |

## `scoring.py`: `_score_discard_v3` with `public_info.py`

| Current Tag | Meaning | Example | Cleaner Name |
| --- | --- | --- | --- |
| `v3_preserve_subqueen_spade_while_qs_live` | Keep `2S` through `JS` while `QS` is still unplayed. | You are void in the led suit and can dump `JS` or `QC`; `JS` gets preserved. | `keep_low_spades_qs_live` |
| `v3_qs_dead_subqueen_spade_as_black_suit` | Once `QS` is gone, low spades are treated like ordinary black-suit cards again. | `QS` has already been played, so dumping `7S` is no longer specially discouraged. | `low_spades_normal_after_qs` |
| `v3_qs_dead_reduce_ak_spade_dump_premium` | Once `QS` is gone, `AS` and `KS` lose most of their special dump urgency. | The queen is dead, so `KS` is no longer treated as an emergency unload. | `less_ak_spade_risk_after_qs` |
| `v3_floor_card_keep_safe` | A floor card is usually a useful safe escape card, so keep it. | `3C` is the lowest outside club left and is better kept than dumped. | `keep_floor_card` |
| `v3_boss_card_dump_risk` | A boss card is dangerous control, so it is a strong dump candidate. | `AC` is now the top remaining club and is expensive to keep. | `dump_boss_card` |
| `v3_trap_card_dump_risk` | A trap card is dangerous because only a few higher cards remain. | `QC` may still win ugly tricks but is not a true floor card. | `dump_trap_card` |
| `v3_discard_void_pressure` | Opponent voids make dumping this dangerous control card even more attractive. | Many players are void in clubs, so dumping a boss/trap club gets extra value. | `voids_raise_dump_value` |
| `v3_floor_card_void_keep` | Opponent voids make a floor card even more worth keeping. | Players are void in diamonds, which increases the value of retaining your safest low diamond. | `voids_strengthen_floor` |

## `scoring.py`: `_score_discard_v3` moon-defense overlays

| Current Tag | Meaning | Example | Cleaner Name |
| --- | --- | --- | --- |
| `v3_moon_defense_keep_suit_stopper` | Keep this card because it may stop a moon run later. | A sole moon threat is live and dumping `AC` would give up your likely future club stopper. | `keep_moon_stopper` |
| `v3_moon_defense_no_backup_stopper` | Keep it even more strongly because it is your only stopper in that suit. | You hold `AC` but no other club stopper, so the preservation penalty is stronger. | `only_moon_stopper` |

## Likely Cleanup Candidates

These are still documented because they exist in code now, but they are the most likely cleanup candidates:

- `cautious_high_spade_lead`
- `first_trick_conservative_lead`
- `discard_priority`
- `lead_non_heart`

Reason:
- they are broader and noisier than the newer `heuristic_v3` structural tags
- in some cases they reflect older scoring ideas that have been narrowed or partially superseded
