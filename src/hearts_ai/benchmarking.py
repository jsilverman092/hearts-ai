from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import permutations
from time import perf_counter
from typing import Literal

from hearts_ai.bots.factory import create_bot
from hearts_ai.bots.runtime import BotBuilder, BotRuntimeSession
from hearts_ai.bots.search import SearchBotConfig, SearchBotV1
from hearts_ai.engine.game import apply_pass, deal, is_game_over, is_hand_over, new_game, play_card
from hearts_ai.engine.state import GameConfig
from hearts_ai.engine.types import PLAYER_COUNT, PLAYER_IDS, PlayerId

SearchBenchmarkPresetName = Literal[
    "all_search_v1",
    "mixed_search_field",
    "search_vs_heuristic_v3_field",
]

DEFAULT_SEARCH_BENCHMARK_PRESET: SearchBenchmarkPresetName = "mixed_search_field"
DEFAULT_SEARCH_WORLD_COUNTS: tuple[int, ...] = (1, 2, 4, 8)


@dataclass(frozen=True, slots=True)
class BenchmarkSeatSummary:
    player_id: PlayerId
    bot_name: str
    win_rate: float
    average_points: float
    average_rank: float


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    games: int
    seed_start: int
    target_score: int
    bot_names: tuple[str, ...]
    seats: tuple[BenchmarkSeatSummary, ...]


@dataclass(frozen=True, slots=True)
class SearchBenchmarkPreset:
    name: SearchBenchmarkPresetName
    description: str
    bot_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SearchBenchmarkBotSummary:
    bot_name: str
    occurrences: int
    win_rate: float
    average_points: float
    average_rank: float


@dataclass(frozen=True, slots=True)
class SearchBenchmarkSummary:
    games: int
    seed_start: int
    target_score: int
    preset_name: str
    base_bot_names: tuple[str, ...]
    unique_lineup_count: int
    games_per_lineup: int | None
    lineups: tuple[tuple[str, ...], ...]
    bots: tuple[SearchBenchmarkBotSummary, ...]


_SEARCH_BENCHMARK_PRESETS: dict[SearchBenchmarkPresetName, SearchBenchmarkPreset] = {
    "all_search_v1": SearchBenchmarkPreset(
        name="all_search_v1",
        description="All four seats run search_v1 for self-play sweeps.",
        bot_names=("search_v1", "search_v1", "search_v1", "search_v1"),
    ),
    "mixed_search_field": SearchBenchmarkPreset(
        name="mixed_search_field",
        description="search_v1 against heuristic_v3, heuristic_v2, and heuristic.",
        bot_names=("search_v1", "heuristic_v3", "heuristic_v2", "heuristic"),
    ),
    "search_vs_heuristic_v3_field": SearchBenchmarkPreset(
        name="search_vs_heuristic_v3_field",
        description="search_v1 against three heuristic_v3 seats.",
        bot_names=("search_v1", "heuristic_v3", "heuristic_v3", "heuristic_v3"),
    ),
}


def available_search_benchmark_preset_names() -> tuple[str, ...]:
    return tuple(sorted(_SEARCH_BENCHMARK_PRESETS))


def resolve_search_benchmark_preset(name: str) -> SearchBenchmarkPreset:
    normalized = name.strip().lower()
    try:
        preset = _SEARCH_BENCHMARK_PRESETS[normalized]
    except KeyError as exc:
        available = ", ".join(available_search_benchmark_preset_names())
        raise ValueError(f"Unknown search benchmark preset: {name!r}. Available: {available}.") from exc
    return preset


def parse_search_world_counts(world_counts_spec: str | None) -> tuple[int, ...]:
    if world_counts_spec is None or not world_counts_spec.strip():
        return DEFAULT_SEARCH_WORLD_COUNTS

    tokens = [token.strip() for token in world_counts_spec.split(",")]
    parsed = tuple(int(token) for token in tokens if token)
    if not parsed:
        raise ValueError("Expected at least one search world count.")
    if any(world_count <= 0 for world_count in parsed):
        raise ValueError(f"search world counts must all be > 0, got {parsed!r}")
    return parsed


