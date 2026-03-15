# Bot Debug Guide

This is a practical guide to the current `Bot Debug` panel in the Hearts UI.

It focuses mainly on the `search_v1` explanation payload, because that is the most detailed and easiest to misread at first glance.

## Two Different Debug Feeds

There are two separate things the UI can show:

### 1. `Show latest bot explanation`

This shows the last real decision made by a bot at the table.

Use this when you want to understand:
- what a bot actually just did
- why an opponent bot made a strange move
- what happened on the previous turn

### 2. `Show my recommendation`

This shows an advisory recommendation for your own seat.

It does **not** play the move for you. It is just a suggestion/explanation generated for the current state.

Use this when you want to understand:
- what the selected advisory bot thinks you should do
- why the advisory bot prefers one move over another

## The First Two Lines

Typical header:

```text
Seat P2 (search_v1)
Kind play  Hand 3  Trick 7
```

Meaning:
- `Seat P2`: the explanation is about player 2
- `search_v1`: that bot generated the explanation
- `Kind play`: this is a play decision, not a pass decision
- `Hand 3`: the current hand number
- `Trick 7`: the current trick number

## Search Debug Fields

When the payload comes from `search_v1`, the UI shows several search-specific lines.

### `Mode`

Example:

```text
Mode: follow
```

Meaning:
- `lead`: this move starts the trick
- `follow`: this move follows the led suit
- `discard`: this player could not follow suit and is throwing off-suit

### `Chosen`

Example:

```text
Chosen: 6C
```

This is the card the bot chose.

### `Source`

Example:

```text
Source: search
```

Meaning:
- `search`: normal sampled-world search picked the move
- `heuristic_fallback_impossible_world`: search could not build a valid sampled world and fell back to `heuristic_v3`
- `heuristic_fallback_empty_world_set`: search produced no usable world set and fell back to `heuristic_v3`

If the source is a fallback, treat the explanation as a search-shaped wrapper around a heuristic choice.

### `Worlds`

Example:

```text
Worlds: 1 / 1
```

Meaning:
- first number: how many sampled worlds were actually used
- second number: how many were requested

A sampled world is one legal guess about the hidden opponent hands.

Current default `search_v1` usually runs with:

```text
Worlds: 1 / 1
```

That means the bot is evaluating the move against one guessed hidden deal.

### `Candidates`

Example:

```text
Candidates: 5 eval / 5 legal
```

Meaning:
- `5 legal`: there were 5 legal plays available
- `5 eval`: search actually evaluated all 5

### `Trick context`

Example:

```text
Trick context: size=2 led=H
```

Meaning:
- `size=2`: two cards are already in the trick before this move
- `led=H`: hearts were led

## `Chosen eval`

Example:

```text
Chosen eval: delta=3.00 hand=3.00 total=18.00 util=-3.00
```

These are the projected outcomes for the chosen move.

### `delta`

Projected score added to this player from now to the end of the hand.

Lower is better.

This is the most important number to read first.

### `hand`

Projected points this player will take in the remainder of this hand.

Lower is better.

### `total`

Projected overall game score after the hand resolves.

Lower is better.

### `util`

Internal convenience score used by search.

Higher is better, but in practice it mostly mirrors the score-based fields.

For quick reading, use:
1. `delta`
2. `hand`
3. `total`

## `Chosen facts`

Example:

```text
Chosen facts: follow, point, trick=13
```

These are quick tactical flags about the selected move.

Possible meanings:
- `follow`: the card follows the led suit
- `point`: the card itself is a point card
- `trick=13`: there are already 13 points sitting in the trick before this card is played

## Baseline Comparison

Search explanations also compare the search choice against `heuristic_v3`.

### Baseline line

Example:

```text
Baseline heuristic_v3: 7C (disagree, rank 2)
```

Meaning:
- `heuristic_v3` would have played `7C`
- search chose something else
- if search's own candidate ranking is used, the heuristic move ranked `#2`

If it says `agree`, both bots wanted the same move.

### `Vs baseline`

Example:

```text
Vs baseline: delta=1.00 util=1.00
```

Meaning:
- on average, search thinks its chosen move is better than the heuristic baseline by this amount

Interpretation:
- positive here means search believes it improved on `heuristic_v3`
- negative would mean search's choice looks worse than the heuristic baseline

### `Worlds: win / tie / lose`

Example:

```text
Worlds: win 1 tie 0 lose 0
```

Meaning:
- `win`: in that sampled world, search's move looked better than the heuristic move
- `tie`: they looked equal
- `lose`: the heuristic move looked better

With current defaults, this is often only one world, so:

```text
win 1 tie 0 lose 0
```

means only:

`In the one guessed hidden deal, search liked its own move better.`

That is useful, but it is not yet strong evidence.

### `Range: best / worst`

Example:

```text
Range: best +2.00 worst -0.00
```

Meaning:
- `best`: best-case advantage search saw over the heuristic move
- `worst`: worst-case downside search saw relative to the heuristic move

## `Top search candidates`

Example:

```text
Top search candidates:
- #1 6C delta=3.00 hand=3.00 util=-3.00 [selected, follow]
- #2 7C delta=4.00 hand=4.00 util=-4.00 [baseline, follow]
- #3 QC delta=7.00 hand=7.00 util=-7.00 [point, follow]
```

This is the ranked shortlist of legal moves search evaluated.

### `#1`, `#2`, `#3`

The move's final rank according to search.

### `selected`

The move search actually chose.

### `baseline`

The move `heuristic_v3` would have chosen.

### Other flags

Possible flags:
- `point`: point card
- `follow`: follows suit
- `trick=...`: there are already that many points in the trick

### Candidate metrics

Each candidate line includes the same kinds of projected numbers:
- `delta`
- `hand`
- `util`

Read these as:

`If the bot plays this card now, this is the projected outcome from there.`

## How To Read The Panel Quickly

If you want the fast version, read it in this order:

1. `Chosen`
2. `Source`
3. `Worlds`
4. `Baseline ... agree/disagree`
5. `Vs baseline`
6. top 2-3 candidate lines

That gives you the practical story without reading every field.

## Important Caveat

Current `search_v1` usually runs with only one sampled world by default.

That means the debug panel is informative, but still noisy.

So if you see something strange like:
- an odd high spade lead
- an aggressive point-taking line
- a disagreement with `heuristic_v3`

do **not** assume the search result is robust.

At this phase, the panel often means:

`In one guessed hidden deal, search preferred this move.`

That is useful for investigation, but it is not the same thing as strong evidence across many possible hidden deals.

## Short Version

If you only want the plain-English summary:

- `Chosen`: what the bot picked
- `Worlds`: how many hidden-hand guesses search used
- `Baseline heuristic_v3`: what the old handcrafted bot would have done
- `Vs baseline`: how much better search thinks its move is
- `Top search candidates`: the shortlist search considered, ranked best to worst
