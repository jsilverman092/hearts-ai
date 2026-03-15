from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias

DecisionKind = Literal["pass", "play"]
SerializedReasonPayload: TypeAlias = dict[str, Any]
DecisionReasonSerializer: TypeAlias = Callable[[Any], SerializedReasonPayload]


class SupportsDecisionReasonPeek(Protocol):
    """Optional bot interface for exposing the last opaque decision-reason object."""

    def peek_last_decision_reason(self, decision_kind: DecisionKind) -> object | None:
        ...


@dataclass(slots=True)
class DecisionReasonSerializerRegistry:
    """Registry that maps opaque reason object types to payload serializers."""

    _serializers: dict[type[Any], DecisionReasonSerializer] = field(default_factory=dict, repr=False)

    def register(self, reason_type: type[Any], serializer: DecisionReasonSerializer) -> None:
        if reason_type in self._serializers:
            raise ValueError(f"Serializer already registered for reason type {reason_type.__name__}.")
        self._serializers[reason_type] = serializer

    def serializer_for(self, reason: object) -> DecisionReasonSerializer | None:
        for candidate_type in type(reason).__mro__:
            serializer = self._serializers.get(candidate_type)
            if serializer is not None:
                return serializer
        return None

    def serialize(self, reason: object) -> SerializedReasonPayload | None:
        serializer = self.serializer_for(reason)
        if serializer is None:
            return None
        return serializer(reason)


_DEFAULT_REASON_SERIALIZER_REGISTRY = DecisionReasonSerializerRegistry()


def default_reason_serializer_registry() -> DecisionReasonSerializerRegistry:
    return _DEFAULT_REASON_SERIALIZER_REGISTRY


def register_default_reason_serializer(reason_type: type[Any], serializer: DecisionReasonSerializer) -> None:
    default_reason_serializer_registry().register(reason_type, serializer)


def peek_bot_decision_reason(bot: object, decision_kind: DecisionKind) -> object | None:
    peek = getattr(bot, "peek_last_decision_reason", None)
    if not callable(peek):
        return None
    return peek(decision_kind)


def serialize_decision_reason(
    reason: object,
    *,
    registry: DecisionReasonSerializerRegistry | None = None,
) -> SerializedReasonPayload | None:
    active_registry = registry if registry is not None else default_reason_serializer_registry()
    return active_registry.serialize(reason)


def serialize_bot_decision_reason(
    bot: object,
    decision_kind: DecisionKind,
    *,
    registry: DecisionReasonSerializerRegistry | None = None,
) -> SerializedReasonPayload | None:
    reason = peek_bot_decision_reason(bot, decision_kind)
    if reason is None:
        return None
    return serialize_decision_reason(reason, registry=registry)


__all__ = [
    "DecisionKind",
    "DecisionReasonSerializer",
    "DecisionReasonSerializerRegistry",
    "SerializedReasonPayload",
    "SupportsDecisionReasonPeek",
    "default_reason_serializer_registry",
    "peek_bot_decision_reason",
    "register_default_reason_serializer",
    "serialize_bot_decision_reason",
    "serialize_decision_reason",
]
