from __future__ import annotations

import copy
import random
import secrets
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from hearts_ai.bots.factory import create_bot, normalize_bot_name
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.game import apply_pass, deal, is_game_over, is_hand_over, new_game, play_card
from hearts_ai.engine.record import GameRecorder
from hearts_ai.engine.scoring import trick_points
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId, Trick, to_player_id
from hearts_ai.server.persistence import RecordStore

TablePhase = Literal["lobby", "passing", "playing", "hand_scoring", "game_over"]
AdvanceAction = Literal[
    "bot_pass_submitted",
    "pass_applied",
    "bot_card_played",
    "hand_scoring_entered",
    "next_hand_dealt",
    "game_over",
]

_TABLE_CODE_ALPHABET = string.ascii_uppercase + string.digits
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


class TableError(RuntimeError):
    """Base class for table and multiplayer server errors."""


class TableNotFoundError(TableError):
    """Raised when a table code does not map to an active table."""


class UnauthorizedError(TableError):
    """Raised when a player secret does not authorize an action."""


class InvalidTableActionError(TableError):
    """Raised when an action does not match table state or seat ownership."""


@dataclass(slots=True)
class Participant:
    display_name: str
    seat: PlayerId | None = None


@dataclass(slots=True, frozen=True)
class AdvanceResult:
    advanced: bool
    action: AdvanceAction | None
    can_advance: bool


@dataclass(slots=True, frozen=True)
class LastTrick:
    winner_id: PlayerId
    trick: Trick
    points: int
    trick_seq: int


def _empty_seat_secrets() -> dict[PlayerId, str | None]:
    return {player_id: None for player_id in PLAYER_IDS}


def _zero_scores() -> dict[PlayerId, int]:
    return {player_id: 0 for player_id in PLAYER_IDS}


def _empty_bot_seat_types() -> dict[PlayerId, str]:
    return {}


def _empty_viewer_advisory_bot_types() -> dict[str, str]:
    return {}


