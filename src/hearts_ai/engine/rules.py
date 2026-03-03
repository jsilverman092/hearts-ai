from __future__ import annotations

from typing import Protocol

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import IllegalMoveError, InvalidStateError
from hearts_ai.engine.types import Deal, PlayerId, Trick


class RulesState(Protocol):
    hands: Deal
    trick_in_progress: Trick
    hearts_broken: bool


def is_point_card(card: Card) -> bool:
    return card.suit == Suit.HEARTS or (card.suit == Suit.SPADES and card.rank == Rank.QUEEN)


def trick_winner(trick: Trick) -> PlayerId:
    if not trick:
        raise InvalidStateError("Cannot determine winner of an empty trick.")

    led_suit = trick[0][1].suit
    winning_player, winning_card = trick[0]

    for player_id, card in trick[1:]:
        if card.suit == led_suit and card.rank > winning_card.rank:
            winning_player = player_id
            winning_card = card

    return winning_player


def legal_moves(state: RulesState, player_id: PlayerId) -> list[Card]:
    if player_id not in state.hands:
        raise InvalidStateError(f"Unknown player id: {player_id!r}")

    hand = state.hands[player_id]
    if not hand:
        return []

    lead_card = state.trick_in_progress[0][1] if state.trick_in_progress else None
    first_trick = _is_first_trick(state)

    if first_trick and not state.trick_in_progress:
        opening_card = Card(Suit.CLUBS, Rank.TWO)
        if opening_card not in hand:
            raise InvalidStateError("Opening lead must come from the player holding 2C.")
        return [opening_card]

    if lead_card is not None:
        same_suit_cards = [card for card in hand if card.suit == lead_card.suit]
        legal = same_suit_cards if same_suit_cards else list(hand)
    else:
        legal = _legal_leads(hand=hand, hearts_broken=state.hearts_broken)

    if first_trick:
        non_point_legal = [card for card in legal if not is_point_card(card)]
        if non_point_legal:
            legal = non_point_legal

    return legal


def validate_move(state: RulesState, player_id: PlayerId, card: Card) -> None:
    if card not in legal_moves(state=state, player_id=player_id):
        raise IllegalMoveError(f"Illegal play: {card} for player {int(player_id)}")


def _cards_played(hands: Deal) -> int:
    cards_in_hands = sum(len(hand) for hand in hands.values())
    cards_played = 52 - cards_in_hands
    if cards_played < 0 or cards_played > 52:
        raise InvalidStateError("Invalid hand sizes; expected a 52-card game state.")
    return cards_played


def _is_first_trick(state: RulesState) -> bool:
    trick_number = getattr(state, "trick_number", None)
    if trick_number is not None:
        return trick_number == 0

    return _cards_played(state.hands) < 4


def _legal_leads(hand: list[Card], hearts_broken: bool) -> list[Card]:
    if hearts_broken:
        return list(hand)

    non_hearts = [card for card in hand if card.suit != Suit.HEARTS]
    return non_hearts if non_hearts else list(hand)


__all__ = ["RulesState", "is_point_card", "legal_moves", "trick_winner", "validate_move"]
