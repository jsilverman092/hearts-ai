from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, TypeAlias

from hearts_ai.bots.base import Bot
from hearts_ai.bots.factory import create_bot
from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search.memory import SeatPrivateMemory
from hearts_ai.search.models import SeatPrivateKnowledge

BotBuilder: TypeAlias = Callable[[str, PlayerId], Bot]


class SupportsNewGame(Protocol):
    def on_new_game(self) -> None:
        """Reset or initialize game-scoped bot state."""


class SupportsNewHand(Protocol):
    def on_new_hand(self, state: GameState) -> None:
        """Reset or initialize hand-scoped bot state."""


class SupportsOwnPassSelected(Protocol):
    def on_own_pass_selected(
        self,
        *,
        state: GameState,
        selected_cards: Sequence[Card],
        recipient: PlayerId | None,
    ) -> None:
        """Capture exact cards this seat passed away for the current hand."""


def _default_bot_builder(bot_name: str, player_id: PlayerId) -> Bot:
    return create_bot(bot_name, player_id=player_id)


@dataclass(slots=True)
class BotRuntimeSession:
    """Persistent per-seat bot instances with explicit lifecycle notifications."""

    bot_names: Mapping[PlayerId, str]
    bot_builder: BotBuilder = _default_bot_builder
    _instances: dict[PlayerId, Bot] = field(default_factory=dict, init=False, repr=False)
    _private_memory_by_player: dict[PlayerId, SeatPrivateMemory] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_bot_names(
        cls,
        bot_names: Sequence[str],
        *,
        bot_builder: BotBuilder = _default_bot_builder,
    ) -> BotRuntimeSession:
        if len(bot_names) != len(PLAYER_IDS):
            raise ValueError(f"Expected {len(PLAYER_IDS)} bot names, got {len(bot_names)}.")
        return cls(
            bot_names={player_id: bot_names[index] for index, player_id in enumerate(PLAYER_IDS)},
            bot_builder=bot_builder,
        )

    def configured_players(self) -> tuple[PlayerId, ...]:
        return tuple(player_id for player_id in PLAYER_IDS if player_id in self.bot_names)

    def bot_name_for_player(self, player_id: PlayerId) -> str:
        if player_id not in self.bot_names:
            raise ValueError(f"Player {int(player_id)} is not configured in this bot runtime session.")
        return self.bot_names[player_id]

    def bot_for_player(self, player_id: PlayerId) -> Bot:
        if player_id not in self.bot_names:
            raise ValueError(f"Player {int(player_id)} is not configured in this bot runtime session.")
        existing = self._instances.get(player_id)
        if existing is not None:
            return existing
        created = self.bot_builder(self.bot_names[player_id], player_id)
        self._instances[player_id] = created
        return created

    def notify_new_game(self) -> None:
        for player_id in PLAYER_IDS:
            self.private_memory_for_player(player_id).on_new_game()
        for player_id in self.configured_players():
            bot = self.bot_for_player(player_id)
            hook = getattr(bot, "on_new_game", None)
            if callable(hook):
                hook()

    def notify_new_hand(self, state: GameState) -> None:
        for player_id in PLAYER_IDS:
            self.private_memory_for_player(player_id).on_new_hand(state)
        for player_id in self.configured_players():
            bot = self.bot_for_player(player_id)
            hook = getattr(bot, "on_new_hand", None)
            if callable(hook):
                hook(state)

    def private_memory_for_player(self, player_id: PlayerId) -> SeatPrivateMemory:
        if player_id not in PLAYER_IDS:
            raise ValueError(f"Unsupported player id for private memory: {player_id!r}")
        existing = self._private_memory_by_player.get(player_id)
        if existing is not None:
            return existing
        created = SeatPrivateMemory(player_id=player_id)
        self._private_memory_by_player[player_id] = created
        return created

    def private_knowledge_for_player(self, player_id: PlayerId) -> SeatPrivateKnowledge:
        return self.private_memory_for_player(player_id).snapshot()

    def record_pass_selection(
        self,
        *,
        player_id: PlayerId,
        state: GameState,
        selected_cards: Sequence[Card],
    ) -> None:
        memory = self.private_memory_for_player(player_id)
        recipient = memory.record_own_pass(state=state, selected_cards=selected_cards)
        if player_id not in self.bot_names:
            return
        bot = self.bot_for_player(player_id)
        hook = getattr(bot, "on_own_pass_selected", None)
        if callable(hook):
            hook(
                state=state,
                selected_cards=tuple(selected_cards),
                recipient=recipient,
            )

    def record_pass_map(
        self,
        *,
        state: GameState,
        pass_map: Mapping[PlayerId, Sequence[Card]],
    ) -> None:
        for player_id, selected_cards in pass_map.items():
            self.record_pass_selection(
                player_id=player_id,
                state=state,
                selected_cards=selected_cards,
            )

    def clear_instances(self) -> None:
        self._instances.clear()


__all__ = [
    "BotBuilder",
    "BotRuntimeSession",
    "SupportsNewGame",
    "SupportsNewHand",
    "SupportsOwnPassSelected",
]