@dataclass(slots=True)
class Table:
    table_code: str
    seed: int
    config: GameConfig
    rng: random.Random
    state: GameState
    phase: TablePhase = "lobby"
    participants: dict[str, Participant] = field(default_factory=dict)
    seat_secrets: dict[PlayerId, str | None] = field(default_factory=_empty_seat_secrets)
    bot_seats: set[PlayerId] = field(default_factory=set)
    bot_seat_types: dict[PlayerId, str] = field(default_factory=_empty_bot_seat_types)
    viewer_advisory_bot_types: dict[str, str] = field(default_factory=_empty_viewer_advisory_bot_types)
    pending_passes: dict[PlayerId, list[Card]] = field(default_factory=dict)
    version: int = 0
    recorder: GameRecorder | None = None
    game_id: str | None = None
    record_path: Path | None = None
    summary_path: Path | None = None
    host_secret: str | None = None
    auto_advance: bool = False
    last_trick: LastTrick | None = None
    hand_score_start: dict[PlayerId, int] = field(default_factory=_zero_scores)
    last_recorded_scored_hand: int = 0
    game_end_recorded: bool = False
    summary_written: bool = False
    debug_last_bot_decision: dict[str, Any] | None = None

    def join(self, display_name: str) -> str:
        if not display_name.strip():
            raise InvalidTableActionError("Display name must not be empty.")
        player_secret = secrets.token_urlsafe(16)
        self.participants[player_secret] = Participant(display_name=display_name.strip())
        self.viewer_advisory_bot_types[player_secret] = "heuristic_v3"
        self.version += 1
        return player_secret

    def claim_seat(self, player_secret: str, seat: int) -> None:
        participant = self._require_participant(player_secret)
        player_id = to_player_id(seat)

        if player_id in self.bot_seats:
            raise InvalidTableActionError(f"Seat {seat} is occupied by a bot.")

        current_secret = self.seat_secrets[player_id]
        if current_secret is not None and current_secret != player_secret:
            raise InvalidTableActionError(f"Seat {seat} is already occupied by another player.")

        if participant.seat is not None and participant.seat != player_id:
            self.seat_secrets[participant.seat] = None

        self.seat_secrets[player_id] = player_secret
        participant.seat = player_id
        self.version += 1
        self._maybe_start_game()

    def add_bot(self, seat: int, *, bot_name: str = "random") -> None:
        if self.phase != "lobby":
            raise InvalidTableActionError("Bot configuration is only allowed during lobby phase.")
        player_id = to_player_id(seat)
        current_secret = self.seat_secrets[player_id]
        if current_secret is not None:
            raise InvalidTableActionError(f"Seat {seat} is occupied by a human player.")
        try:
            normalized_bot_name = normalize_bot_name(bot_name)
        except ValueError as exc:
            raise InvalidTableActionError(str(exc)) from exc
        self.bot_seats.add(player_id)
        self.bot_seat_types[player_id] = normalized_bot_name
        self.version += 1
        self._maybe_start_game()

    def set_viewer_advisory_bot(self, player_secret: str, *, bot_name: str) -> None:
        self._require_participant(player_secret)
        try:
            normalized_bot_name = normalize_bot_name(bot_name)
        except ValueError as exc:
            raise InvalidTableActionError(str(exc)) from exc
        self.viewer_advisory_bot_types[player_secret] = normalized_bot_name
        self.version += 1

    def submit_pass(self, player_secret: str, cards: list[str]) -> None:
        if self.phase != "passing":
            raise InvalidTableActionError("Pass submissions are only allowed during the passing phase.")
        player_id = self._require_seated_human(player_secret)
        if player_id in self.pending_passes:
            raise InvalidTableActionError("Pass already submitted for this hand.")
        self.pending_passes[player_id] = [_card_from_code(code) for code in cards]
        self.version += 1
        self._maybe_auto_advance()

    def play(self, player_secret: str, card_code: str) -> None:
        if self.phase != "playing":
            raise InvalidTableActionError("Card play is only allowed during the playing phase.")
        player_id = self._require_seated_human(player_secret)
        if self.state.turn != player_id:
            raise InvalidTableActionError(
                f"It is player {int(self.state.turn) if self.state.turn is not None else 'none'}'s turn."
            )
        card = _card_from_code(card_code)
        previous_trick_number = self.state.trick_number
        play_card(state=self.state, player_id=player_id, card=card)
        self._capture_last_trick(previous_trick_number=previous_trick_number)
        self._record_card_played(player_id=player_id, card=card)
        self.version += 1
        self._maybe_auto_advance()

    def can_advance(self) -> bool:
        if self.phase == "passing":
            if len(self.pending_passes) == len(PLAYER_IDS):
                return True
            return any(player_id in self.bot_seats and player_id not in self.pending_passes for player_id in PLAYER_IDS)
        if self.phase == "playing":
            if is_hand_over(self.state):
                return True
            if self.state.turn is None:
                raise InvalidTableActionError("Game state turn is unset during playing phase.")
            return self.state.turn in self.bot_seats
        if self.phase == "hand_scoring":
            return True
        return False

    def advance_one_action(self, *, player_secret: str) -> AdvanceResult:
        self._require_pace_controller(player_secret)
        action = self._advance_one_action()
        return AdvanceResult(
            advanced=action is not None,
            action=action,
            can_advance=self.can_advance(),
        )

    def seat_display_name(self, player_id: PlayerId) -> str | None:
        seat_secret = self.seat_secrets[player_id]
        if seat_secret is None:
            return None
        participant = self.participants.get(seat_secret)
        return participant.display_name if participant is not None else None

    def viewer_advisory_bot_name(self, player_secret: str | None) -> str | None:
        if player_secret is None:
            return None
        return self.viewer_advisory_bot_types.get(player_secret)

    def viewer_debug_recommendation(self, viewer_secret: str | None) -> dict[str, Any] | None:
        if viewer_secret is None:
            return None
        participant = self.participants.get(viewer_secret)
        if participant is None or participant.seat is None:
            return {
                "status": "idle",
                "message": "Viewer must claim a human seat for recommendations.",
            }
        viewer_seat = participant.seat
        if viewer_seat in self.bot_seats:
            return {
                "status": "idle",
                "message": "Viewer recommendations are available only for human-controlled seats.",
            }

        decision_kind: Literal["pass", "play"] | None = None
        if self.phase == "passing":
            if viewer_seat in self.pending_passes:
                return {
                    "status": "idle",
                    "message": "Pass already submitted for this hand.",
                }
            decision_kind = "pass"
        elif self.phase == "playing":
            if self.state.turn != viewer_seat:
                return {
                    "status": "idle",
                    "message": f"Waiting on P{int(self.state.turn)}.",
                }
            decision_kind = "play"
        else:
            return {
                "status": "idle",
                "message": f"No viewer recommendation in phase '{self.phase}'.",
            }

        advisory_bot_name = self.viewer_advisory_bot_name(viewer_secret) or "heuristic_v3"
        if advisory_bot_name not in {"heuristic_v2", "heuristic_v3"}:
            return {
                "status": "unsupported_bot",
                "seat": int(viewer_seat),
                "bot_name": advisory_bot_name,
                "decision_kind": decision_kind,
                "hand_number": self.state.hand_number,
                "trick_number": self.state.trick_number,
                "message": f"No explanation payload support for advisory bot '{advisory_bot_name}'.",
            }

        advisory_rng_seed = (
            (self.seed << 16)
            ^ (self.state.hand_number << 8)
            ^ (self.state.trick_number << 2)
            ^ int(viewer_seat)
            ^ sum(ord(ch) for ch in advisory_bot_name)
        )
        advisory_rng = random.Random(advisory_rng_seed)
        advisory_state = copy.deepcopy(self.state)
        advisory_bot = create_bot(advisory_bot_name, player_id=viewer_seat)

        try:
            if decision_kind == "pass":
                advisory_bot.choose_pass(
                    hand=advisory_state.hands[viewer_seat],
                    state=advisory_state,
                    rng=advisory_rng,
                )
                payload = _serialize_heuristic_v2_pass_reason(advisory_bot)
            else:
                advisory_bot.choose_play(state=advisory_state, rng=advisory_rng)
                payload = _serialize_heuristic_v2_play_reason(advisory_bot)
        except Exception as exc:
            return {
                "status": "error",
                "seat": int(viewer_seat),
                "bot_name": advisory_bot_name,
                "decision_kind": decision_kind,
                "hand_number": self.state.hand_number,
                "trick_number": self.state.trick_number,
                "message": f"Failed to generate recommendation: {exc}",
            }

        if payload is None:
            return {
                "status": "error",
                "seat": int(viewer_seat),
                "bot_name": advisory_bot_name,
                "decision_kind": decision_kind,
                "hand_number": self.state.hand_number,
                "trick_number": self.state.trick_number,
                "message": "Recommendation bot did not expose a reason payload.",
            }

        return {
            "status": "ok",
            "seat": int(viewer_seat),
            "bot_name": advisory_bot_name,
            "decision_kind": decision_kind,
            "hand_number": self.state.hand_number,
            "trick_number": self.state.trick_number,
            "payload": payload,
        }

    def is_started(self) -> bool:
        return self.phase != "lobby"

    def _maybe_start_game(self) -> None:
        if self.phase != "lobby":
            return
        if any(self.seat_secrets[player_id] is None and player_id not in self.bot_seats for player_id in PLAYER_IDS):
            return

        self.phase = "playing" if self.state.pass_applied else "passing"
        self.pending_passes.clear()
        self.version += 1
        self._maybe_auto_advance()

    def _maybe_auto_advance(self) -> None:
        if not self.auto_advance:
            return
        while self._advance_one_action() is not None:
            pass

    def _advance_one_action(self) -> AdvanceAction | None:
        if self.phase == "passing":
            if len(self.pending_passes) == len(PLAYER_IDS):
                pass_map = dict(self.pending_passes)
                apply_pass(state=self.state, pass_map=pass_map)
                self._record_pass_applied(pass_map=pass_map)
                self.pending_passes.clear()
                self.phase = "playing"
                self.version += 1
                return "pass_applied"

            for player_id in PLAYER_IDS:
                if player_id in self.pending_passes or player_id not in self.bot_seats:
                    continue
                bot = self._bot_for_player(player_id)
                self.pending_passes[player_id] = bot.choose_pass(
                    hand=self.state.hands[player_id],
                    state=self.state,
                    rng=self.rng,
                )
                self._capture_bot_debug_decision(player_id=player_id, bot=bot, decision_kind="pass")
                self.version += 1
                return "bot_pass_submitted"
            return None

        if self.phase == "playing":
            if is_hand_over(self.state):
                self.phase = "hand_scoring"
                self.version += 1
                return "hand_scoring_entered"

            if self.state.turn is None:
                raise InvalidTableActionError("Game state turn is unset during playing phase.")
            if self.state.turn not in self.bot_seats:
                return None

            bot_player = self.state.turn
            bot = self._bot_for_player(bot_player)
            card = bot.choose_play(state=self.state, rng=self.rng)
            self._capture_bot_debug_decision(player_id=bot_player, bot=bot, decision_kind="play")
            previous_trick_number = self.state.trick_number
            play_card(state=self.state, player_id=bot_player, card=card)
            self._capture_last_trick(previous_trick_number=previous_trick_number)
            self._record_card_played(player_id=bot_player, card=card)
            self.version += 1
            return "bot_card_played"

        if self.phase == "hand_scoring":
            if not self.state.hand_scored or not is_hand_over(self.state):
                raise InvalidTableActionError("Cannot transition from hand_scoring before hand completion.")
            self._record_hand_scored_if_needed()

            if is_game_over(self.state):
                self.phase = "game_over"
                self.version += 1
                return "game_over"

            deal(state=self.state, rng=self.rng)
            if self.recorder is not None:
                self.recorder.record_hand_dealt(self.state)
            self.pending_passes.clear()
            self.last_trick = None
            self.phase = "playing" if self.state.pass_applied else "passing"
            self.hand_score_start = dict(self.state.scores)
            self.version += 1
            return "next_hand_dealt"

        return None

    def _require_participant(self, player_secret: str) -> Participant:
        participant = self.participants.get(player_secret)
        if participant is None:
            raise UnauthorizedError("Unknown player secret.")
        return participant

    def _require_seated_human(self, player_secret: str) -> PlayerId:
        participant = self._require_participant(player_secret)
        if participant.seat is None:
            raise UnauthorizedError("You must claim a seat before taking game actions.")
        if participant.seat in self.bot_seats:
            raise UnauthorizedError("Bot-occupied seats cannot be controlled by a human.")
        if self.seat_secrets[participant.seat] != player_secret:
            raise UnauthorizedError("Player secret does not control this seat.")
        return participant.seat

    def _require_pace_controller(self, player_secret: str) -> None:
        participant = self._require_participant(player_secret)
        if self.host_secret is not None and player_secret == self.host_secret:
            return
        if participant.seat == to_player_id(0):
            return
        raise UnauthorizedError("Only the host or seat 0 can control table pacing.")

    def _capture_last_trick(self, *, previous_trick_number: int) -> None:
        if self.state.trick_number <= previous_trick_number:
            return
        winner = self.state.turn
        if winner is None:
            raise InvalidTableActionError("Completed trick is missing winner turn.")
        winner_tricks = self.state.taken_tricks[winner]
        if not winner_tricks:
            raise InvalidTableActionError("Completed trick is missing from winner taken tricks.")
        trick = list(winner_tricks[-1])
        self.last_trick = LastTrick(
            winner_id=winner,
            trick=trick,
            points=trick_points(trick),
            trick_seq=self.state.trick_number,
        )

    def _record_pass_applied(self, *, pass_map: dict[PlayerId, list[Card]]) -> None:
        if self.recorder is None:
            return
        self.recorder.record_pass_applied(hand_index=self.state.hand_number, pass_map=pass_map)

    def _record_card_played(self, *, player_id: PlayerId, card: Card) -> None:
        if self.recorder is None:
            return
        self.recorder.record_card_played(
            hand_index=self.state.hand_number,
            player_id=player_id,
            card=card,
        )

    def _record_hand_scored_if_needed(self) -> None:
        if self.last_recorded_scored_hand == self.state.hand_number:
            return
        delta_scores = {
            player_id: self.state.scores[player_id] - self.hand_score_start[player_id]
            for player_id in PLAYER_IDS
        }
        if self.recorder is not None:
            self.recorder.record_hand_scored(
                hand_index=self.state.hand_number,
                delta_scores=delta_scores,
                total_scores=self.state.scores,
            )
        self.hand_score_start = dict(self.state.scores)
        self.last_recorded_scored_hand = self.state.hand_number

    def bot_name_for_seat(self, player_id: PlayerId) -> str:
        return self.bot_seat_types.get(player_id, "random")

    def _bot_for_player(self, player_id: PlayerId):
        return create_bot(self.bot_name_for_seat(player_id), player_id=player_id)

    def _capture_bot_debug_decision(self, *, player_id: PlayerId, bot: Any, decision_kind: str) -> None:
        bot_name = self.bot_name_for_seat(player_id)
        if bot_name not in {"heuristic_v2", "heuristic_v3"}:
            return
        if decision_kind == "pass":
            payload = _serialize_heuristic_v2_pass_reason(bot)
        elif decision_kind == "play":
            payload = _serialize_heuristic_v2_play_reason(bot)
        else:
            return
        if payload is None:
            return
        self.debug_last_bot_decision = {
            "seat": int(player_id),
            "bot_name": bot_name,
            "decision_kind": decision_kind,
            "hand_number": self.state.hand_number,
            "trick_number": self.state.trick_number,
            "payload": payload,
        }


