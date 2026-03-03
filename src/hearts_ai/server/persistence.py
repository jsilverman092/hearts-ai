from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from hearts_ai.engine.record import GameRecorder
from hearts_ai.engine.state import GameConfig


@dataclass(slots=True)
class RecordStore:
    records_dir: Path | str = "records"
    summary_filename: str = "summaries.jsonl"

    def __post_init__(self) -> None:
        self.records_dir = Path(self.records_dir)
        self.records_dir.mkdir(parents=True, exist_ok=True)

    @property
    def summary_path(self) -> Path:
        return self.records_dir / self.summary_filename

    def create_game_recorder(
        self,
        *,
        table_code: str,
        seed: int,
        config: GameConfig,
    ) -> tuple[GameRecorder, Path, str]:
        game_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        game_id = f"{table_code}-{game_stamp}"
        record_path = self.records_dir / f"{game_id}.jsonl"
        recorder = GameRecorder(path=record_path, game_id=game_id, table_id=table_code)
        recorder.record_game_created(config=config, seed=seed)
        return recorder, record_path, game_id

    def write_game_summary(
        self,
        *,
        table_code: str,
        game_id: str,
        seed: int,
        target_score: int,
        hands_played: int,
        final_scores: Mapping[str, int],
        winner_ids: list[int],
        record_path: str | None,
    ) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "table_code": table_code,
            "game_id": game_id,
            "seed": seed,
            "target_score": target_score,
            "hands_played": hands_played,
            "final_scores": dict(final_scores),
            "winner_ids": list(winner_ids),
            "record_path": record_path,
        }
        _append_jsonl(self.summary_path, payload)


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(payload), separators=(",", ":"), sort_keys=True))
        handle.write("\n")


__all__ = ["RecordStore"]

