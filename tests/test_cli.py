import pytest

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