@dataclass(slots=True)
class TableManager:
    tables: dict[str, Table] = field(default_factory=dict)
    record_store: RecordStore | None = None

    @classmethod
    def with_persistence(cls, records_dir: Path | str = "records") -> TableManager:
        return cls(record_store=RecordStore(records_dir=records_dir))

    def create_table(
        self,
        *,
        display_name: str,
        target_score: int = 50,
        seed: int | None = None,
        auto_advance: bool = False,
    ) -> tuple[Table, str]:
        table_code = self._generate_table_code()
        table_seed = seed if seed is not None else secrets.randbelow(2**32)
        config = GameConfig(target_score=target_score)
        rng = random.Random(table_seed)
        state = new_game(rng=rng, config=config)
        table = Table(
            table_code=table_code,
            seed=table_seed,
            config=config,
            rng=rng,
            state=state,
            auto_advance=auto_advance,
        )
        if self.record_store is not None:
            recorder, record_path, game_id = self.record_store.create_game_recorder(
                table_code=table_code,
                seed=table_seed,
                config=config,
            )
            recorder.record_hand_dealt(state)
            table.recorder = recorder
            table.record_path = record_path
            table.summary_path = self.record_store.summary_path
            table.game_id = game_id
            table.hand_score_start = dict(state.scores)

        creator_secret = table.join(display_name=display_name)
        table.host_secret = creator_secret
        self.tables[table_code] = table
        return table, creator_secret

    def get_table(self, table_code: str) -> Table:
        table = self.tables.get(table_code.upper())
        if table is None:
            raise TableNotFoundError(f"Unknown table code: {table_code!r}.")
        return table

    def join_table(self, table_code: str, *, display_name: str) -> str:
        table = self.get_table(table_code)
        return table.join(display_name=display_name)

    def claim_seat(self, table_code: str, *, player_secret: str, seat: int) -> None:
        table = self.get_table(table_code)
        table.claim_seat(player_secret=player_secret, seat=seat)
        self._post_action(table)

    def add_bot(self, table_code: str, *, seat: int, bot_name: str = "random") -> None:
        table = self.get_table(table_code)
        table.add_bot(seat=seat, bot_name=bot_name)
        self._post_action(table)

    def set_viewer_advisory_bot(
        self,
        table_code: str,
        *,
        player_secret: str,
        bot_name: str,
    ) -> None:
        table = self.get_table(table_code)
        table.set_viewer_advisory_bot(player_secret=player_secret, bot_name=bot_name)
        self._post_action(table)

    def submit_pass(self, table_code: str, *, player_secret: str, cards: list[str]) -> None:
        table = self.get_table(table_code)
        table.submit_pass(player_secret=player_secret, cards=cards)
        self._post_action(table)

    def play_card(self, table_code: str, *, player_secret: str, card: str) -> None:
        table = self.get_table(table_code)
        table.play(player_secret=player_secret, card_code=card)
        self._post_action(table)

    def advance_one_action(self, table_code: str, *, player_secret: str) -> AdvanceResult:
        table = self.get_table(table_code)
        result = table.advance_one_action(player_secret=player_secret)
        self._post_action(table)
        return result

    def _post_action(self, table: Table) -> None:
        if table.phase != "game_over":
            return

        if table.recorder is not None and not table.game_end_recorded:
            table.recorder.record_game_ended(final_scores=table.state.scores)
            table.game_end_recorded = True

        if self.record_store is None or table.summary_written:
            return

        self.record_store.write_game_summary(
            table_code=table.table_code,
            game_id=table.game_id or table.table_code,
            seed=table.seed,
            target_score=table.config.target_score,
            hands_played=table.state.hand_number,
            final_scores={str(int(player_id)): table.state.scores[player_id] for player_id in PLAYER_IDS},
            winner_ids=_winner_ids(table.state.scores),
            record_path=str(table.record_path) if table.record_path is not None else None,
        )
        table.summary_written = True

    def _generate_table_code(self, length: int = 6) -> str:
        while True:
            code = "".join(secrets.choice(_TABLE_CODE_ALPHABET) for _ in range(length))
            if code not in self.tables:
                return code


