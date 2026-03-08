from __future__ import annotations

import random
from dataclasses import dataclass

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.rules import is_point_card, legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId, Trick

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
        return _choose_follow_or_discard(trick=state.trick_in_progress, legal=moves)


def _choose_lead(legal: list[Card]) -> Card:
    non_hearts = [card for card in legal if card.suit != Suit.HEARTS]
    candidates = non_hearts if non_hearts else legal
    return min(candidates, key=_low_key)


def _choose_follow_or_discard(trick: Trick, legal: list[Card]) -> Card:
    led_suit = trick[0][1].suit
    follow_cards = [card for card in legal if card.suit == led_suit]
    if follow_cards:
        return _choose_follow(trick=trick, follow_cards=follow_cards)
    return max(legal, key=_discard_priority)


def _choose_follow(trick: Trick, follow_cards: list[Card]) -> Card:
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


__all__ = ["HeuristicBot"]
