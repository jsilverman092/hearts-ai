from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.game import apply_pass, is_game_over, is_hand_over, play_card
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, Deal, PlayerId, to_player_id
from hearts_ai.protocol.messages import MessageValidationError, SCHEMA_VERSION, validate_schema_version

_TWO_OF_CLUBS = Card(Suit.CLUBS, Rank.TWO)
_CARD_SUITS = {"C": Suit.CLUBS, "D": Suit.DIAMONDS, "H": Suit.HEARTS, "S": Suit.SPADES}
_CARD_RANKS = {
    "2": Rank.TWO,
    "3": Rank.THREE,
    "4": Rank.FOUR,
    "5": Rank.FIVE,
    "6": Rank.SIX,
    "7": Rank.SEVEN,
    "8": Rank.EIGHT,
    "9": Rank.NINE,
    "10": Rank.TEN,
    "T": Rank.TEN,
    "J": Rank.JACK,
    "Q": Rank.QUEEN,
    "K": Rank.KING,
    "A": Rank.ACE,
}


class ReplayValidationError(InvalidStateError):
    """Raised when replay events are malformed or violate game invariants."""


@dataclass(slots=True)
class GameRecorder:
    path: Path | str
    game_id: str
    table_id: str = "local-cli"
    schema_version: int = SCHEMA_VERSION
    _next_event_id: int = field(default=1, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    def record_game_created(self, *, config: GameConfig, seed: int) -> None:
        payload = {"config": _encode_config(config), "seed": seed}
        self.emit(event_type="game_created", actor="server", payload=payload)

    def record_hand_dealt(self, state: GameState) -> None:
        payload = {
            "hand_number": state.hand_number,
            "pass_direction": state.pass_direction,
            "hands": _encode_hands(state.hands),
        }
        self.emit(
            event_type="hand_dealt",
            actor="server",
            hand_index=state.hand_number,
            payload=payload,
        )

    def record_pass_applied(self, *, hand_index: int, pass_map: Mapping[PlayerId, list[Card]]) -> None:
        payload = {"pass_map": _encode_pass_map(pass_map)}
        self.emit(
            event_type="pass_applied",
            actor="server",
            hand_index=hand_index,
            payload=payload,
        )

    def record_card_played(self, *, hand_index: int, player_id: PlayerId, card: Card) -> None:
        payload = {"player_id": int(player_id), "card": _card_to_code(card)}
        self.emit(
            event_type="card_played",
            actor=f"player:{int(player_id)}",
            hand_index=hand_index,
            payload=payload,
        )

    def record_hand_scored(
        self,
        *,
        hand_index: int,
        delta_scores: Mapping[PlayerId, int],
        total_scores: Mapping[PlayerId, int],
    ) -> None:
        payload = {
            "delta_scores": _encode_scores(delta_scores),
            "total_scores": _encode_scores(total_scores),
        }
        self.emit(
            event_type="hand_scored",
            actor="server",
            hand_index=hand_index,
            payload=payload,
        )

    def record_game_ended(self, *, final_scores: Mapping[PlayerId, int]) -> None:
        payload = {
            "final_scores": _encode_scores(final_scores),
            "winner_ids": _winner_ids(final_scores),
        }
        self.emit(event_type="game_ended", actor="server", payload=payload)

    def emit(
        self,
        *,
        event_type: str,
        actor: str,
        payload: Mapping[str, Any],
        hand_index: int | None = None,
    ) -> None:
        event = {
            "schema_version": self.schema_version,
            "event_id": self._next_event_id,
            "event_type": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            "table_id": self.table_id,
            "game_id": self.game_id,
            "hand_index": hand_index,
            "actor": actor,
            "payload": dict(payload),
        }
        _append_jsonl_event(self.path, event)
        self._next_event_id += 1


def load_events(path: Path | str) -> list[dict[str, Any]]:
    file_path = Path(path)
    events: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                decoded = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReplayValidationError(
                    f"Invalid JSON in replay file {file_path} line {line_number}: {exc.msg}."
                ) from exc
            if not isinstance(decoded, dict):
                raise ReplayValidationError(
                    f"Replay file {file_path} line {line_number} must be a JSON object."
                )

            event = dict(decoded)
            try:
                validate_schema_version(event)
            except MessageValidationError as exc:
                raise ReplayValidationError(
                    f"Replay file {file_path} line {line_number} schema validation failed: {exc}"
                ) from exc
            events.append(event)
    return events


def replay_jsonl(path: Path | str) -> list[tuple[str, GameState]]:
    events = load_events(path)
    if not events:
        raise ReplayValidationError(f"Replay file {Path(path)} does not contain any events.")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        game_id = _required_str(event, "game_id")
        grouped.setdefault(game_id, []).append(event)

    results: list[tuple[str, GameState]] = []
    for game_id, game_events in grouped.items():
        state = replay(game_events)
        results.append((game_id, state))
    return results


def replay(events: Sequence[Mapping[str, Any]]) -> GameState:
    if not events:
        raise ReplayValidationError("Replay requires at least one event.")

    first_event = dict(events[0])
    if _required_str(first_event, "event_type") != "game_created":
        raise ReplayValidationError("Replay must start with a 'game_created' event.")

    game_id = _required_str(first_event, "game_id")
    game_created_payload = _required_mapping(first_event, "payload")
    config_raw = _required_mapping(game_created_payload, "config")
    state = GameState(config=_decode_config(config_raw))
    score_start = dict(state.scores)

    expected_event_id = 1
    saw_hand = False
    saw_game_end = False

    for raw_event in events:
        event = dict(raw_event)
        try:
            validate_schema_version(event)
        except MessageValidationError as exc:
            raise ReplayValidationError(f"Replay event schema validation failed: {exc}") from exc

        event_game_id = _required_str(event, "game_id")
        if event_game_id != game_id:
            raise ReplayValidationError(
                f"Mismatched game id in replay stream: {event_game_id!r} != {game_id!r}."
            )

        event_id = _required_int(event, "event_id")
        if event_id != expected_event_id:
            raise ReplayValidationError(
                f"Non-monotonic event_id: expected {expected_event_id}, got {event_id}."
            )
        expected_event_id += 1

        event_type = _required_str(event, "event_type")
        payload = _required_mapping(event, "payload")

        if event_type == "game_created":
            continue
        if event_type == "hand_dealt":
            _apply_recorded_deal(state=state, payload=payload)
            score_start = dict(state.scores)
            saw_hand = True
            continue
        if event_type == "pass_applied":
            if not saw_hand:
                raise ReplayValidationError("Received pass event before any hand was dealt.")
            pass_map = _decode_pass_map(_required_mapping(payload, "pass_map"))
            apply_pass(state=state, pass_map=pass_map)
            continue
        if event_type == "card_played":
            if not saw_hand:
                raise ReplayValidationError("Received card play before any hand was dealt.")
            player_id = to_player_id(_required_int(payload, "player_id"))
            card = _card_from_code(_required_str(payload, "card"))
            play_card(state=state, player_id=player_id, card=card)
            continue
        if event_type == "hand_scored":
            if not state.hand_scored:
                raise ReplayValidationError(
                    "Replay expected hand to be scored before 'hand_scored' event."
                )
            expected_delta = _decode_scores(_required_mapping(payload, "delta_scores"))
            expected_totals = _decode_scores(_required_mapping(payload, "total_scores"))
            actual_delta = {
                player_id: state.scores[player_id] - score_start[player_id] for player_id in PLAYER_IDS
            }
            if actual_delta != expected_delta:
                raise ReplayValidationError(
                    f"Hand delta mismatch: expected {expected_delta}, got {actual_delta}."
                )
            if state.scores != expected_totals:
                raise ReplayValidationError(
                    f"Hand total score mismatch: expected {expected_totals}, got {state.scores}."
                )
            continue
        if event_type == "game_ended":
            if not is_game_over(state):
                raise ReplayValidationError("Replay reached 'game_ended' before game-over condition.")
            expected_final = _decode_scores(_required_mapping(payload, "final_scores"))
            expected_winners = sorted(_decode_winner_ids(payload.get("winner_ids")))
            actual_winners = sorted(_winner_ids(state.scores))
            if state.scores != expected_final:
                raise ReplayValidationError(
                    f"Final score mismatch: expected {expected_final}, got {state.scores}."
                )
            if actual_winners != expected_winners:
                raise ReplayValidationError(
                    f"Winner mismatch: expected {expected_winners}, got {actual_winners}."
                )
            saw_game_end = True
            continue

        raise ReplayValidationError(f"Unsupported event type in replay: {event_type!r}.")

    if not saw_hand:
        raise ReplayValidationError("Replay stream did not include any dealt hands.")
    if not saw_game_end:
        raise ReplayValidationError("Replay stream did not include a 'game_ended' event.")
    if not is_hand_over(state):
        raise ReplayValidationError("Replay ended before the current hand completed.")
    return state


def _apply_recorded_deal(state: GameState, payload: Mapping[str, Any]) -> None:
    hand_number = _required_int(payload, "hand_number")
    if hand_number != state.hand_number + 1:
        raise ReplayValidationError(
            f"Unexpected hand_number {hand_number}; expected {state.hand_number + 1}."
        )
    if state.hand_number > 0 and not is_hand_over(state):
        raise ReplayValidationError("Cannot deal a new recorded hand before current hand completion.")

    hands = _decode_hands(_required_mapping(payload, "hands"))
    _validate_dealt_hands(hands)
    pass_direction = _required_str(payload, "pass_direction")

    expected_pass_direction = state.config.pass_directions[
        (hand_number - 1) % len(state.config.pass_directions)
    ]
    if pass_direction != expected_pass_direction:
        raise ReplayValidationError(
            f"Pass direction mismatch for hand {hand_number}: "
            f"expected {expected_pass_direction!r}, got {pass_direction!r}."
        )

    state.hands = hands
    state.hearts_broken = False
    state.trick_in_progress = []
    state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}
    state.trick_number = 0
    state.hand_number = hand_number
    state.pass_direction = pass_direction
    state.pass_applied = pass_direction == "hold"
    state.hand_scored = False
    state.turn = _player_holding_two_of_clubs(hands)


