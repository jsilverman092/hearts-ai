from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.rules import is_point_card, legal_moves, trick_winner
from hearts_ai.engine.scoring import trick_points
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_COUNT, Hand, PlayerId, Trick

_QUEEN_SPADES = Card(Suit.SPADES, Rank.QUEEN)
_KING_SPADES = Card(Suit.SPADES, Rank.KING)
_ACE_SPADES = Card(Suit.SPADES, Rank.ACE)


@dataclass(slots=True, frozen=True)
class HeuristicBot:
    player_id: PlayerId

    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        del rng
        pass_count = state.config.pass_count
        if state.pass_direction == "hold" or pass_count == 0:
            return []
        if pass_count > len(hand):
            raise InvalidStateError(
                f"Cannot pass {pass_count} cards from hand of size {len(hand)} for player {int(self.player_id)}."
            )

        by_risk = sorted(hand, key=_pass_priority, reverse=True)
        return sorted(by_risk[:pass_count])

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        del rng
        moves = legal_moves(state=state, player_id=self.player_id)
        if not moves:
            raise InvalidStateError(f"No legal moves available for player {int(self.player_id)}.")

        if not state.trick_in_progress:
            return _choose_lead(moves)
        return _choose_follow_or_discard(
            trick=state.trick_in_progress,
            legal=moves,
            first_trick=state.trick_number == 0,
        )


@dataclass(slots=True, frozen=True)
class PassCandidateReason:
    card: Card
    score: tuple[int, int, int]


@dataclass(slots=True, frozen=True)
class PassDecisionReason:
    selected_cards: tuple[Card, ...]
    candidates: tuple[PassCandidateReason, ...]


@dataclass(slots=True, frozen=True)
class PlayCandidateReason:
    card: Card
    base_score: float
    rollout_score: float
    total_score: float
    tags: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class PlayDecisionReason:
    mode: Literal["lead", "follow", "discard"]
    trick_number: int
    chosen_card: Card
    moon_defense_target: PlayerId | None
    candidates: tuple[PlayCandidateReason, ...]


@dataclass(slots=True)
class HeuristicBotV2:
    player_id: PlayerId
    rollout_samples: int = 4
    rollout_weight: float = 0.35
    moon_defense_threshold: int = 12
    _last_pass_reason: PassDecisionReason | None = field(init=False, default=None, repr=False)
    _last_play_reason: PlayDecisionReason | None = field(init=False, default=None, repr=False)

    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        del rng
        pass_count = state.config.pass_count
        if state.pass_direction == "hold" or pass_count == 0:
            self._last_pass_reason = PassDecisionReason(selected_cards=(), candidates=())
            return []
        if pass_count > len(hand):
            raise InvalidStateError(
                f"Cannot pass {pass_count} cards from hand of size {len(hand)} for player {int(self.player_id)}."
            )

        ranked = sorted(hand, key=_pass_priority, reverse=True)
        selected = tuple(sorted(ranked[:pass_count]))
        self._last_pass_reason = PassDecisionReason(
            selected_cards=selected,
            candidates=tuple(PassCandidateReason(card=card, score=_pass_priority(card)) for card in ranked),
        )
        return list(selected)

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        legal = legal_moves(state=state, player_id=self.player_id)
        if not legal:
            raise InvalidStateError(f"No legal moves available for player {int(self.player_id)}.")

        mode = _play_mode(state=state, legal=legal)
        moon_target = _moon_defense_target(
            state=state,
            player_id=self.player_id,
            threshold=self.moon_defense_threshold,
        )
        candidate_reasons: list[PlayCandidateReason] = []
        for card in legal:
            base_score, tags = _score_base_v2(
                state=state,
                player_id=self.player_id,
                card=card,
                mode=mode,
                moon_target=moon_target,
            )
            rollout_score = _rollout_score_v2(
                state=state,
                player_id=self.player_id,
                card=card,
                mode=mode,
                moon_target=moon_target,
                samples=self.rollout_samples,
                rng=rng,
            )
            total_score = base_score + (self.rollout_weight * rollout_score)
            candidate_reasons.append(
                PlayCandidateReason(
                    card=card,
                    base_score=base_score,
                    rollout_score=rollout_score,
                    total_score=total_score,
                    tags=tuple(tags),
                )
            )

        ordered_candidates = tuple(
            sorted(
                candidate_reasons,
                key=lambda entry: (
                    entry.total_score,
                    *_move_tiebreak(mode=mode, card=entry.card),
                ),
                reverse=True,
            )
        )
        chosen = ordered_candidates[0].card
        self._last_play_reason = PlayDecisionReason(
            mode=mode,
            trick_number=state.trick_number,
            chosen_card=chosen,
            moon_defense_target=moon_target,
            candidates=ordered_candidates,
        )
        return chosen

    # Internal hooks for future debug UI integration.
    def _peek_last_pass_reason(self) -> PassDecisionReason | None:
        return self._last_pass_reason

    def _peek_last_play_reason(self) -> PlayDecisionReason | None:
        return self._last_play_reason


