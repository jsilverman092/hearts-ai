from __future__ import annotations

import random

from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.errors import IllegalMoveError, InvalidStateError
from hearts_ai.engine.rules import trick_winner, validate_move
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_COUNT, PLAYER_IDS, PlayerId

_TWO_OF_CLUBS = Card(Suit.CLUBS, Rank.TWO)
_PASS_OFFSETS = {"left": 1, "right": -1, "across": 2}


def new_game(rng: random.Random, config: GameConfig | None = None) -> GameState:
    state = GameState(config=config or GameConfig())
    deal(state=state, rng=rng)
    return state


def deal(state: GameState, rng: random.Random) -> None:
    _validate_player_collections(state)
    if state.hand_number > 0 and not is_hand_over(state):
        raise InvalidStateError("Cannot deal a new hand while the current hand is still active.")

    deck = make_deck()
    rng.shuffle(deck)

    cards_per_player = len(deck) // PLAYER_COUNT
    for index, player_id in enumerate(PLAYER_IDS):
        start = index * cards_per_player
        stop = start + cards_per_player
        state.hands[player_id] = sorted(deck[start:stop])

    state.hearts_broken = False
    state.trick_in_progress.clear()
    state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}
    state.trick_number = 0
    state.hand_number += 1
    state.pass_direction = state.config.pass_directions[
        (state.hand_number - 1) % len(state.config.pass_directions)
    ]
    state.pass_applied = state.pass_direction == "hold"
    state.turn = _player_holding_two_of_clubs(state)


def apply_pass(state: GameState, pass_map: dict[PlayerId, list[Card]]) -> None:
    _validate_player_collections(state)
    if is_hand_over(state):
        raise InvalidStateError("Cannot pass cards after a hand is over.")
    if state.trick_in_progress or state.trick_number > 0:
        raise InvalidStateError("Passing is only allowed before the first trick starts.")
    if state.pass_applied:
        raise InvalidStateError("Pass phase already completed for this hand.")

    direction = state.pass_direction
    if direction == "hold":
        if pass_map and any(pass_map.values()):
            raise InvalidStateError("No cards should be passed during a hold hand.")
        state.pass_applied = True
        state.turn = _player_holding_two_of_clubs(state)
        return

    _validate_pass_map(state=state, pass_map=pass_map)

    outbound = {player_id: list(pass_map[player_id]) for player_id in PLAYER_IDS}
    for player_id, cards in outbound.items():
        for card in cards:
            state.hands[player_id].remove(card)

    for player_id, cards in outbound.items():
        recipient = _pass_recipient(player_id=player_id, direction=direction)
        state.hands[recipient].extend(cards)

    for player_id in PLAYER_IDS:
        state.hands[player_id].sort()
        if len(state.hands[player_id]) != 13:
            raise InvalidStateError(f"Player {int(player_id)} has invalid hand size after pass.")

    state.pass_applied = True
    state.turn = _player_holding_two_of_clubs(state)


def play_card(state: GameState, player_id: PlayerId, card: Card) -> None:
    _validate_player_collections(state)
    if is_hand_over(state):
        raise InvalidStateError("Cannot play a card after hand completion.")
    if state.turn is None:
        raise InvalidStateError("No active turn. Deal cards first.")
    if state.turn != player_id:
        raise IllegalMoveError(
            f"It is player {int(state.turn)}'s turn, not player {int(player_id)}'s turn."
        )
    if not state.pass_applied and state.pass_direction != "hold":
        raise InvalidStateError("Cannot play before pass phase is completed.")
    if card not in state.hands[player_id]:
        raise IllegalMoveError(f"Player {int(player_id)} does not hold {card}.")

    validate_move(state=state, player_id=player_id, card=card)
    state.hands[player_id].remove(card)
    state.trick_in_progress.append((player_id, card))
    if card.suit == Suit.HEARTS:
        state.hearts_broken = True

    if len(state.trick_in_progress) < PLAYER_COUNT:
        state.turn = _next_player(player_id)
        return

    completed_trick = list(state.trick_in_progress)
    winner = trick_winner(completed_trick)
    state.taken_tricks[winner].append(completed_trick)
    state.trick_in_progress.clear()
    state.trick_number += 1
    state.turn = winner


def is_hand_over(state: GameState) -> bool:
    return not state.trick_in_progress and all(len(state.hands[player_id]) == 0 for player_id in PLAYER_IDS)


def is_game_over(state: GameState) -> bool:
    _validate_player_collections(state)
    return any(score >= state.config.target_score for score in state.scores.values())


def _validate_pass_map(state: GameState, pass_map: dict[PlayerId, list[Card]]) -> None:
    if set(pass_map.keys()) != set(PLAYER_IDS):
        raise InvalidStateError("Pass map must include one entry per player.")

    pass_count = state.config.pass_count
    for player_id in PLAYER_IDS:
        cards = pass_map[player_id]
        if len(cards) != pass_count:
            raise InvalidStateError(
                f"Player {int(player_id)} must pass exactly {pass_count} cards, got {len(cards)}."
            )
        if len(set(cards)) != len(cards):
            raise InvalidStateError(f"Player {int(player_id)} pass list contains duplicate cards.")
        hand = state.hands[player_id]
        if any(card not in hand for card in cards):
            raise InvalidStateError(f"Player {int(player_id)} attempted to pass a card not in hand.")


def _player_holding_two_of_clubs(state: GameState) -> PlayerId:
    for player_id in PLAYER_IDS:
        if _TWO_OF_CLUBS in state.hands[player_id]:
            return player_id
    raise InvalidStateError("No player holds 2C in a dealt hand.")


def _pass_recipient(player_id: PlayerId, direction: str) -> PlayerId:
    if direction not in _PASS_OFFSETS:
        raise InvalidStateError(f"Unsupported pass direction: {direction!r}")
    return PlayerId((int(player_id) + _PASS_OFFSETS[direction]) % PLAYER_COUNT)


def _next_player(player_id: PlayerId) -> PlayerId:
    return PlayerId((int(player_id) + 1) % PLAYER_COUNT)


def _validate_player_collections(state: GameState) -> None:
    expected_players = set(PLAYER_IDS)
    if set(state.hands.keys()) != expected_players:
        raise InvalidStateError("State hands must include exactly four players.")
    if set(state.scores.keys()) != expected_players:
        raise InvalidStateError("State scores must include exactly four players.")
    if set(state.taken_tricks.keys()) != expected_players:
        raise InvalidStateError("State taken_tricks must include exactly four players.")


__all__ = [
    "apply_pass",
    "deal",
    "is_game_over",
    "is_hand_over",
    "new_game",
    "play_card",
]
