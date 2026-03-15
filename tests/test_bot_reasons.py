from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from hearts_ai.bots.heuristic_bot import HeuristicBotV2, HeuristicBotV3
from hearts_ai.bots.search import SearchBotConfig, SearchBotV1
from hearts_ai.bots.reasons import (
    DecisionReasonSerializerRegistry,
    peek_bot_decision_reason,
    serialize_bot_decision_reason,
    serialize_decision_reason,
)
from hearts_ai.engine.game import new_game
from hearts_ai.engine.cards import make_deck
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PlayerId


@dataclass(frozen=True)
class _BaseReason:
    label: str


@dataclass(frozen=True)
class _DerivedReason(_BaseReason):
    score: int


class _FakeReasonBot:
    def __init__(self, *, pass_reason: object | None = None, play_reason: object | None = None) -> None:
        self._pass_reason = pass_reason
        self._play_reason = play_reason

    def peek_last_decision_reason(self, decision_kind: str) -> object | None:
        if decision_kind == "pass":
            return self._pass_reason
        if decision_kind == "play":
            return self._play_reason
        raise AssertionError(f"Unexpected decision kind: {decision_kind}")


def _expected_pass_payload(reason) -> dict[str, object]:
    return {
        "selected_cards": [str(card) for card in reason.selected_cards],
        "candidates": [
            {
                "card": str(candidate.card),
                "score": [int(value) for value in candidate.score],
            }
            for candidate in reason.candidates
        ],
    }


def _expected_play_payload(reason) -> dict[str, object]:
    return {
        "mode": str(reason.mode),
        "chosen_card": str(reason.chosen_card),
        "moon_defense_target": int(reason.moon_defense_target) if reason.moon_defense_target is not None else None,
        "candidates": [
            {
                "card": str(candidate.card),
                "base_score": float(candidate.base_score),
                "rollout_score": float(candidate.rollout_score),
                "total_score": float(candidate.total_score),
                "tags": [str(tag) for tag in candidate.tags],
            }
            for candidate in reason.candidates
        ],
    }


def test_reason_serializer_registry_serializes_exact_registered_type() -> None:
    registry = DecisionReasonSerializerRegistry()
    registry.register(_BaseReason, lambda reason: {"label": reason.label})

    payload = registry.serialize(_BaseReason(label="exact"))

    assert payload == {"label": "exact"}


def test_reason_serializer_registry_uses_parent_serializer_for_subclass() -> None:
    registry = DecisionReasonSerializerRegistry()
    registry.register(_BaseReason, lambda reason: {"label": reason.label})

    payload = registry.serialize(_DerivedReason(label="child", score=9))

    assert payload == {"label": "child"}


def test_reason_serializer_registry_rejects_duplicate_registration() -> None:
    registry = DecisionReasonSerializerRegistry()
    registry.register(_BaseReason, lambda reason: {"label": reason.label})

    with pytest.raises(ValueError):
        registry.register(_BaseReason, lambda reason: {"other": reason.label})


def test_peek_bot_decision_reason_returns_none_when_bot_has_no_reason_interface() -> None:
    assert peek_bot_decision_reason(object(), "play") is None


def test_serialize_bot_decision_reason_serializes_supported_bot_reason() -> None:
    registry = DecisionReasonSerializerRegistry()
    registry.register(_DerivedReason, lambda reason: {"label": reason.label, "score": reason.score})
    bot = _FakeReasonBot(play_reason=_DerivedReason(label="play", score=4))

    payload = serialize_bot_decision_reason(bot, "play", registry=registry)

    assert payload == {"label": "play", "score": 4}


def test_serialize_bot_decision_reason_returns_none_for_unregistered_reason_type() -> None:
    bot = _FakeReasonBot(pass_reason=_BaseReason(label="pass"))

    payload = serialize_bot_decision_reason(bot, "pass", registry=DecisionReasonSerializerRegistry())

    assert payload is None


def test_serialize_decision_reason_returns_none_for_unregistered_reason_type() -> None:
    payload = serialize_decision_reason(_BaseReason(label="standalone"), registry=DecisionReasonSerializerRegistry())

    assert payload is None


def test_heuristic_v3_pass_reason_uses_generic_boundary_without_payload_change() -> None:
    state = new_game(rng=random.Random(17))
    bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0)

    passed = bot.choose_pass(hand=state.hands[PlayerId(0)], state=state, rng=random.Random(23))
    legacy_reason = bot._peek_last_pass_reason()

    assert legacy_reason is not None
    assert peek_bot_decision_reason(bot, "pass") is legacy_reason
    assert serialize_bot_decision_reason(bot, "pass") == _expected_pass_payload(legacy_reason)
    assert _expected_pass_payload(legacy_reason)["selected_cards"] == [str(card) for card in passed]