def _choose_lead(legal: list[Card]) -> Card:
    non_hearts = [card for card in legal if card.suit != Suit.HEARTS]
    candidates = non_hearts if non_hearts else legal
    return min(candidates, key=_low_key)


def _choose_follow_or_discard(trick: Trick, legal: list[Card], first_trick: bool) -> Card:
    led_suit = trick[0][1].suit
    follow_cards = [card for card in legal if card.suit == led_suit]
    if follow_cards:
        return _choose_follow(trick=trick, follow_cards=follow_cards, first_trick=first_trick)
    return max(legal, key=_discard_priority)


def _choose_follow(trick: Trick, follow_cards: list[Card], first_trick: bool) -> Card:
    led_suit = trick[0][1].suit
    current_highest = max(
        card.rank for _, card in trick if card.suit == led_suit
    )
    losing_cards = [card for card in follow_cards if card.rank < current_highest]
    trick_has_points = any(is_point_card(card) for _, card in trick)

    if trick_has_points and losing_cards:
        return max(losing_cards, key=_discard_priority)
    if trick_has_points:
        return min(follow_cards, key=_low_key)
    if first_trick and not losing_cards:
        # First trick without points: if we must win, shed the highest club now.
        return max(follow_cards, key=_discard_priority)
    if losing_cards:
        return max(losing_cards, key=_discard_priority)
    return min(follow_cards, key=_low_key)


def _low_key(card: Card) -> tuple[int, int]:
    return (int(card.rank), int(card.suit))


def _pass_priority(card: Card) -> tuple[int, int, int]:
    if card == _QUEEN_SPADES:
        return (6, int(card.rank), int(card.suit))
    if card == _ACE_SPADES:
        return (5, int(card.rank), int(card.suit))
    if card == _KING_SPADES:
        return (4, int(card.rank), int(card.suit))
    if card.suit == Suit.HEARTS:
        return (3, int(card.rank), int(card.suit))
    if card.suit in (Suit.CLUBS, Suit.DIAMONDS):
        return (2, int(card.rank), int(card.suit))
    return (1, int(card.rank), int(card.suit))


def _discard_priority(card: Card) -> tuple[int, int, int]:
    return _pass_priority(card)


def _play_mode(state: GameState, legal: list[Card]) -> Literal["lead", "follow", "discard"]:
    if not state.trick_in_progress:
        return "lead"
    led_suit = state.trick_in_progress[0][1].suit
    has_follow = any(card.suit == led_suit for card in legal)
    return "follow" if has_follow else "discard"


def _moon_defense_target(state: GameState, player_id: PlayerId, threshold: int) -> PlayerId | None:
    hand_points = {
        pid: sum(trick_points(trick) for trick in state.taken_tricks[pid])
        for pid in state.taken_tricks
    }
    opponents = [pid for pid in hand_points if pid != player_id]
    if not opponents:
        return None
    target = max(opponents, key=lambda pid: hand_points[pid])
    target_points = hand_points[target]
    runner_up = max((hand_points[pid] for pid in opponents if pid != target), default=0)
    if target_points >= threshold and target_points >= runner_up + 6:
        return target
    return None


