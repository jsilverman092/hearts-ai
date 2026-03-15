from __future__ import annotations

from dataclasses import dataclass

import pytest

from hearts_ai.bots.reasons import (
    DecisionReasonSerializerRegistry,
    peek_bot_decision_reason,
    serialize_bot_decision_reason,
    serialize_decision_reason,
)


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