def run_benchmark_summary(
    *,
    seed: int,
    games: int,
    target_score: int,
    bot_names: tuple[str, ...],
    bot_builder: BotBuilder | None = None,
) -> BenchmarkSummary:
    if games <= 0:
        raise ValueError(f"games must be > 0, got {games}")
    if target_score <= 0:
        raise ValueError(f"target_score must be > 0, got {target_score}")
    if len(bot_names) != PLAYER_COUNT:
        raise ValueError(f"Expected {PLAYER_COUNT} bot names, got {len(bot_names)}.")

    runtime_builder = bot_builder if bot_builder is not None else _default_benchmark_bot_builder
    wins = {player_id: 0.0 for player_id in PLAYER_IDS}
    total_points = {player_id: 0 for player_id in PLAYER_IDS}
    total_ranks = {player_id: 0.0 for player_id in PLAYER_IDS}

    for offset in range(games):
        rng = random.Random(seed + offset)
        state = new_game(rng=rng, config=GameConfig(target_score=target_score))
        runtime_session = BotRuntimeSession.from_bot_names(bot_names, bot_builder=runtime_builder)
        runtime_session.notify_new_game()
        runtime_session.notify_new_hand(state)

        while True:
            _play_hand_to_completion(state=state, runtime_session=runtime_session, rng=rng)
            if is_game_over(state):
                break
            deal(state=state, rng=rng)
            runtime_session.notify_new_hand(state)

        winners = _winner_ids(state.scores)
        winner_share = 1.0 / len(winners)
        for winner in winners:
            wins[PlayerId(winner)] += winner_share
        ranks = _average_ranks(state.scores)
        for player_id in PLAYER_IDS:
            total_points[player_id] += state.scores[player_id]
            total_ranks[player_id] += ranks[player_id]

    return BenchmarkSummary(
        games=games,
        seed_start=seed,
        target_score=target_score,
        bot_names=bot_names,
        seats=tuple(
            BenchmarkSeatSummary(
                player_id=player_id,
                bot_name=bot_names[int(player_id)],
                win_rate=wins[player_id] / games,
                average_points=total_points[player_id] / games,
                average_rank=total_ranks[player_id] / games,
            )
            for player_id in PLAYER_IDS
        ),
    )


def format_benchmark_summary(summary: BenchmarkSummary) -> list[str]:
    output_lines = [
        f"BENCHMARK GAMES {summary.games} SEED_START {summary.seed_start} TARGET {summary.target_score} "
        f"BOTS {','.join(summary.bot_names)}"
    ]
    for seat in summary.seats:
        output_lines.append(
            f"P{int(seat.player_id)} BOT {seat.bot_name} "
            f"WIN_RATE {seat.win_rate:.3f} "
            f"AVG_POINTS {seat.average_points:.3f} "
            f"AVG_RANK {seat.average_rank:.3f}"
        )
    return output_lines


def build_search_benchmark_lineups(
    *,
    preset_name: str,
    games: int,
) -> tuple[tuple[str, ...], ...]:
    if games <= 0:
        raise ValueError(f"games must be > 0, got {games}")
    preset = resolve_search_benchmark_preset(preset_name)
    unique_lineups = _unique_lineups(preset.bot_names)
    return tuple(unique_lineups[index % len(unique_lineups)] for index in range(games))


def run_search_benchmark_summary(
    *,
    seed: int,
    games: int,
    target_score: int,
    preset_name: str,
    world_count: int,
) -> SearchBenchmarkSummary:
    if games <= 0:
        raise ValueError(f"games must be > 0, got {games}")
    if target_score <= 0:
        raise ValueError(f"target_score must be > 0, got {target_score}")
    if world_count <= 0:
        raise ValueError(f"world_count must be > 0, got {world_count}")

    preset = resolve_search_benchmark_preset(preset_name)
    lineups = build_search_benchmark_lineups(preset_name=preset_name, games=games)
    unique_lineup_count = len(_unique_lineups(preset.bot_names))
    games_per_lineup = games // unique_lineup_count if games % unique_lineup_count == 0 else None
    bot_builder = _search_world_count_bot_builder(world_count=world_count)
    unique_bot_names = tuple(dict.fromkeys(preset.bot_names))
    wins = {bot_name: 0.0 for bot_name in unique_bot_names}
    total_points = {bot_name: 0.0 for bot_name in unique_bot_names}
    total_ranks = {bot_name: 0.0 for bot_name in unique_bot_names}
    occurrences = {bot_name: 0 for bot_name in unique_bot_names}

    for offset, bot_names in enumerate(lineups):
        rng = random.Random(seed + offset)
        state = new_game(rng=rng, config=GameConfig(target_score=target_score))
        runtime_session = BotRuntimeSession.from_bot_names(bot_names, bot_builder=bot_builder)
        runtime_session.notify_new_game()
        runtime_session.notify_new_hand(state)

        while True:
            _play_hand_to_completion(state=state, runtime_session=runtime_session, rng=rng)
            if is_game_over(state):
                break
            deal(state=state, rng=rng)
            runtime_session.notify_new_hand(state)

        winners = _winner_ids(state.scores)
        winner_share = 1.0 / len(winners)
        ranks = _average_ranks(state.scores)
        for player_id in PLAYER_IDS:
            bot_name = bot_names[int(player_id)]
            occurrences[bot_name] += 1
            total_points[bot_name] += state.scores[player_id]
            total_ranks[bot_name] += ranks[player_id]
            if int(player_id) in winners:
                wins[bot_name] += winner_share

    return SearchBenchmarkSummary(
        games=games,
        seed_start=seed,
        target_score=target_score,
        preset_name=preset.name,
        base_bot_names=preset.bot_names,
        unique_lineup_count=unique_lineup_count,
        games_per_lineup=games_per_lineup,
        lineups=lineups,
        bots=tuple(
            SearchBenchmarkBotSummary(
                bot_name=bot_name,
                occurrences=occurrences[bot_name],
                win_rate=wins[bot_name] / occurrences[bot_name],
                average_points=total_points[bot_name] / occurrences[bot_name],
                average_rank=total_ranks[bot_name] / occurrences[bot_name],
            )
            for bot_name in unique_bot_names
        ),
    )


