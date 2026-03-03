from __future__ import annotations

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.types import PLAYER_IDS, PlayerId, Trick

SHOOT_THE_MOON_POINTS = 26


def card_points(card: Card) -> int:
    if card.suit == Suit.HEARTS:
        return 1
    if card.suit == Suit.SPADES and card.rank == Rank.QUEEN:
        return 13
    return 0


def trick_points(trick: Trick) -> int:
    return sum(card_points(card) for _, card in trick)


def hand_points(taken_tricks: dict[PlayerId, list[Trick]]) -> dict[PlayerId, int]:
    if set(taken_tricks.keys()) != set(PLAYER_IDS):
        raise InvalidStateError("taken_tricks must include exactly four players.")

    raw_points = {
        player_id: sum(trick_points(trick) for trick in taken_tricks[player_id])
        for player_id in PLAYER_IDS
    }

    shooter = next(
        (player_id for player_id, points in raw_points.items() if points == SHOOT_THE_MOON_POINTS),
        None,
    )
    if shooter is None:
        return raw_points

    return {
        player_id: 0 if player_id == shooter else SHOOT_THE_MOON_POINTS for player_id in PLAYER_IDS
    }


__all__ = ["SHOOT_THE_MOON_POINTS", "card_points", "hand_points", "trick_points"]
