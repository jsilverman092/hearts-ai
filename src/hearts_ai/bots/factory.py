from __future__ import annotations

from collections.abc import Sequence

from hearts_ai.bots.base import Bot
from hearts_ai.bots.heuristic_bot import HeuristicBot
from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.engine.types import PLAYER_COUNT, PLAYER_IDS, PlayerId

_BOT_BUILDERS = {
    "heuristic": HeuristicBot,
    "random": RandomBot,
}


def available_bot_names() -> tuple[str, ...]:
    return tuple(sorted(_BOT_BUILDERS))


def resolve_bot_names(bot_spec: str | None) -> tuple[str, ...]:
    if bot_spec is None or not bot_spec.strip():
        names = ["random"] * PLAYER_COUNT
    else:
        tokens = [token.strip().lower() for token in bot_spec.split(",")]
        names = [token for token in tokens if token]
        if len(names) == 1:
            names = names * PLAYER_COUNT

    if len(names) != PLAYER_COUNT:
        raise ValueError(
            f"Expected either 1 bot name or {PLAYER_COUNT} comma-separated names, got {len(names)}."
        )

    unknown = sorted({name for name in names if name not in _BOT_BUILDERS})
    if unknown:
        available = ", ".join(available_bot_names())
        raise ValueError(f"Unknown bot name(s): {', '.join(unknown)}. Available: {available}.")

    return tuple(names)


def create_bots(bot_names: Sequence[str]) -> dict[PlayerId, Bot]:
    if len(bot_names) != PLAYER_COUNT:
        raise ValueError(f"Expected {PLAYER_COUNT} bot names, got {len(bot_names)}.")

    return {
        player_id: _BOT_BUILDERS[bot_names[index]](player_id=player_id)
        for index, player_id in enumerate(PLAYER_IDS)
    }


__all__ = ["available_bot_names", "create_bots", "resolve_bot_names"]
