from __future__ import annotations

import pytest

from hearts_ai.benchmarking import (
    DEFAULT_SEARCH_BENCHMARK_PRESET,
    DEFAULT_SEARCH_WORLD_COUNTS,
    available_search_benchmark_preset_names,
    benchmark_search_world_counts,
    build_search_benchmark_lineups,
    parse_search_world_counts,
    resolve_search_benchmark_preset,
)


def test_parse_search_world_counts_defaults_and_validation() -> None:
    assert parse_search_world_counts(None) == DEFAULT_SEARCH_WORLD_COUNTS
    assert parse_search_world_counts("") == DEFAULT_SEARCH_WORLD_COUNTS
    assert parse_search_world_counts("1, 2,4") == (1, 2, 4)

    with pytest.raises(ValueError):
        parse_search_world_counts("0,2")


def test_search_benchmark_presets_are_available_and_resolvable() -> None:
    assert available_search_benchmark_preset_names() == (
        "all_search_v1",
        "mixed_search_field",
        "search_vs_heuristic_v3_field",
    )

    preset = resolve_search_benchmark_preset(DEFAULT_SEARCH_BENCHMARK_PRESET)
    assert preset.name == "mixed_search_field"
    assert preset.bot_names == ("search_v1", "heuristic_v3", "heuristic_v2", "heuristic")

    with pytest.raises(ValueError):
        resolve_search_benchmark_preset("unknown")


def test_build_search_benchmark_lineups_uses_unique_permutations() -> None:
    mixed_lineups = build_search_benchmark_lineups(preset_name="mixed_search_field", games=24)
    primary_lineups = build_search_benchmark_lineups(
        preset_name="search_vs_heuristic_v3_field",
        games=4,
    )

    assert len(set(mixed_lineups)) == 24
    assert len(set(primary_lineups)) == 4
    assert len(build_search_benchmark_lineups(preset_name="all_search_v1", games=3)) == 3
    assert len(set(build_search_benchmark_lineups(preset_name="all_search_v1", games=3))) == 1


def test_benchmark_search_world_counts_is_deterministic() -> None:
    first = benchmark_search_world_counts(
        seed=11,
        games=1,
        target_score=15,
        preset_name="mixed_search_field",
        world_counts=(1, 2),
    )
    second = benchmark_search_world_counts(
        seed=11,
        games=1,
        target_score=15,
        preset_name="mixed_search_field",
        world_counts=(1, 2),
    )

    assert _normalize_elapsed(first) == _normalize_elapsed(second)
    assert first[0] == (
        "SEARCH BENCHMARK GAMES 1 SEED_START 11 TARGET 15 "
        "PRESET mixed_search_field WORLD_COUNTS 1,2 "
        "BASE_BOTS search_v1,heuristic_v3,heuristic_v2,heuristic"
    )
    assert first[1].startswith("WORLD_COUNT 1 UNIQUE_LINEUPS 24 ELAPSED_SECONDS ")
    assert "GAMES_PER_LINEUP uneven" in first[1]
    assert first[2].startswith("BOT search_v1 OCCURRENCES 1 WIN_RATE ")
    assert first[6].startswith("WORLD_COUNT 2 UNIQUE_LINEUPS 24 ELAPSED_SECONDS ")


def _normalize_elapsed(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    for line in lines:
        if "ELAPSED_SECONDS " not in line:
            normalized.append(line)
            continue
        before, _, after = line.partition("ELAPSED_SECONDS ")
        _, _, tail = after.partition(" ")
        normalized.append(f"{before}ELAPSED_SECONDS <elapsed> {tail}".rstrip())
    return normalized
