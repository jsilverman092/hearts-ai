from __future__ import annotations

import json
from typing import Any, Literal, Mapping, TypeAlias, TypedDict, cast

SCHEMA_VERSION = 1


class MessageValidationError(ValueError):
    """Raised when a protocol message is malformed or unsupported."""


class CreateTableMsg(TypedDict):
    schema_version: int
    type: Literal["create_table"]
    display_name: str


class JoinTableMsgBase(TypedDict):
    schema_version: int
    type: Literal["join_table"]
    table_code: str
    display_name: str


class JoinTableMsg(JoinTableMsgBase, total=False):
    player_secret: str


class SitSeatMsg(TypedDict):
    schema_version: int
    type: Literal["sit_seat"]
    seat: int
    player_secret: str


class SubmitPassMsg(TypedDict):
    schema_version: int
    type: Literal["submit_pass"]
    player_secret: str
    cards: list[str]


class PlayCardMsg(TypedDict):
    schema_version: int
    type: Literal["play_card"]
    player_secret: str
    card: str


class PingMsg(TypedDict):
    schema_version: int
    type: Literal["ping"]
    nonce: str


ClientMsg: TypeAlias = (
    CreateTableMsg | JoinTableMsg | SitSeatMsg | SubmitPassMsg | PlayCardMsg | PingMsg
)


class ErrorMsg(TypedDict):
    schema_version: int
    type: Literal["error"]
    code: str
    message: str


class TableJoinedMsg(TypedDict):
    schema_version: int
    type: Literal["table_joined"]
    table_code: str
    player_secret: str
    seat: int | None


class StateSnapshotMsg(TypedDict):
    schema_version: int
    type: Literal["state_snapshot"]
    table_code: str
    phase: str
    payload: dict[str, Any]


class EventMsg(TypedDict):
    schema_version: int
    type: Literal["event"]
    table_code: str
    event: dict[str, Any]


class PongMsg(TypedDict):
    schema_version: int
    type: Literal["pong"]
    nonce: str


ServerMsg: TypeAlias = ErrorMsg | TableJoinedMsg | StateSnapshotMsg | EventMsg | PongMsg


def validate_schema_version(message: Mapping[str, Any]) -> None:
    if "schema_version" not in message:
        raise MessageValidationError("Message is missing required field 'schema_version'.")

    schema_version = message["schema_version"]
    if not isinstance(schema_version, int):
        raise MessageValidationError(
            f"Field 'schema_version' must be int, got {type(schema_version).__name__}."
        )
    if schema_version != SCHEMA_VERSION:
        raise MessageValidationError(
            f"Unsupported schema_version {schema_version}; expected {SCHEMA_VERSION}."
        )


def dumps_message(message: Mapping[str, Any]) -> str:
    validate_schema_version(message)
    if "type" not in message or not isinstance(message["type"], str):
        raise MessageValidationError("Message is missing required string field 'type'.")
    return json.dumps(dict(message), separators=(",", ":"), sort_keys=True)


def loads_message(raw: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MessageValidationError(f"Invalid JSON message: {exc.msg}.") from exc

    if not isinstance(decoded, dict):
        raise MessageValidationError("Protocol message must decode to a JSON object.")

    message = cast(dict[str, Any], decoded)
    validate_schema_version(message)
    if "type" not in message or not isinstance(message["type"], str):
        raise MessageValidationError("Message is missing required string field 'type'.")
    return message


__all__ = [
    "ClientMsg",
    "MessageValidationError",
    "SCHEMA_VERSION",
    "ServerMsg",
    "dumps_message",
    "loads_message",
    "validate_schema_version",
]
