from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search.models import SeatPrivateKnowledge

_PASS_RECIPIENT_OFFSETS = {
    "left": 1,
    "right": -1,
    "across": 2,
}


@dataclass(slots=True)
class SeatPrivateMemory:
    """Mutable hand-scoped private memory for one seat."""

    player_id: PlayerId
    passed_cards_by_recipient: dict[PlayerId, tuple[Card, ...]] = field(default_factory=dict)

    def on_new_game(self) -> None:
        self.clear_hand_memory()

    def on_new_hand(self, state: GameState) -> None:
        del state
        self.clear_hand_memory()

    def clear_hand_memory(self) -> None:
        self.passed_cards_by_recipient.clear()

    def record_own_pass(
        self,
        *,
        state: GameState,
        selected_cards: Sequence[Card],
    ) -> PlayerId | None:
        self.clear_hand_memory()
        recipient = _pass_recipient(player_id=self.player_id, direction=state.pass_direction)
        if recipient is None or not selected_cards:
            return recipient
        self.passed_cards_by_recipient[recipient] = tuple(sorted(selected_cards))
        return recipient

    def cards_passed_to(self, recipient: PlayerId) -> tuple[Card, ...]:
        return self.passed_cards_by_recipient.get(recipient, ())

    def recipient_for_passed_card(self, card: Card) -> PlayerId | None:
        for recipient, cards in self.passed_cards_by_recipient.items():
            if card in cards:
                return recipient
        return None

    def has_passed_card(self, *, card: Card, recipient: PlayerId | None = None) -> bool:
        if recipient is not None:
            return card in self.passed_cards_by_recipient.get(recipient, ())
        return self.recipient_for_passed_card(card) is not None

    def snapshot(self) -> SeatPrivateKnowledge:
        return SeatPrivateKnowledge(
            passed_cards_by_recipient=MappingProxyType(dict(self.passed_cards_by_recipient))
        )


def _pass_recipient(*, player_id: PlayerId, direction: str) -> PlayerId | None:
    if direction == "hold":
        return None
    if direction not in _PASS_RECIPIENT_OFFSETS:
        raise ValueError(f"Unsupported pass direction: {direction!r}")
    if player_id not in PLAYER_IDS:
        raise ValueError(f"Unsupported player id: {player_id!r}")
    return PlayerId((int(player_id) + _PASS_RECIPIENT_OFFSETS[direction]) % len(PLAYER_IDS))


__all__ = ["SeatPrivateMemory"]