def _winner_ids(scores: dict[PlayerId, int]) -> list[int]:
    best_score = min(scores.values())
    return sorted(int(player_id) for player_id in PLAYER_IDS if scores[player_id] == best_score)


def _card_from_code(code: str) -> Card:
    cleaned = code.strip().upper()
    if len(cleaned) < 2:
        raise InvalidTableActionError(f"Invalid card code: {code!r}.")

    rank_code = cleaned[:-1]
    suit_code = cleaned[-1]

    if suit_code not in _CARD_SUITS:
        raise InvalidTableActionError(f"Invalid card suit in card code: {code!r}.")
    if rank_code not in _CARD_RANKS:
        raise InvalidTableActionError(f"Invalid card rank in card code: {code!r}.")
    return Card(suit=_CARD_SUITS[suit_code], rank=_CARD_RANKS[rank_code])


def _serialize_heuristic_v2_pass_reason(bot: Any) -> dict[str, Any] | None:
    peek = getattr(bot, "_peek_last_pass_reason", None)
    if not callable(peek):
        return None
    reason = peek()
    if reason is None:
        return None
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


def _serialize_heuristic_v2_play_reason(bot: Any) -> dict[str, Any] | None:
    peek = getattr(bot, "_peek_last_play_reason", None)
    if not callable(peek):
        return None
    reason = peek()
    if reason is None:
        return None
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


__all__ = [
    "AdvanceResult",
    "InvalidTableActionError",
    "LastTrick",
    "Table",
    "TableError",
    "TableManager",
    "TableNotFoundError",
    "TablePhase",
    "UnauthorizedError",
]
