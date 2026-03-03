import pytest

from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.errors import IllegalMoveError, InvalidStateError
from hearts_ai.engine.types import PLAYER_COUNT, PLAYER_IDS, PlayerId, to_player_id


def test_make_deck_has_52_unique_cards() -> None:
    deck = make_deck()
    assert len(deck) == 52
    assert len(set(deck)) == 52


def test_make_deck_has_all_suits_and_ranks() -> None:
    deck = make_deck()

    for suit in Suit:
        assert sum(card.suit == suit for card in deck) == 13
    for rank in Rank:
        assert sum(card.rank == rank for card in deck) == 4


def test_card_string_and_ordering() -> None:
    assert str(Card(Suit.HEARTS, Rank.QUEEN)) == "QH"
    assert Card(Suit.CLUBS, Rank.TWO) < Card(Suit.SPADES, Rank.ACE)


def test_player_id_helpers() -> None:
    assert PLAYER_COUNT == 4
    assert PLAYER_IDS == (PlayerId(0), PlayerId(1), PlayerId(2), PlayerId(3))
    assert to_player_id(3) == PlayerId(3)

    with pytest.raises(ValueError):
        to_player_id(-1)
    with pytest.raises(ValueError):
        to_player_id(4)


def test_engine_errors_inherit_expected_bases() -> None:
    assert issubclass(IllegalMoveError, ValueError)
    assert issubclass(InvalidStateError, RuntimeError)
