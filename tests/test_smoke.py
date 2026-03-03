from hearts_ai import __version__
from hearts_ai.cli import simulate_games


def test_version_string_exists() -> None:
    assert isinstance(__version__, str)
    assert __version__


def test_full_game_simulation_smoke_fixed_seed() -> None:
    lines = simulate_games(seed=1, games=1, target_score=50)

    assert lines
    assert lines[-1] == "GAME 1 FINAL P0=49 P1=30 P2=51 P3=52 WINNER P1"
