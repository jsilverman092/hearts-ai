from __future__ import annotations

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PlayerId
from hearts_ai.search import SeatPrivateMemory, build_search_player_view


def test_seat_private_memory_records_pass_recipient_and_snapshot_helpers() -> None:
    state = GameState()
    state.pass_direction = "right"
    memory = SeatPrivateMemory(player_id=PlayerId(0))
    queen_spades = Card(Suit.SPADES, Rank.QUEEN)
    ace_clubs = Card(Suit.CLUBS, Rank.ACE)

    recipient = memory.record_own_pass(
        state=state,
        selected_cards=[queen_spades, ace_clubs],
    )
    snapshot = memory.snapshot()

    assert recipient == PlayerId(3)
    assert memory.cards_passed_to(PlayerId(3)) == (ace_clubs, queen_spades)
    assert snapshot.cards_passed_to(PlayerId(3)) == (ace_clubs, queen_spades)
    assert snapshot.recipient_for_passed_card(queen_spades) == PlayerId(3)
    assert snapshot.has_passed_card(card=queen_spades, recipient=PlayerId(3)) is True


def test_seat_private_memory_resets_on_new_hand_and_new_game() -> None:
    state = GameState()
    memory = SeatPrivateMemory(player_id=PlayerId(2))
    queen_spades = Card(Suit.SPADES, Rank.QUEEN)

    memory.record_own_pass(state=state, selected_cards=[queen_spades])
    assert memory.has_passed_card(card=queen_spades) is True

    state.hand_number = 2
    memory.on_new_hand(state)
    assert memory.has_passed_card(card=queen_spades) is False

    memory.record_own_pass(state=state, selected_cards=[queen_spades])
    memory.on_new_game()
    assert memory.has_passed_card(card=queen_spades) is False


def test_search_player_view_accepts_snapshot_from_seat_private_memory() -> None:
    state = GameState()
    state.hands[PlayerId(0)] = [Card(Suit.CLUBS, Rank.TWO)]
    state.turn = PlayerId(0)
    state.pass_applied = True
    memory = SeatPrivateMemory(player_id=PlayerId(0))
    queen_spades = Card(Suit.SPADES, Rank.QUEEN)
    memory.record_own_pass(state=state, selected_cards=[queen_spades])

    view = build_search_player_view(
        state=state,
        player_id=PlayerId(0),
        private_knowledge=memory.snapshot(),
    )

    assert view.private_knowledge.recipient_for_passed_card(queen_spades) == PlayerId(1)