def _player_holding_two_of_clubs(hands: Deal) -> PlayerId:
    for player_id in PLAYER_IDS:
        if _TWO_OF_CLUBS in hands[player_id]:
            return player_id
    raise ReplayValidationError("Recorded deal is invalid: no player holds 2C.")


def _append_jsonl_event(path: Path, event: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(event), separators=(",", ":"), sort_keys=True))
        handle.write("\n")


def _card_to_code(card: Card) -> str:
    return str(card)


def _card_from_code(code: str) -> Card:
    if len(code) < 2:
        raise ReplayValidationError(f"Invalid card code {code!r}.")
    rank_text = code[:-1]
    suit_text = code[-1].upper()

    if suit_text not in _CARD_SUITS:
        raise ReplayValidationError(f"Invalid card suit in {code!r}.")
    if rank_text.upper() not in _CARD_RANKS:
        raise ReplayValidationError(f"Invalid card rank in {code!r}.")

    suit = _CARD_SUITS[suit_text]
    rank = _CARD_RANKS[rank_text.upper()]
    return Card(suit=suit, rank=rank)


def _encode_hands(hands: Mapping[PlayerId, list[Card]]) -> dict[str, list[str]]:
    return {str(int(player_id)): [_card_to_code(card) for card in hands[player_id]] for player_id in PLAYER_IDS}