def _score_base_v2(
    state: GameState,
    player_id: PlayerId,
    card: Card,
    mode: Literal["lead", "follow", "discard"],
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    if mode == "lead":
        return _score_lead_v2(state=state, card=card)
    if mode == "follow":
        return _score_follow_v2(
            state=state,
            player_id=player_id,
            card=card,
            moon_target=moon_target,
        )
    return _score_discard_v2(
        state=state,
        card=card,
        moon_target=moon_target,
    )


def _score_lead_v2(state: GameState, card: Card) -> tuple[float, list[str]]:
    score = 0.0
    tags: list[str] = []
    if card.suit != Suit.HEARTS:
        score += 2.0
        tags.append("lead_non_heart")
    else:
        score -= 2.5
        tags.append("avoid_heart_lead")
    score -= float(int(card.rank)) * 0.12
    tags.append("prefer_lower_lead")
    if card in (_QUEEN_SPADES, _KING_SPADES, _ACE_SPADES):
        score += 1.1
        tags.append("shed_spade_risk")
    if state.trick_number == 0:
        score -= float(int(card.rank)) * 0.06
        tags.append("first_trick_conservative_lead")
    return score, tags


def _score_follow_v2(
    state: GameState,
    player_id: PlayerId,
    card: Card,
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    trick = state.trick_in_progress
    led_suit = trick[0][1].suit
    current_highest = max(current.rank for _, current in trick if current.suit == led_suit)
    losing = card.rank < current_highest
    trick_has_points = any(is_point_card(current) for _, current in trick)

    score = 0.0
    tags: list[str] = []
    if losing:
        score += 3.0 + (float(int(card.rank)) * 0.08)
        tags.append("prefer_high_losing_follow")
    else:
        score -= 2.0
        tags.append("forced_win_follow")

    if trick_has_points:
        if losing:
            score += 1.2
            tags.append("avoid_point_capture")
        else:
            score -= 7.5
            tags.append("point_trick_win_penalty")
    elif state.trick_number == 0 and not losing:
        # First trick has no points; if we must win, shed high club now.
        score += float(int(card.rank)) * 0.22
        tags.append("first_trick_forced_win_shed_high")

    if moon_target is not None and trick_has_points:
        projected_winner = trick_winner([*trick, (player_id, card)])
        if projected_winner == moon_target:
            score -= 5.0
            tags.append("moon_target_still_wins")
        elif projected_winner == player_id:
            score += 2.4
            tags.append("block_moon_target")

    return score, tags


def _score_discard_v2(
    state: GameState,
    card: Card,
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    score = 0.0
    tags: list[str] = []
    priority = _discard_priority(card)
    score += (float(priority[0]) * 1.8) + (float(priority[1]) * 0.04)
    tags.append("discard_priority")

    if moon_target is not None:
        current_points = trick_points(state.trick_in_progress)
        current_winner = trick_winner(state.trick_in_progress)
        if current_points > 0 and current_winner == moon_target and is_point_card(card):
            score -= 4.5
            tags.append("avoid_feeding_moon_target")
    return score, tags


def _rollout_score_v2(
    state: GameState,
    player_id: PlayerId,
    card: Card,
    mode: Literal["lead", "follow", "discard"],
    moon_target: PlayerId | None,
    samples: int,
    rng: random.Random,
) -> float:
    if samples <= 0:
        return 0.0
    if not state.trick_in_progress and mode == "lead":
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
    total = 0.0
    for _ in range(samples):
        sample_pool = list(unknown_pool)
        sample_trick = list(base_trick)
        for _pid in remaining_players:
            if not sample_pool:
                break
            sampled = _sample_unknown_card_for_trick(
                trick=sample_trick,
                pool=sample_pool,
                first_trick=state.trick_number == 0,
                rng=rng,
            )
            sample_pool.remove(sampled)
            sample_trick.append((_pid, sampled))
        if len(sample_trick) == PLAYER_COUNT:
            total += _evaluate_rollout_trick(
                sample_trick,
                player_id=player_id,
                moon_target=moon_target,
            )
    return total / float(samples)


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


def _move_tiebreak(mode: Literal["lead", "follow", "discard"], card: Card) -> tuple[int, int, int]:
    if mode == "lead":
        # Prefer lower lead cards on ties.
        return (-int(card.rank), -int(card.suit), 0)
    priority = _discard_priority(card)
    return (priority[0], priority[1], priority[2])


def _full_deck() -> tuple[Card, ...]:
    deck: list[Card] = []
    for suit in Suit:
        for rank in Rank:
            deck.append(Card(suit=suit, rank=rank))
    return tuple(deck)


__all__ = [
    "HeuristicBot",
    "HeuristicBotV2",
    "PassCandidateReason",
    "PassDecisionReason",
    "PlayCandidateReason",
    "PlayDecisionReason",
]
