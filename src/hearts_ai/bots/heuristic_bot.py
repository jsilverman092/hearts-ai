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


@dataclass(slots=True, frozen=True)
class PublicInfoV3:
    qs_live: bool
    played_count_by_suit: dict[Suit, int]
    lowest_unseen_rank_by_suit: dict[Suit, int | None]
    unseen_ranks_by_suit: dict[Suit, tuple[int, ...]]
    void_suits_by_player: dict[PlayerId, frozenset[Suit]]


@dataclass(slots=True)
class HeuristicBotV2:
    player_id: PlayerId
    rollout_samples: int = 12
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
        shared_rollout_sample_seeds = _shared_rollout_sample_seeds(
            samples=self.rollout_samples,
            rng=rng,
        )
        candidate_reasons: list[PlayCandidateReason] = []
        for card in legal:
            base_score, tags = self._score_base(
                state=state,
                player_id=self.player_id,
                legal=legal,
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
                sample_seeds=shared_rollout_sample_seeds,
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

    def _score_base(
        self,
        state: GameState,
        player_id: PlayerId,
        legal: list[Card],
        card: Card,
        mode: Literal["lead", "follow", "discard"],
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        return _score_base_v2(
            state=state,
            player_id=player_id,
            legal=legal,
            card=card,
            mode=mode,
            moon_target=moon_target,
        )


class HeuristicBotV3(HeuristicBotV2):
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

        ranked = sorted(hand, key=lambda card: _pass_priority_v3(card=card, hand=hand), reverse=True)
        selected = tuple(sorted(ranked[:pass_count]))
        self._last_pass_reason = PassDecisionReason(
            selected_cards=selected,
            candidates=tuple(
                PassCandidateReason(card=card, score=_pass_priority_v3(card=card, hand=hand))
                for card in ranked
            ),
        )
        return list(selected)

    def _score_base(
        self,
        state: GameState,
        player_id: PlayerId,
        legal: list[Card],
        card: Card,
        mode: Literal["lead", "follow", "discard"],
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        return _score_base_v3(
            state=state,
            player_id=player_id,
            legal=legal,
            card=card,
            mode=mode,
            moon_target=moon_target,
        )


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


def _pass_priority_v3(card: Card, hand: Hand) -> tuple[int, int, int]:
    spades = [current for current in hand if current.suit == Suit.SPADES]
    spade_count = len(spades)
    has_qs = _QUEEN_SPADES in spades
    has_ks = _KING_SPADES in spades
    has_as = _ACE_SPADES in spades
    low_spade_cover = sum(1 for current in spades if current.rank <= Rank.NINE)
    suit_count = sum(1 for current in hand if current.suit == card.suit)
    rank_value = int(card.rank)

    if card == _QUEEN_SPADES:
        if spade_count <= 3:
            primary = 980
        elif spade_count == 4:
            primary = 920
        elif spade_count == 5:
            primary = 350
        else:
            primary = 260
        if low_spade_cover >= 3:
            primary -= 40
        return (primary, rank_value, int(card.suit))

    if card in (_ACE_SPADES, _KING_SPADES):
        primary = 720 if card == _ACE_SPADES else 690
        if spade_count >= 5:
            primary -= 220
        # In longer non-queen spade holdings, keep A/K as future queen protection.
        if not has_qs and spade_count >= 3:
            primary -= 140
        if low_spade_cover >= 3:
            primary -= 70
        if has_as and has_ks:
            if low_spade_cover < 3:
                primary += 80 if card == _KING_SPADES else 30
            else:
                primary -= 30
        lower_cover_for_card = sum(1 for current in spades if current.rank < card.rank)
        if lower_cover_for_card == 0:
            primary += 70
        elif lower_cover_for_card >= 2:
            primary -= 60
        return (primary, rank_value, int(card.suit))

    if card.suit == Suit.SPADES:
        # Keep sub-queen spades as protection/escape cards in normal pass logic.
        # They should only be passed when effectively forced by hand composition.
        primary = -220 + rank_value
        if spade_count >= 7:
            primary += 80
        elif spade_count >= 6:
            primary += 50
        return (primary, rank_value, int(card.suit))

    if card.suit == Suit.HEARTS:
        if card.rank <= Rank.FOUR:
            primary = 70 + (rank_value * 2)
        elif card.rank == Rank.FIVE:
            primary = 220
        elif card.rank == Rank.SIX:
            primary = 320
        else:
            primary = 460 + (rank_value - int(Rank.SEVEN)) * 40
        if suit_count >= 5 and card.rank <= Rank.SIX:
            primary -= 30
        if suit_count <= 2 and card.rank >= Rank.TEN:
            primary += 30
        return (primary, rank_value, int(card.suit))

    if card.suit == Suit.CLUBS:
        if card.rank <= Rank.FOUR:
            primary = 60
        elif card.rank == Rank.FIVE:
            primary = 180
        elif card.rank <= Rank.NINE:
            primary = 250 + (rank_value - int(Rank.SIX)) * 25
        else:
            primary = 520 + (rank_value - int(Rank.JACK)) * 45
    else:
        if card.rank <= Rank.THREE:
            primary = 55
        elif card.rank == Rank.FOUR:
            primary = 175
        elif card.rank <= Rank.NINE:
            primary = 245 + (rank_value - int(Rank.FIVE)) * 24
        else:
            primary = 515 + (rank_value - int(Rank.JACK)) * 45

    if card.rank >= Rank.JACK and suit_count <= 2:
        primary += 45
    if suit_count >= 5 and card.rank <= Rank.FIVE:
        primary -= 30
    return (primary, rank_value, int(card.suit))


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
    legal: list[Card],
    card: Card,
    mode: Literal["lead", "follow", "discard"],
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    if mode == "lead":
        return _score_lead_v2(state=state, legal=legal, card=card)
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


def _score_base_v3(
    state: GameState,
    player_id: PlayerId,
    legal: list[Card],
    card: Card,
    mode: Literal["lead", "follow", "discard"],
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    if mode == "lead":
        return _score_lead_v3(
            state=state,
            player_id=player_id,
            legal=legal,
            hand=state.hands[player_id],
            card=card,
        )
    if mode == "follow":
        return _score_follow_v2(
            state=state,
            player_id=player_id,
            card=card,
            moon_target=moon_target,
        )
    return _score_discard_v3(
        state=state,
        player_id=player_id,
        card=card,
        moon_target=moon_target,
    )


def _score_lead_v2(
    state: GameState,
    legal: list[Card],
    card: Card,
) -> tuple[float, list[str]]:
    score = 0.0
    tags: list[str] = []
    spade_legal = [candidate for candidate in legal if candidate.suit == Suit.SPADES]
    lower_spade_available = any(candidate.rank < card.rank for candidate in spade_legal)
    low_heart_legal = [
        candidate
        for candidate in legal
        if candidate.suit == Suit.HEARTS and int(candidate.rank) <= int(Rank.FIVE)
    ]

    if card.suit != Suit.HEARTS:
        score += 2.0
        tags.append("lead_non_heart")
    else:
        if not state.hearts_broken:
            score -= 2.5
            tags.append("avoid_heart_lead")
        else:
            # Once hearts are broken, low hearts are often useful escape leads.
            score -= 0.5
            tags.append("hearts_broken_heart_lead")
            if int(card.rank) <= int(Rank.FIVE):
                score += 1.9
                tags.append("low_heart_escape_lead")
            elif int(card.rank) >= int(Rank.TEN):
                score -= 0.9
                tags.append("avoid_high_heart_lead")
    score -= float(int(card.rank)) * 0.12
    tags.append("prefer_lower_lead")
    if card == _QUEEN_SPADES:
        score -= 4.0 if lower_spade_available else 2.2
        tags.append("avoid_qs_lead")
    elif card in (_KING_SPADES, _ACE_SPADES):
        score -= 2.6 if lower_spade_available else 1.4
        tags.append("avoid_high_spade_lead")
    if card.suit == Suit.SPADES and int(card.rank) >= int(Rank.JACK):
        # High spade leads are broadly risky without strong trick context.
        score -= 0.8
        tags.append("cautious_high_spade_lead")
    if state.hearts_broken and low_heart_legal and card in (_QUEEN_SPADES, _KING_SPADES, _ACE_SPADES):
        # Do not burn high spades when a cheap heart escape lead exists.
        score -= 1.6
        tags.append("prefer_low_heart_over_high_spade")
    if state.trick_number == 0:
        score -= float(int(card.rank)) * 0.06
        tags.append("first_trick_conservative_lead")
    if card == _QUEEN_SPADES and state.hearts_broken:
        # If hearts are already live, opening with queen is even less attractive.
        score -= 0.5
        tags.append("avoid_qs_after_hearts_broken")
    if card.suit == Suit.SPADES and len(spade_legal) == len(legal):
        # If we are effectively forced to lead spades, favor lower spades.
        score -= float(int(card.rank)) * 0.04
        tags.append("forced_spade_lead_prefer_low")
    return score, tags


def _score_lead_v3(
    state: GameState,
    player_id: PlayerId,
    legal: list[Card],
    hand: Hand,
    card: Card,
) -> tuple[float, list[str]]:
    score, tags = _score_lead_v2(state=state, legal=legal, card=card)
    public_info = _build_public_info_v3(state=state)
    players_ahead = _remaining_players_after(player_id=player_id, already_played=1)
    outside_lower_count, outside_higher_count = _outside_rank_counts_for_card(
        state=state,
        public_info=public_info,
        player_id=player_id,
        card=card,
    )
    outside_count = outside_lower_count + outside_higher_count
    voids_ahead = _void_count_in_players(
        public_info=public_info,
        suit=card.suit,
        players=players_ahead,
    )
    is_floor = outside_count > 0 and outside_lower_count == 0
    is_boss = outside_count > 0 and outside_higher_count == 0
    is_trap = outside_lower_count > 0 and 0 < outside_higher_count <= 2

    if is_floor:
        score += 0.45
        tags.append("v3_floor_card_lead_safe")
    elif is_boss:
        score -= 0.78
        tags.append("v3_boss_card_lead_risk")
    elif is_trap:
        score -= 0.5 + (0.2 * float(2 - outside_higher_count))
        tags.append("v3_trap_card_lead_risk")

    if outside_count == 0:
        # If we hold all remaining cards in suit, leading it always yields control.
        score -= 0.9
        tags.append("v3_lead_owned_suit_control_risk")

    if int(card.rank) >= int(Rank.NINE) and voids_ahead > 0 and not is_floor:
        score -= 0.22 * float(voids_ahead)
        tags.append("v3_avoid_high_lead_with_voids_ahead")

    if voids_ahead > 0 and (is_boss or is_trap or outside_count == 0):
        score -= 0.14 * float(voids_ahead)
        tags.append("v3_lead_void_amplifies_control_risk")

    has_sub_queen_spade_lead = any(
        candidate.suit == Suit.SPADES and int(candidate.rank) <= int(Rank.JACK)
        for candidate in legal
    )
    if (
        card.suit != Suit.SPADES
        and _QUEEN_SPADES not in hand
        and public_info.qs_live
        and has_sub_queen_spade_lead
        and int(card.rank) >= int(Rank.TEN)
    ):
        # If QS is still live, mid/high off-suit leads can win awkward queen-dump tricks.
        score -= 0.35
        tags.append("v3_avoid_mid_offsuit_when_qs_live")
        if int(card.rank) >= int(Rank.JACK):
            score -= 0.15
            tags.append("v3_extra_offsuit_win_risk")

    if card.suit != Suit.SPADES:
        return score, tags

    if card == Card(Suit.SPADES, Rank.JACK):
        # Jack of spades is not in the same control-risk class as Q/K/A spades.
        score += 0.8
        tags.append("v3_jack_spade_not_high_control")

    non_spade_legal = [candidate for candidate in legal if candidate.suit != Suit.SPADES]
    if not non_spade_legal:
        return score, tags

    spades = [current for current in hand if current.suit == Suit.SPADES]
    spade_count = len(spades)
    has_qs = _QUEEN_SPADES in spades
    has_ks = _KING_SPADES in spades
    has_as = _ACE_SPADES in spades
    high_spade_count = int(has_as) + int(has_ks)
    low_spade_cover = sum(1 for current in spades if current.rank <= Rank.NINE)

    if has_qs and spade_count <= 4:
        score -= 2.1
        tags.append("v3_avoid_short_qs_shape_spade_lead")
        if card == _QUEEN_SPADES:
            score -= 1.4
            tags.append("v3_avoid_qs_flush_lead")

    fragile_protection_shape = (
        not has_qs
        and high_spade_count > 0
        and (spade_count - high_spade_count) <= 2
        and low_spade_cover <= 2
    )
    if fragile_protection_shape:
        score -= 1.5
        tags.append("v3_preserve_spade_protection_shape")
        if card in (_ACE_SPADES, _KING_SPADES):
            score -= 1.3
            tags.append("v3_avoid_exposing_high_spade_protection")

    return score, tags


def _score_discard_v3(
    state: GameState,
    player_id: PlayerId,
    card: Card,
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    score, tags = _score_discard_v2(state=state, card=card, moon_target=moon_target)
    public_info = _build_public_info_v3(state=state)
    if card.suit == Suit.SPADES and int(card.rank) <= int(Rank.JACK):
        if public_info.qs_live:
            score -= 1.8
            tags.append("v3_preserve_subqueen_spade_while_qs_live")
        else:
            # Bring 2S-JS back to ordinary black-suit treatment once QS is gone.
            score += 1.8
            tags.append("v3_qs_dead_subqueen_spade_as_black_suit")
    if card in (_ACE_SPADES, _KING_SPADES) and not public_info.qs_live:
        # _score_discard_v2 includes a large queen-protection premium for A/K spades via
        # shared discard/pass priority buckets. Once QS is dead, remove most of it.
        queen_premium_buckets = max(_pass_priority(card)[0] - 2, 0)
        score -= 1.8 * float(queen_premium_buckets)
        tags.append("v3_qs_dead_reduce_ak_spade_dump_premium")

    outside_lower_count, outside_higher_count = _outside_rank_counts_for_card(
        state=state,
        public_info=public_info,
        player_id=player_id,
        card=card,
    )
    opponents = [PlayerId(index) for index in range(PLAYER_COUNT) if PlayerId(index) != player_id]
    voids_in_opponents = _void_count_in_players(
        public_info=public_info,
        suit=card.suit,
        players=opponents,
    )
    outside_count = outside_lower_count + outside_higher_count
    is_floor = outside_count > 0 and outside_lower_count == 0
    is_boss = outside_count > 0 and outside_higher_count == 0
    is_trap = outside_lower_count > 0 and 0 < outside_higher_count <= 2

    if is_floor:
        # Floor cards are often reliable escape cards; avoid dumping them early.
        score -= 0.75
        tags.append("v3_floor_card_keep_safe")
    elif is_boss:
        score += 0.85
        tags.append("v3_boss_card_dump_risk")
    elif is_trap:
        score += 0.55 + (0.2 * float(2 - outside_higher_count))
        tags.append("v3_trap_card_dump_risk")

    if voids_in_opponents >= 2:
        if is_boss or is_trap:
            score += 0.3 + (0.12 * float(voids_in_opponents - 2))
            tags.append("v3_discard_void_pressure")
        elif is_floor:
            score -= 0.2
            tags.append("v3_floor_card_void_keep")
    return score, tags


def _build_public_info_v3(state: GameState) -> PublicInfoV3:
    seen_cards = {
        current
        for trick in _all_public_tricks(state=state)
        for _, current in trick
    }
    played_count_by_suit = {
        suit: sum(1 for current in seen_cards if current.suit == suit) for suit in Suit
    }
    unseen_ranks_by_suit: dict[Suit, tuple[int, ...]] = {}
    lowest_unseen_rank_by_suit: dict[Suit, int | None] = {}
    for suit in Suit:
        unseen = tuple(
            int(rank)
            for rank in Rank
            if Card(suit=suit, rank=rank) not in seen_cards
        )
        unseen_ranks_by_suit[suit] = unseen
        lowest_unseen_rank_by_suit[suit] = unseen[0] if unseen else None

    void_suits_by_player = _infer_void_suits_by_player(state=state)
    return PublicInfoV3(
        qs_live=_QUEEN_SPADES not in seen_cards,
        played_count_by_suit=played_count_by_suit,
        lowest_unseen_rank_by_suit=lowest_unseen_rank_by_suit,
        unseen_ranks_by_suit=unseen_ranks_by_suit,
        void_suits_by_player=void_suits_by_player,
    )


def _all_public_tricks(state: GameState) -> list[Trick]:
    tricks = [
        trick
        for taken in state.taken_tricks.values()
        for trick in taken
    ]
    if state.trick_in_progress:
        tricks.append(state.trick_in_progress)
    return tricks


def _infer_void_suits_by_player(state: GameState) -> dict[PlayerId, frozenset[Suit]]:
    inferred: dict[PlayerId, set[Suit]] = {
        PlayerId(index): set() for index in range(PLAYER_COUNT)
    }
    for trick in _all_public_tricks(state=state):
        if len(trick) < 2:
            continue
        led_suit = trick[0][1].suit
        for player_id, card in trick[1:]:
            if card.suit != led_suit:
                inferred[player_id].add(led_suit)
    return {player_id: frozenset(suits) for player_id, suits in inferred.items()}


def _outside_rank_counts_for_card(
    state: GameState,
    public_info: PublicInfoV3,
    player_id: PlayerId,
    card: Card,
) -> tuple[int, int]:
    rank_value = int(card.rank)
    own_suit_ranks = {
        int(current.rank) for current in state.hands[player_id] if current.suit == card.suit
    }
    unseen_ranks = public_info.unseen_ranks_by_suit[card.suit]
    outside_lower = sum(
        1 for unseen in unseen_ranks if unseen < rank_value and unseen not in own_suit_ranks
    )
    outside_higher = sum(
        1 for unseen in unseen_ranks if unseen > rank_value and unseen not in own_suit_ranks
    )
    return outside_lower, outside_higher


def _void_count_in_players(
    public_info: PublicInfoV3,
    suit: Suit,
    players: list[PlayerId],
) -> int:
    return sum(
        1
        for player_id in players
        if suit in public_info.void_suits_by_player.get(player_id, frozenset())
    )


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
    "HeuristicBotV3",
    "PassCandidateReason",
    "PassDecisionReason",
    "PlayCandidateReason",
    "PlayDecisionReason",
]
