import pytest

from hearts_ai.bots.factory import available_bot_names, create_bots, resolve_bot_names
from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.engine.types import PLAYER_IDS


def test_available_bot_names_contains_random() -> None:
    assert available_bot_names() == ("random",)


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
