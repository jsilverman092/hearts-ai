from __future__ import annotations

import pytest

from hearts_ai.benchmarking import (
    DEFAULT_SEARCH_BENCHMARK_PRESET,
    DEFAULT_SEARCH_WORLD_COUNTS,
    available_search_benchmark_preset_names,
    benchmark_search_world_counts,
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
    assert available_search_benchmark_preset_names() == ("all_search_v1", "mixed_search_field")

    preset = resolve_search_benchmark_preset(DEFAULT_SEARCH_BENCHMARK_PRESET)
    assert preset.name == "mixed_search_field"
    assert preset.bot_names == ("search_v1", "heuristic_v3", "heuristic_v2", "random")

    with pytest.raises(ValueError):
        resolve_search_benchmark_preset("unknown")


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

    assert first == second
    assert first[0] == (
        "SEARCH BENCHMARK GAMES 1 SEED_START 11 TARGET 15 "
        "PRESET mixed_search_field WORLD_COUNTS 1,2 "
        "BOTS search_v1,heuristic_v3,heuristic_v2,random"
    )
    assert first[1] == "WORLD_COUNT 1 BOTS search_v1,heuristic_v3,heuristic_v2,random"
    assert first[6] == "WORLD_COUNT 2 BOTS search_v1,heuristic_v3,heuristic_v2,random"