def _decode_hands(raw: Mapping[str, Any]) -> Deal:
    decoded: Deal = {player_id: [] for player_id in PLAYER_IDS}
    for player_id in PLAYER_IDS:
        key = str(int(player_id))
        if key not in raw:
            raise ReplayValidationError(f"Recorded hands are missing player {int(player_id)}.")
        card_codes = raw[key]
        if not isinstance(card_codes, list) or any(not isinstance(item, str) for item in card_codes):
            raise ReplayValidationError(
                f"Recorded hand for player {int(player_id)} must be a list of card codes."
            )
        decoded[player_id] = sorted(_card_from_code(code) for code in card_codes)
    return decoded


def _validate_dealt_hands(hands: Deal) -> None:
    all_cards: list[Card] = []
    for player_id in PLAYER_IDS:
        hand = hands[player_id]
        if len(hand) != 13:
            raise ReplayValidationError(
                f"Recorded hand size for player {int(player_id)} must be 13, got {len(hand)}."
            )
        all_cards.extend(hand)
    if len(set(all_cards)) != 52:
        raise ReplayValidationError("Recorded hand contains duplicate or missing cards.")


def _encode_pass_map(pass_map: Mapping[PlayerId, list[Card]]) -> dict[str, list[str]]:
    return {
        str(int(player_id)): [_card_to_code(card) for card in pass_map[player_id]]
        for player_id in PLAYER_IDS
    }


