from __future__ import annotations

import random
from typing import Literal

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.rules import is_point_card, trick_winner
from hearts_ai.engine.scoring import trick_points
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_COUNT, PlayerId, Trick


def _rollout_score_v2(
    state: GameState,
    player_id: PlayerId,
    card: Card,
    mode: Literal["lead", "follow", "discard"],
    moon_target: PlayerId | None,
    samples: int,
    sample_seeds: tuple[int, ...] | None,
    rng: random.Random,
) -> float:
    if samples <= 0:
        return 0.0
    if _skip_rollout_for_follow_candidate(state=state, mode=mode, card=card):
        return 0.0

    base_trick = [*state.trick_in_progress, (player_id, card)]
    if len(base_trick) >= PLAYER_COUNT:
        return _evaluate_rollout_trick(base_trick, player_id=player_id, moon_target=moon_target)

    known_cards = {held for held in state.hands[player_id]}
    for taken in state.taken_tricks.values():
        for trick in taken:
            known_cards.update(current for _, current in trick)
    known_cards.update(current for _, current in state.trick_in_progress)
    unknown_pool = [
        current for current in _full_deck() if current not in known_cards and current != card
    ]
    if not unknown_pool:
        return 0.0

    remaining_players = _remaining_players_after(player_id=player_id, already_played=len(base_trick))
    seeds = sample_seeds if sample_seeds is not None else _shared_rollout_sample_seeds(samples, rng)
    if not seeds:
        return 0.0
    total = 0.0
    for sample_seed in seeds:
        sample_rng = random.Random(sample_seed)
        sample_pool = list(unknown_pool)
        sample_trick = list(base_trick)
        for _pid in remaining_players:
            if not sample_pool:
                break
            sampled = _sample_unknown_card_for_trick(
                trick=sample_trick,
                pool=sample_pool,
                first_trick=state.trick_number == 0,
                rng=sample_rng,
            )
            sample_pool.remove(sampled)
            sample_trick.append((_pid, sampled))
        if len(sample_trick) == PLAYER_COUNT:
            total += _evaluate_rollout_trick(
                sample_trick,
                player_id=player_id,
                moon_target=moon_target,
            )
    return total / float(len(seeds))


def _evaluate_rollout_trick(trick: Trick, player_id: PlayerId, moon_target: PlayerId | None) -> float:
    winner = trick_winner(trick)
    points = trick_points(trick)
    score = 0.0
    if winner == player_id:
        score -= float(points)
    else:
        score += float(points) * 0.2

    if moon_target is not None and points > 0:
        if winner == moon_target:
            score -= float(points) * 2.5
        elif winner == player_id:
            score += float(points) * 1.6
        else:
            score += float(points) * 0.7
    return score


def _skip_rollout_for_follow_candidate(
    state: GameState,
    mode: Literal["lead", "follow", "discard"],
    card: Card,
) -> bool:
    if mode != "follow":
        return False
    if is_point_card(card):
        return False
    trick = state.trick_in_progress
    if not trick:
        return False
    led_suit = trick[0][1].suit
    current_highest = max(current.rank for _, current in trick if current.suit == led_suit)
    # If we are guaranteed to lose with a non-point follow card, rollout cannot
    # change card-winning outcome for this trick and should not add sampling noise.
    return card.suit == led_suit and card.rank < current_highest


def _shared_rollout_sample_seeds(samples: int, rng: random.Random) -> tuple[int, ...]:
    if samples <= 0:
        return ()
    return tuple(rng.randrange(0, 2**63) for _ in range(samples))


def _remaining_players_after(player_id: PlayerId, already_played: int) -> list[PlayerId]:
    remaining = PLAYER_COUNT - already_played
    return [PlayerId((int(player_id) + offset) % PLAYER_COUNT) for offset in range(1, remaining + 1)]


def _sample_unknown_card_for_trick(
    trick: Trick,
    pool: list[Card],
    first_trick: bool,
    rng: random.Random,
) -> Card:
    led_suit = trick[0][1].suit
    suited_cards = [current for current in pool if current.suit == led_suit]
    if suited_cards and rng.random() < 0.65:
        return rng.choice(suited_cards)

    if first_trick:
        safe_cards = [current for current in pool if not is_point_card(current)]
        if safe_cards:
            return rng.choice(safe_cards)

    return rng.choice(pool)


def _full_deck() -> tuple[Card, ...]:
    deck: list[Card] = []
    for suit in Suit:
        for rank in Rank:
            deck.append(Card(suit=suit, rank=rank))
    return tuple(deck)

