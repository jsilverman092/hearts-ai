from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from hearts_ai.bots.runtime import BotRuntimeSession
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId


@dataclass(slots=True)
class _FakeBot:
    player_id: PlayerId
    game_notifications: int = 0
    hand_notifications: list[int] = field(default_factory=list)
    own_pass_notifications: list[tuple[tuple[Card, ...], PlayerId | None]] = field(default_factory=list)

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

    def on_own_pass_selected(
        self,
        *,
        state: GameState,
        selected_cards: Sequence[Card],
        recipient: PlayerId | None,
    ) -> None:
        del state
        self.own_pass_notifications.append((tuple(selected_cards), recipient))


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


def test_bot_runtime_session_tracks_private_pass_memory_for_any_seat() -> None:
    session = BotRuntimeSession(
        bot_names={PlayerId(1): "heuristic_v3"},
        bot_builder=_fake_builder,
    )
    state = GameState()
    state.pass_direction = "across"
    queen_spades = Card(Suit.SPADES, Rank.QUEEN)

    session.record_pass_selection(
        player_id=PlayerId(0),
        state=state,
        selected_cards=[queen_spades],
    )
    snapshot = session.private_knowledge_for_player(PlayerId(0))

    assert snapshot.recipient_for_passed_card(queen_spades) == PlayerId(2)
    assert snapshot.has_passed_card(card=queen_spades, recipient=PlayerId(2)) is True


def test_bot_runtime_session_resets_private_pass_memory_between_hands_and_games() -> None:
    session = BotRuntimeSession.from_bot_names(
        ("random", "random", "random", "random"),
        bot_builder=_fake_builder,
    )
    state = GameState()
    queen_spades = Card(Suit.SPADES, Rank.QUEEN)

    session.record_pass_selection(
        player_id=PlayerId(3),
        state=state,
        selected_cards=[queen_spades],
    )
    assert session.private_knowledge_for_player(PlayerId(3)).has_passed_card(card=queen_spades) is True

    state.hand_number = 2
    session.notify_new_hand(state)
    assert session.private_knowledge_for_player(PlayerId(3)).has_passed_card(card=queen_spades) is False

    session.record_pass_selection(
        player_id=PlayerId(3),
        state=state,
        selected_cards=[queen_spades],
    )
    session.notify_new_game()
    assert session.private_knowledge_for_player(PlayerId(3)).has_passed_card(card=queen_spades) is False


def test_bot_runtime_session_notifies_configured_bot_when_own_pass_is_recorded() -> None:
    session = BotRuntimeSession(
        bot_names={PlayerId(2): "heuristic_v3"},
        bot_builder=_fake_builder,
    )
    state = GameState()
    state.pass_direction = "right"
    cards = [Card(Suit.CLUBS, Rank.THREE), Card(Suit.HEARTS, Rank.TEN)]

    session.record_pass_selection(
        player_id=PlayerId(2),
        state=state,
        selected_cards=cards,
    )
    bot = session.bot_for_player(PlayerId(2))

    assert bot.own_pass_notifications == [((Card(Suit.CLUBS, Rank.THREE), Card(Suit.HEARTS, Rank.TEN)), PlayerId(1))]
