from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3

    @property
    def short_name(self) -> str:
        return ("C", "D", "H", "S")[self.value]


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def short_name(self) -> str:
        if self.value <= 10:
            return str(self.value)
        return {Rank.JACK: "J", Rank.QUEEN: "Q", Rank.KING: "K", Rank.ACE: "A"}[self]


@dataclass(frozen=True, order=True, slots=True)
class Card:
    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        return f"{self.rank.short_name}{self.suit.short_name}"


def make_deck() -> list[Card]:
    return [Card(suit=suit, rank=rank) for suit in Suit for rank in Rank]


__all__ = ["Card", "Rank", "Suit", "make_deck"]
