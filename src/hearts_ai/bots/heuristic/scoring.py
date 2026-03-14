from __future__ import annotations

from hearts_ai.bots.heuristic.models import _ACE_SPADES, _KING_SPADES, _QUEEN_SPADES
from hearts_ai.bots.heuristic.public_info import (
    _build_public_info,
    _outside_rank_counts_for_card,
    _void_count_in_players,
)
from hearts_ai.bots.heuristic.rollout import _remaining_players_after
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.rules import is_point_card, trick_winner
from hearts_ai.engine.scoring import trick_points
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_COUNT, Hand, PlayerId, Trick


# Scripted v1 helper mechanics.
def _choose_lead(legal: list[Card]) -> Card:
    non_hearts = [card for card in legal if card.suit != Suit.HEARTS]
    candidates = non_hearts if non_hearts else legal
    return min(candidates, key=_low_key)


def _choose_follow_or_discard(trick: Trick, legal: list[Card], first_trick: bool) -> Card:
    led_suit = trick[0][1].suit
    follow_cards = [card for card in legal if card.suit == led_suit]
    if follow_cards:
        return _choose_follow(trick=trick, follow_cards=follow_cards, first_trick=first_trick)
    return max(legal, key=_score_discard_priority_base)


def _choose_follow(trick: Trick, follow_cards: list[Card], first_trick: bool) -> Card:
    led_suit = trick[0][1].suit
    current_highest = max(
        card.rank for _, card in trick if card.suit == led_suit
    )
    losing_cards = [card for card in follow_cards if card.rank < current_highest]
    trick_has_points = any(is_point_card(card) for _, card in trick)

    if trick_has_points and losing_cards:
        return max(losing_cards, key=_score_discard_priority_base)
    if trick_has_points:
        return min(follow_cards, key=_low_key)
    if first_trick and not losing_cards:
        # First trick without points: if we must win, shed the highest club now.
        return max(follow_cards, key=_score_discard_priority_base)
    if losing_cards:
        return max(losing_cards, key=_score_discard_priority_base)
    return min(follow_cards, key=_low_key)


def _low_key(card: Card) -> tuple[int, int]:
    return (int(card.rank), int(card.suit))


# Pass scoring helpers used by the heuristic bot versions.
def _score_pass_base(card: Card) -> tuple[int, int, int]:
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


def _score_pass_v3(card: Card, hand: Hand) -> tuple[int, int, int]:
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


def _score_discard_priority_base(card: Card) -> tuple[int, int, int]:
    # Keep current v2 behavior stable while decoupling discard naming/ownership from pass scoring.
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