def _decode_pass_map(raw: Mapping[str, Any]) -> dict[PlayerId, list[Card]]:
    decoded: dict[PlayerId, list[Card]] = {}
    for player_id in PLAYER_IDS:
        key = str(int(player_id))
        if key not in raw:
            raise ReplayValidationError(f"Pass map is missing player {int(player_id)}.")
        card_codes = raw[key]
        if not isinstance(card_codes, list) or any(not isinstance(item, str) for item in card_codes):
            raise ReplayValidationError(
                f"Pass map for player {int(player_id)} must be a list of card codes."
            )
        decoded[player_id] = [_card_from_code(code) for code in card_codes]
    return decoded


def _encode_scores(scores: Mapping[PlayerId, int]) -> dict[str, int]:
    return {str(int(player_id)): int(scores[player_id]) for player_id in PLAYER_IDS}


def _decode_scores(raw: Mapping[str, Any]) -> dict[PlayerId, int]:
    decoded: dict[PlayerId, int] = {}
    for player_id in PLAYER_IDS:
        key = str(int(player_id))
        if key not in raw or not isinstance(raw[key], int):
            raise ReplayValidationError(f"Score payload is missing integer value for player {int(player_id)}.")
        decoded[player_id] = raw[key]
    return decoded


def _encode_config(config: GameConfig) -> dict[str, Any]:
    return {
        "target_score": config.target_score,
        "pass_directions": list(config.pass_directions),
        "pass_count": config.pass_count,
        "require_two_clubs_open": config.require_two_clubs_open,
        "enforce_follow_suit": config.enforce_follow_suit,
        "hearts_must_be_broken_to_lead": config.hearts_must_be_broken_to_lead,
        "no_points_on_first_trick": config.no_points_on_first_trick,
    }


def _decode_config(raw: Mapping[str, Any]) -> GameConfig:
    try:
        target_score = int(raw["target_score"])
        pass_directions = tuple(str(direction) for direction in raw["pass_directions"])
        pass_count = int(raw["pass_count"])
        require_two_clubs_open = bool(raw["require_two_clubs_open"])
        enforce_follow_suit = bool(raw["enforce_follow_suit"])
        hearts_must_be_broken_to_lead = bool(raw["hearts_must_be_broken_to_lead"])
        no_points_on_first_trick = bool(raw["no_points_on_first_trick"])
    except KeyError as exc:
        raise ReplayValidationError(f"Replay config is missing key: {exc}.") from exc
    except (TypeError, ValueError) as exc:
        raise ReplayValidationError(f"Replay config is malformed: {exc}.") from exc

    return GameConfig(
        target_score=target_score,
        pass_directions=pass_directions,
        pass_count=pass_count,
        require_two_clubs_open=require_two_clubs_open,
        enforce_follow_suit=enforce_follow_suit,
        hearts_must_be_broken_to_lead=hearts_must_be_broken_to_lead,
        no_points_on_first_trick=no_points_on_first_trick,
    )


def _decode_winner_ids(raw: Any) -> list[int]:
    if not isinstance(raw, list) or any(not isinstance(item, int) for item in raw):
        raise ReplayValidationError("winner_ids must be a list of integers.")
    return sorted(raw)


def _winner_ids(scores: Mapping[PlayerId, int]) -> list[int]:
    best_score = min(scores.values())
    return sorted(int(player_id) for player_id in PLAYER_IDS if scores[player_id] == best_score)


def _required_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise ReplayValidationError(f"Field {key!r} must be an object.")
    return value


def _required_str(container: Mapping[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str):
        raise ReplayValidationError(f"Field {key!r} must be a string.")
    return value


def _required_int(container: Mapping[str, Any], key: str) -> int:
    value = container.get(key)
    if not isinstance(value, int):
        raise ReplayValidationError(f"Field {key!r} must be an integer.")
    return value


__all__ = ["GameRecorder", "ReplayValidationError", "load_events", "replay", "replay_jsonl"]

