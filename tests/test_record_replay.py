import re
from pathlib import Path

import pytest

from hearts_ai.cli import main, simulate_games
from hearts_ai.engine.record import replay_jsonl
from hearts_ai.engine.types import PLAYER_IDS


def _scores_from_final_line(final_line: str) -> dict[int, int]:
    matches = re.findall(r"P([0-3])=(\d+)", final_line)
    if len(matches) != 4:
        raise AssertionError(f"Could not parse full score payload from line: {final_line!r}")
    return {int(player): int(score) for player, score in matches}


def test_recorded_game_replays_to_matching_final_scores(tmp_path: Path) -> None:
    record_path = tmp_path / "game_record.jsonl"
    lines = simulate_games(seed=7, games=1, target_score=50, record_path=str(record_path))
    final_lines = [line for line in lines if " FINAL " in line]
    assert len(final_lines) == 1

    expected_scores = _scores_from_final_line(final_lines[0])
    replayed = replay_jsonl(record_path)
    assert len(replayed) == 1

    _, replayed_state = replayed[0]
    actual_scores = {int(player_id): replayed_state.scores[player_id] for player_id in PLAYER_IDS}
    assert actual_scores == expected_scores


def test_cli_replay_prints_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record_path = tmp_path / "game_record.jsonl"
    simulate_games(seed=5, games=1, target_score=40, record_path=str(record_path))

    exit_code = main(["replay", str(record_path)])
    output = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert len(output) == 1
    assert output[0].startswith("REPLAY game-1 HANDS ")
    assert " FINAL " in output[0]

