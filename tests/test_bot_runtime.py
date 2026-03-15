from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from hearts_ai.bots.runtime import BotRuntimeSession
from hearts_ai.engine.cards import Card
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId


@dataclass(slots=True)
class _FakeBot:
    player_id: PlayerId
    game_notifications: int = 0
    hand_notifications: list[int] = field(default_factory=list)

    def choose_pass(self, hand, state, rng) -> list[Card]:
        del hand, state, rng
        return []

    def choose_play(self, state, rng) -> Card:
        del state, rng
        raise AssertionError("choose_play should not be called in bot runtime tests.")

    def on_new_game(self) -> None:
        self.game_notifications += 1

    def on_new_hand(self, state: GameState) -> None:
        self.hand_notifications.append(state.hand_number)


def _fake_builder(bot_name: str, player_id: PlayerId) -> _FakeBot:
    return _FakeBot(player_id=player_id)


def test_bot_runtime_session_reuses_same_instance_per_player() -> None:
    session = BotRuntimeSession.from_bot_names(
        ("random", "heuristic", "heuristic_v2", "heuristic_v3"),
        bot_builder=_fake_builder,
    )

    first = session.bot_for_player(PlayerId(0))
    second = session.bot_for_player(PlayerId(0))

    assert first is second


def test_bot_runtime_session_notifies_all_configured_bots_for_new_game_and_hand() -> None:
    session = BotRuntimeSession(
        bot_names={
            PlayerId(1): "heuristic_v3",
            PlayerId(3): "random",
        },
        bot_builder=_fake_builder,
    )
    state = GameState()
    state.hand_number = 4

    session.notify_new_game()
    session.notify_new_hand(state)

    bot_one = session.bot_for_player(PlayerId(1))
    bot_three = session.bot_for_player(PlayerId(3))

    assert bot_one.game_notifications == 1
    assert bot_three.game_notifications == 1
    assert bot_one.hand_notifications == [4]
    assert bot_three.hand_notifications == [4]


def test_bot_runtime_session_clear_instances_recreates_bots() -> None:
    session = BotRuntimeSession.from_bot_names(
        ("random", "random", "random", "random"),
        bot_builder=_fake_builder,
    )

    original = session.bot_for_player(PlayerId(2))
    session.clear_instances()
    recreated = session.bot_for_player(PlayerId(2))

    assert original is not recreated


def test_bot_runtime_session_rejects_unconfigured_player() -> None:
    session = BotRuntimeSession(
        bot_names={PlayerId(1): "heuristic_v3"},
        bot_builder=_fake_builder,
    )

    with pytest.raises(ValueError):
        session.bot_for_player(PlayerId(0))


def test_bot_runtime_session_configured_players_follow_table_order() -> None:
    session = BotRuntimeSession(
        bot_names={
            PlayerId(3): "random",
            PlayerId(1): "heuristic_v2",
        },
        bot_builder=_fake_builder,
    )

    assert session.configured_players() == (PlayerId(1), PlayerId(3))


def test_bot_runtime_session_from_bot_names_requires_full_table_length() -> None:
    with pytest.raises(ValueError):
        BotRuntimeSession.from_bot_names(("random",) * (len(PLAYER_IDS) - 1), bot_builder=_fake_builder)
