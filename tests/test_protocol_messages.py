import pytest

from hearts_ai.protocol.messages import MessageValidationError, dumps_message, loads_message


def test_protocol_message_roundtrip() -> None:
    message = {
        "schema_version": 1,
        "type": "play_card",
        "player_secret": "abc123",
        "card": "QH",
    }

    encoded = dumps_message(message)
    decoded = loads_message(encoded)

    assert decoded == message


def test_protocol_message_requires_supported_schema_version() -> None:
    with pytest.raises(MessageValidationError):
        loads_message('{"schema_version":2,"type":"ping","nonce":"x"}')

    with pytest.raises(MessageValidationError):
        dumps_message({"type": "ping", "nonce": "x"})