def format_search_benchmark_summary(
    summary: SearchBenchmarkSummary,
    *,
    world_count: int,
    elapsed_seconds: float,
) -> list[str]:
    block_header = (
        f"WORLD_COUNT {world_count} UNIQUE_LINEUPS {summary.unique_lineup_count} "
        f"ELAPSED_SECONDS {elapsed_seconds:.3f}"
    )
    if summary.games_per_lineup is not None:
        block_header += f" GAMES_PER_LINEUP {summary.games_per_lineup}"
    else:
        block_header += " GAMES_PER_LINEUP uneven"

    output_lines = [block_header]
    for bot in summary.bots:
        output_lines.append(
            f"BOT {bot.bot_name} OCCURRENCES {bot.occurrences} "
            f"WIN_RATE {bot.win_rate:.3f} "
            f"AVG_POINTS {bot.average_points:.3f} "
            f"AVG_RANK {bot.average_rank:.3f}"
        )
    return output_lines


def benchmark_search_world_counts(
    *,
    seed: int,
    games: int,
    target_score: int,
    preset_name: str = DEFAULT_SEARCH_BENCHMARK_PRESET,
    world_counts: tuple[int, ...] = DEFAULT_SEARCH_WORLD_COUNTS,
) -> list[str]:
    preset = resolve_search_benchmark_preset(preset_name)
    if not world_counts:
        raise ValueError("Expected at least one search world count.")
    if any(world_count <= 0 for world_count in world_counts):
        raise ValueError(f"search world counts must all be > 0, got {world_counts!r}")

    output_lines = [
        f"SEARCH BENCHMARK GAMES {games} SEED_START {seed} TARGET {target_score} "
        f"PRESET {preset.name} WORLD_COUNTS {','.join(str(world_count) for world_count in world_counts)} "
        f"BASE_BOTS {','.join(preset.bot_names)}"
    ]
    for world_count in world_counts:
        start = perf_counter()
        summary = run_search_benchmark_summary(
            seed=seed,
            games=games,
            target_score=target_score,
            preset_name=preset.name,
            world_count=world_count,
        )
        elapsed_seconds = perf_counter() - start
        output_lines.extend(
            format_search_benchmark_summary(
                summary,
                world_count=world_count,
                elapsed_seconds=elapsed_seconds,
            )
        )
    return output_lines


def _play_hand_to_completion(
    *,
    state,
    runtime_session: BotRuntimeSession,
    rng: random.Random,
) -> None:
    if not state.pass_applied:
        pass_map = {
            player_id: runtime_session.bot_for_player(player_id).choose_pass(
                hand=state.hands[player_id],
                state=state,
                rng=rng,
            )
            for player_id in PLAYER_IDS
        }
        runtime_session.record_pass_map(state=state, pass_map=pass_map)
        apply_pass(state=state, pass_map=pass_map)

    while not is_hand_over(state):
        player_id = state.turn
        if player_id is None:
            raise ValueError("State turn is unset during active hand.")
        card = runtime_session.bot_for_player(player_id).choose_play(state=state, rng=rng)
        play_card(state=state, player_id=player_id, card=card)


def _default_benchmark_bot_builder(bot_name: str, player_id: PlayerId):
    return create_bot(bot_name, player_id=player_id)


def _search_world_count_bot_builder(*, world_count: int) -> BotBuilder:
    config = SearchBotConfig(world_count=world_count)

    def _builder(bot_name: str, player_id: PlayerId):
        if bot_name == "search_v1":
            return SearchBotV1(player_id=player_id, config=config)
        return create_bot(bot_name, player_id=player_id)

    return _builder


def _unique_lineups(bot_names: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    # `dict.fromkeys` preserves order while removing duplicates from repeated names.
    return tuple(dict.fromkeys(permutations(bot_names)))


def _winner_ids(scores: dict[PlayerId, int]) -> list[int]:
    best_score = min(scores.values())
    return [int(player_id) for player_id in PLAYER_IDS if scores[player_id] == best_score]


def _average_ranks(scores: dict[PlayerId, int]) -> dict[PlayerId, float]:
    sorted_scores = sorted(scores.values())
    ranks: dict[PlayerId, float] = {}
    for player_id in PLAYER_IDS:
        score = scores[player_id]
        positions = [index + 1 for index, current in enumerate(sorted_scores) if current == score]
        ranks[player_id] = sum(positions) / len(positions)
    return ranks


__all__ = [
    "BenchmarkSeatSummary",
    "BenchmarkSummary",
    "DEFAULT_SEARCH_BENCHMARK_PRESET",
    "DEFAULT_SEARCH_WORLD_COUNTS",
    "SearchBenchmarkBotSummary",
    "SearchBenchmarkPreset",
    "SearchBenchmarkSummary",
    "available_search_benchmark_preset_names",
    "benchmark_search_world_counts",
    "build_search_benchmark_lineups",
    "format_benchmark_summary",
    "format_search_benchmark_summary",
    "parse_search_world_counts",
    "resolve_search_benchmark_preset",
    "run_benchmark_summary",
    "run_search_benchmark_summary",
]
