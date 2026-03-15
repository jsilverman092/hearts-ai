import pytest

import hearts_ai.cli as cli_module
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS
from hearts_ai.cli import benchmark_games, main, simulate_games


def test_simulate_games_is_deterministic() -> None:
    first = simulate_games(seed=1, games=1, target_score=50)
    second = simulate_games(seed=1, games=1, target_score=50)

    assert first == second
    assert any(" FINAL " in line for line in first)


def test_cli_main_play_prints_expected_lines(capsys: pytest.CaptureFixture[str]) -> None:
    expected = simulate_games(seed=2, games=1, target_score=50)
    exit_code = main(["play", "--seed", "2", "--games", "1", "--target-score", "50"])
    captured = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert captured == expected


def test_simulate_games_supports_multiple_games() -> None:
    lines = simulate_games(seed=3, games=2, target_score=30)
    final_lines = [line for line in lines if " FINAL " in line]

    assert len(final_lines) == 2


def test_simulate_games_explicit_random_bot_matches_default() -> None:
    default_lines = simulate_games(seed=4, games=1, target_score=50)
    explicit_lines = simulate_games(seed=4, games=1, target_score=50, bot_spec="random")

    assert explicit_lines == default_lines


def test_simulate_games_is_deterministic_with_heuristic_bots() -> None:
    first = simulate_games(seed=5, games=1, target_score=50, bot_spec="heuristic")
    second = simulate_games(seed=5, games=1, target_score=50, bot_spec="heuristic")

    assert first == second
    assert any(" FINAL " in line for line in first)


def test_simulate_games_rejects_invalid_bot_spec() -> None:
    with pytest.raises(ValueError):
        simulate_games(seed=1, games=1, target_score=50, bot_spec="random,random")


def test_benchmark_games_is_deterministic() -> None:
    first = benchmark_games(seed=8, games=10, target_score=50, bot_spec="random")
    second = benchmark_games(seed=8, games=10, target_score=50, bot_spec="random")

    assert first == second
    assert first[0] == "BENCHMARK GAMES 10 SEED_START 8 TARGET 50 BOTS random,random,random,random"
    assert len(first) == 5


def test_cli_main_benchmark_prints_expected_lines(capsys: pytest.CaptureFixture[str]) -> None:
    expected = benchmark_games(seed=3, games=5, target_score=40, bot_spec="random")
    exit_code = main(
        ["benchmark", "--seed", "3", "--games", "5", "--target-score", "40", "--bots", "random"]
    )
    captured = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert captured == expected


def test_benchmark_games_supports_heuristic_bot_name() -> None:
    lines = benchmark_games(seed=2, games=3, target_score=30, bot_spec="heuristic")
    assert lines[0] == "BENCHMARK GAMES 3 SEED_START 2 TARGET 30 BOTS heuristic,heuristic,heuristic,heuristic"


def test_benchmark_games_supports_heuristic_v2_bot_name() -> None:
    lines = benchmark_games(seed=2, games=3, target_score=30, bot_spec="heuristic_v2")
    assert lines[0] == (
        "BENCHMARK GAMES 3 SEED_START 2 TARGET 30 "
        "BOTS heuristic_v2,heuristic_v2,heuristic_v2,heuristic_v2"
    )


def test_benchmark_games_supports_heuristic_v3_bot_name() -> None:
    lines = benchmark_games(seed=2, games=3, target_score=30, bot_spec="heuristic_v3")
    assert lines[0] == (
        "BENCHMARK GAMES 3 SEED_START 2 TARGET 30 "
        "BOTS heuristic_v3,heuristic_v3,heuristic_v3,heuristic_v3"
    )


def test_simulate_games_notifies_runtime_session_for_initial_and_dealt_hands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _SpyRuntimeSession:
        def __init__(self) -> None:
            self.events: list[str] = []

        def notify_new_game(self) -> None:
            self.events.append("game")

        def notify_new_hand(self, state: GameState) -> None:
            self.events.append(f"hand:{state.hand_number}")

        def bot_for_player(self, player_id):  # pragma: no cover - should not be reached in this test
            raise AssertionError(f"bot_for_player should not be called for player {player_id!r}")

    spy = _SpyRuntimeSession()

    class _SpyRuntimeFactory:
        @classmethod
        def from_bot_names(cls, bot_names):
            assert tuple(bot_names) == ("random", "random", "random", "random")
            return spy

    def _fake_new_game(*, rng, config):
        del rng
        state = GameState(config=config)
        state.hand_number = 1
        state.pass_direction = "left"
        state.pass_applied = True
        state.scores = {player_id: 0 for player_id in PLAYER_IDS}
        return state

    def _fake_play_hand(*, state, runtime_session, rng, recorder=None):
        del state, runtime_session, rng, recorder

    game_over_calls = {"count": 0}

    def _fake_is_game_over(state):
        del state
        game_over_calls["count"] += 1
        return game_over_calls["count"] >= 2

    def _fake_deal(*, state, rng):
        del rng
        state.hand_number += 1
        state.pass_direction = "right"
        state.pass_applied = True

    monkeypatch.setattr(cli_module, "BotRuntimeSession", _SpyRuntimeFactory)
    monkeypatch.setattr(cli_module, "resolve_bot_names", lambda bot_spec: ("random",) * 4)
    monkeypatch.setattr(cli_module, "new_game", _fake_new_game)
    monkeypatch.setattr(cli_module, "_play_hand", _fake_play_hand)
    monkeypatch.setattr(cli_module, "is_game_over", _fake_is_game_over)
    monkeypatch.setattr(cli_module, "deal", _fake_deal)

    simulate_games(seed=1, games=1, target_score=50)

    assert spy.events == ["game", "hand:1", "hand:2"]
