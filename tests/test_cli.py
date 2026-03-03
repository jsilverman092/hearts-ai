import pytest

from hearts_ai.cli import main, simulate_games


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
