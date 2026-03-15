"""Bot implementations for Hearts."""

from hearts_ai.bots.base import Bot
from hearts_ai.bots.factory import (
    available_bot_names,
    create_bot,
    create_bots,
    normalize_bot_name,
    resolve_bot_names,
)
from hearts_ai.bots.heuristic_bot import HeuristicBot, HeuristicBotV2, HeuristicBotV3
from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.bots.reasons import (
    DecisionKind,
    DecisionReasonSerializer,
    DecisionReasonSerializerRegistry,
    SerializedReasonPayload,
    SupportsDecisionReasonPeek,
    default_reason_serializer_registry,
    peek_bot_decision_reason,
    register_default_reason_serializer,
    serialize_bot_decision_reason,
    serialize_decision_reason,
)

__all__ = [
    "Bot",
    "DecisionKind",
    "DecisionReasonSerializer",
    "DecisionReasonSerializerRegistry",
    "HeuristicBot",
    "HeuristicBotV2",
    "HeuristicBotV3",
    "RandomBot",
    "SerializedReasonPayload",
    "SupportsDecisionReasonPeek",
    "available_bot_names",
    "create_bot",
    "create_bots",
    "default_reason_serializer_registry",
    "normalize_bot_name",
    "peek_bot_decision_reason",
    "register_default_reason_serializer",
    "resolve_bot_names",
    "serialize_bot_decision_reason",
    "serialize_decision_reason",
]