# Lead scoring systems.
def _score_lead_base(
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
        else:
            # Once hearts are broken, low hearts are often useful escape leads.
            score -= 0.5
            if int(card.rank) <= int(Rank.FIVE):
                score += 1.9
                tags.append("low_heart_escape_lead")
            elif int(card.rank) >= int(Rank.TEN):
                score -= 0.9
                tags.append("avoid_high_heart_lead")
    score -= float(int(card.rank)) * 0.12
    if card == _QUEEN_SPADES:
        score -= 4.0 if lower_spade_available else 2.2
        tags.append("avoid_qs_lead")
    elif card in (_KING_SPADES, _ACE_SPADES):
        score -= 2.6 if lower_spade_available else 1.4
        tags.append("avoid_high_spade_lead")
    if state.hearts_broken and low_heart_legal and card in (_QUEEN_SPADES, _KING_SPADES, _ACE_SPADES):
        # Do not burn high spades when a cheap heart escape lead exists.
        score -= 1.6
        tags.append("prefer_low_heart_over_high_spade")
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
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    score, tags = _score_lead_base(state=state, legal=legal, card=card)
    public_info = _build_public_info(state=state)
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
        if state.trick_number <= 3:
            score -= 0.6
            tags.append("v3_preserve_floor_lead_inventory")
        elif state.trick_number <= 7:
            score -= 0.32
            tags.append("v3_preserve_floor_lead_inventory")
        else:
            score -= 0.12
            tags.append("v3_preserve_floor_lead_inventory")
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
        has_live_alternative = any(
            candidate != card
            and (
                sum(
                    _outside_rank_counts_for_card(
                        state=state,
                        public_info=public_info,
                        player_id=player_id,
                        card=candidate,
                    )
                )
                > 0
            )
            for candidate in legal
        )
        if moon_target is None and has_live_alternative:
            score -= 6.0
            tags.append("v3_avoid_owned_suit_lead_when_live_alternative")

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
    safe_qs_cash_lead = card == _QUEEN_SPADES and is_floor and outside_count > 0

    if safe_qs_cash_lead:
        score += 8.5
        tags.append("v3_safe_qs_cash_lead")

    if has_qs and spade_count <= 4 and not safe_qs_cash_lead:
        score -= 2.1
        tags.append("v3_avoid_short_qs_shape_spade_lead")
        if card == _QUEEN_SPADES:
            score -= 1.4
            tags.append("v3_avoid_qs_flush_lead")

    fragile_protection_shape = (
        public_info.qs_live
        and not has_qs
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


# Discard scoring systems.
def _score_discard_v3(
    state: GameState,
    player_id: PlayerId,
    card: Card,
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    score, tags = _score_discard_base(state=state, card=card, moon_target=moon_target)
    public_info = _build_public_info(state=state)
    if card.suit == Suit.SPADES and int(card.rank) <= int(Rank.JACK):
        if public_info.qs_live:
            score -= 1.8
            tags.append("v3_preserve_subqueen_spade_while_qs_live")
        else:
            # Bring 2S-JS back to ordinary black-suit treatment once QS is gone.
            score += 1.8
            tags.append("v3_qs_dead_subqueen_spade_as_black_suit")
    if card in (_ACE_SPADES, _KING_SPADES) and not public_info.qs_live:
        # _score_discard_base includes a large queen-protection premium for A/K spades
        # via v2 discard-priority buckets. Once QS is dead, remove most of it.
        queen_premium_buckets = max(_score_discard_priority_base(card)[0] - 2, 0)
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

    if outside_count == 0:
        score -= 1.0
        tags.append("v3_all_void_suit_safe_slough_keep")
    elif voids_in_opponents >= 2:
        if is_boss or is_trap:
            score += 0.3 + (0.12 * float(voids_in_opponents - 2))
            tags.append("v3_discard_void_pressure")
        elif is_floor:
            score -= 0.2
            tags.append("v3_floor_card_void_keep")

    if moon_target is not None and not is_point_card(card):
        moon_target_voids = public_info.void_suits_by_player.get(moon_target, frozenset())
        suit_still_live = outside_count >= 4
        stopper_candidate = is_boss or (
            outside_count > 0 and outside_higher_count <= 1 and int(card.rank) >= int(Rank.JACK)
        )
        if card.suit not in moon_target_voids and suit_still_live and stopper_candidate:
            has_secondary_cover = any(
                other != card
                and not is_point_card(other)
                and int(other.rank) >= int(Rank.TEN)
                and _outside_rank_counts_for_card(
                    state=state,
                    public_info=public_info,
                    player_id=player_id,
                    card=other,
                )[1]
                <= 1
                for other in state.hands[player_id]
                if other.suit == card.suit
            )
            stopper_penalty = 3.0
            if outside_count >= 8:
                stopper_penalty += 1.0
            if is_boss:
                stopper_penalty += 0.6
            if not has_secondary_cover:
                stopper_penalty += 1.6
                tags.append("v3_moon_defense_no_backup_stopper")
            score -= stopper_penalty
            tags.append("v3_moon_defense_keep_suit_stopper")
    return score, tags


# Follow scoring system.
def _score_follow_base(
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
    cards_already_played = len(trick)
    is_second_seat = cards_already_played == 1

    # Keep follow as one scoring family while making seat context explicit.
    if is_second_seat:
        losing_follow_bonus = 3.0
        forced_win_follow_penalty = 2.0
        avoid_point_capture_bonus = 1.2
        point_trick_win_penalty = 7.5
        first_trick_forced_win_rank_factor = 0.22
        moon_target_still_wins_penalty = 5.0
        block_moon_target_bonus = 2.4
    else:
        # Later-seat branch (third/fourth seat) intentionally uses the same
        # weights today; branch remains explicit for future follow tuning.
        losing_follow_bonus = 3.0
        forced_win_follow_penalty = 2.0
        avoid_point_capture_bonus = 1.2
        point_trick_win_penalty = 7.5
        first_trick_forced_win_rank_factor = 0.22
        moon_target_still_wins_penalty = 5.0
        block_moon_target_bonus = 2.4

    score = 0.0
    tags: list[str] = []
    if losing:
        score += losing_follow_bonus + (float(int(card.rank)) * 0.08)
        tags.append("prefer_high_losing_follow")
    else:
        score -= forced_win_follow_penalty
        tags.append("forced_win_follow")

    if trick_has_points:
        if losing:
            score += avoid_point_capture_bonus
            tags.append("avoid_point_capture")
        else:
            score -= point_trick_win_penalty
            tags.append("point_trick_win_penalty")
    elif state.trick_number == 0 and not losing:
        # First trick has no points; if we must win, shed high club now.
        score += float(int(card.rank)) * first_trick_forced_win_rank_factor
        tags.append("first_trick_forced_win_shed_high")

    if moon_target is not None and trick_has_points:
        projected_winner = trick_winner([*trick, (player_id, card)])
        if projected_winner == moon_target:
            score -= moon_target_still_wins_penalty
            tags.append("moon_target_still_wins")
        elif projected_winner == player_id:
            score += block_moon_target_bonus
            tags.append("block_moon_target")

    return score, tags


def _score_follow_v3(
    state: GameState,
    player_id: PlayerId,
    card: Card,
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    score, tags = _score_follow_base(
        state=state,
        player_id=player_id,
        card=card,
        moon_target=moon_target,
    )
    trick = state.trick_in_progress
    if len(trick) != 3:
        return score, tags

    led_suit = trick[0][1].suit
    current_highest = max(current.rank for _, current in trick if current.suit == led_suit)
    losing = card.rank < current_highest
    projected_trick = [*trick, (player_id, card)]
    if trick_points(projected_trick) != 0:
        return score, tags

    if losing:
        score -= 1.8
        tags.append("v3_last_seat_zero_point_duck_discount")
        return score, tags

    score += 2.0
    tags.append("v3_last_seat_zero_point_safe_win")
    public_info = _build_public_info(state=state)

    if card in (_ACE_SPADES, _KING_SPADES) and public_info.qs_live:
        score += 2.4
        tags.append("v3_last_seat_safe_ak_spade_shed")
        return score, tags

    if card.suit not in (Suit.CLUBS, Suit.DIAMONDS):
        return score, tags

    outside_lower_count, outside_higher_count = _outside_rank_counts_for_card(
        state=state,
        public_info=public_info,
        player_id=player_id,
        card=card,
    )
    outside_count = outside_lower_count + outside_higher_count
    is_boss = outside_count > 0 and outside_higher_count == 0
    is_trap = outside_lower_count > 0 and 0 < outside_higher_count <= 2

    if is_boss:
        score += 1.8
        tags.append("v3_last_seat_safe_boss_win_shed")
    elif is_trap:
        score += 1.5
        tags.append("v3_last_seat_safe_trap_win_shed")
    return score, tags


def _score_discard_base(
    state: GameState,
    card: Card,
    moon_target: PlayerId | None,
) -> tuple[float, list[str]]:
    score = 0.0
    tags: list[str] = []
    priority = _score_discard_priority_base(card)
    score += (float(priority[0]) * 1.8) + (float(priority[1]) * 0.04)
    tags.append("discard_priority")

    if moon_target is not None:
        current_points = trick_points(state.trick_in_progress)
        current_winner = trick_winner(state.trick_in_progress)
        if current_points > 0 and current_winner == moon_target and is_point_card(card):
            score -= 4.5
            tags.append("avoid_feeding_moon_target")
    return score, tags