def test_heuristic_v2_play_reason_uses_generic_boundary_without_payload_change() -> None:
    state = new_game(rng=random.Random(19))
    state.pass_applied = True
    assert state.turn is not None
    bot = HeuristicBotV2(player_id=state.turn, rollout_samples=0)

    chosen_card = bot.choose_play(state=state, rng=random.Random(29))
    legacy_reason = bot._peek_last_play_reason()

    assert legacy_reason is not None
    assert peek_bot_decision_reason(bot, "play") is legacy_reason
    assert serialize_bot_decision_reason(bot, "play") == _expected_play_payload(legacy_reason)
    assert _expected_play_payload(legacy_reason)["chosen_card"] == str(chosen_card)


def test_search_v1_play_reason_uses_generic_boundary() -> None:
    state = _full_search_state_with_rotating_hidden_hands(rotation=0)
    bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=2))

    chosen_card = bot.choose_play(state=state, rng=random.Random(37))
    reason = peek_bot_decision_reason(bot, "play")
    payload = serialize_bot_decision_reason(bot, "play")

    assert reason is not None
    assert payload is not None
    assert payload["chosen_card"] == str(chosen_card)
    assert payload["mode"] == "lead"
    assert payload["legal_move_count"] == 1
    assert payload["evaluated_candidate_count"] == 1
    assert payload["current_trick_size"] == 0
    assert payload["led_suit"] is None
    assert payload["requested_world_count"] == 2
    assert payload["world_count"] == 2
    assert payload["selection_source"] == "search"
    assert payload["fallback_message"] is None
    assert payload["baseline_comparison"] is not None
    assert payload["baseline_comparison"]["baseline_bot_name"] == "heuristic_v3"
    assert payload["baseline_comparison"]["agrees_with_search"] is True
    assert payload["baseline_comparison"]["baseline"]["card"] == str(chosen_card)
    assert payload["baseline_comparison"]["baseline"]["selection_rank"] == 1
    assert payload["baseline_comparison"]["mean_projected_score_delta_advantage"] == 0.0
    assert payload["baseline_comparison"]["mean_root_utility_gain"] == 0.0
    assert payload["baseline_comparison"]["worlds_search_better"] == 0
    assert payload["baseline_comparison"]["worlds_tied"] == 2
    assert payload["baseline_comparison"]["worlds_baseline_better"] == 0
    assert payload["chosen"]["card"] == str(chosen_card)
    assert payload["chosen"]["mode"] == "lead"
    assert payload["chosen"]["candidate_index"] == payload["candidates"][0]["candidate_index"]
    assert payload["chosen"]["average_projected_raw_hand_points"] == payload["candidates"][0]["average_projected_raw_hand_points"]
    assert payload["chosen"]["average_projected_score_delta"] == payload["candidates"][0]["average_projected_score_delta"]
    assert payload["chosen"]["average_projected_hand_points"] == payload["candidates"][0]["average_projected_hand_points"]
    assert payload["chosen"]["average_projected_total_score"] == payload["candidates"][0]["average_projected_total_score"]
    assert payload["chosen"]["average_root_utility"] == payload["candidates"][0]["average_root_utility"]
    assert payload["selection_policy"] == [
        "average_projected_score_delta",
        "average_projected_hand_points",
        "average_projected_total_score",
        "heuristic_v3_exact_tie_order",
        "candidate_index",
    ]
    assert isinstance(payload["candidates"], list)
    assert payload["candidates"][0]["selected"] is True
    assert payload["candidates"][0]["selection_rank"] == 1
    assert payload["candidates"][0]["card"] == str(chosen_card)


def _full_search_state_with_rotating_hidden_hands(*, rotation: int) -> GameState:
    deck = tuple(make_deck())
    own_hand = list(deck[:13])
    hidden_chunks = [
        list(deck[13:26]),
        list(deck[26:39]),
        list(deck[39:52]),
    ]
    hidden_chunks = hidden_chunks[rotation:] + hidden_chunks[:rotation]

    state = GameState()
    state.hands = {
        PlayerId(0): sorted(own_hand),
        PlayerId(1): sorted(hidden_chunks[0]),
        PlayerId(2): sorted(hidden_chunks[1]),
        PlayerId(3): sorted(hidden_chunks[2]),
    }
    state.taken_tricks = {PlayerId(index): [] for index in range(4)}
    state.scores = {PlayerId(index): 0 for index in range(4)}
    state.turn = PlayerId(0)
    state.trick_number = 0
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = True
    return state
