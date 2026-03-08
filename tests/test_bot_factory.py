import pytest

from hearts_ai.bots.factory import (
    available_bot_names,
    create_bot,
    create_bots,
    normalize_bot_name,
    resolve_bot_names,
)
from hearts_ai.bots.heuristic_bot import HeuristicBot, HeuristicBotV2
from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.engine.types import PLAYER_IDS, PlayerId


def test_available_bot_names_contains_heuristics_and_random() -> None:
    assert available_bot_names() == ("heuristic", "heuristic_v2", "random")


def test_resolve_bot_names_single_value_applies_to_all_players() -> None:
    names = resolve_bot_names("random")
    assert names == ("random", "random", "random", "random")


def test_resolve_bot_names_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        resolve_bot_names("random,unknown,random,random")


def test_create_bots_builds_four_bots() -> None:
    bots = create_bots(("random", "random", "random", "random"))
    assert set(bots.keys()) == set(PLAYER_IDS)
    assert all(isinstance(bots[player_id], RandomBot) for player_id in PLAYER_IDS)


def test_create_bots_supports_heuristic() -> None:
    bots = create_bots(("heuristic", "heuristic", "heuristic", "heuristic"))
    assert set(bots.keys()) == set(PLAYER_IDS)
    assert all(isinstance(bots[player_id], HeuristicBot) for player_id in PLAYER_IDS)


def test_create_bots_supports_heuristic_v2() -> None:
    bots = create_bots(("heuristic_v2", "heuristic_v2", "heuristic_v2", "heuristic_v2"))
    assert set(bots.keys()) == set(PLAYER_IDS)
    assert all(isinstance(bots[player_id], HeuristicBotV2) for player_id in PLAYER_IDS)


def test_create_bot_supports_mixed_case_name() -> None:
    bot = create_bot("Heuristic", player_id=PlayerId(0))
    assert isinstance(bot, HeuristicBot)


def test_create_bot_supports_heuristic_v2_name() -> None:
    bot = create_bot("Heuristic_V2", player_id=PlayerId(0))
    assert isinstance(bot, HeuristicBotV2)


def test_normalize_bot_name_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        normalize_bot_name("not-a-bot")
