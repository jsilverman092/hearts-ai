from __future__ import annotations

import random
import secrets
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.game import apply_pass, deal, is_game_over, is_hand_over, new_game, play_card
from hearts_ai.engine.record import GameRecorder
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId, to_player_id
from hearts_ai.server.persistence import RecordStore

TablePhase = Literal["lobby", "passing", "playing", "hand_scoring", "game_over"]

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


def _empty_seat_secrets() -> dict[PlayerId, str | None]:
    return {player_id: None for player_id in PLAYER_IDS}


def _zero_scores() -> dict[PlayerId, int]:
    return {player_id: 0 for player_id in PLAYER_IDS}


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
    pending_passes: dict[PlayerId, list[Card]] = field(default_factory=dict)
    version: int = 0
    recorder: GameRecorder | None = None
    game_id: str | None = None
    record_path: Path | None = None
    summary_path: Path | None = None
    hand_score_start: dict[PlayerId, int] = field(default_factory=_zero_scores)
    last_recorded_scored_hand: int = 0
    game_end_recorded: bool = False
    summary_written: bool = False

    def join(self, display_name: str) -> str:
        if not display_name.strip():
            raise InvalidTableActionError("Display name must not be empty.")
        player_secret = secrets.token_urlsafe(16)
        self.participants[player_secret] = Participant(display_name=display_name.strip())
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

    def add_bot(self, seat: int) -> None:
        player_id = to_player_id(seat)
        current_secret = self.seat_secrets[player_id]
        if current_secret is not None:
            raise InvalidTableActionError(f"Seat {seat} is occupied by a human player.")
        self.bot_seats.add(player_id)
        self.version += 1
        self._maybe_start_game()

    def submit_pass(self, player_secret: str, cards: list[str]) -> None:
        if self.phase != "passing":
            raise InvalidTableActionError("Pass submissions are only allowed during the passing phase.")
        player_id = self._require_seated_human(player_secret)
        if player_id in self.pending_passes:
            raise InvalidTableActionError("Pass already submitted for this hand.")
        self.pending_passes[player_id] = [_card_from_code(code) for code in cards]
        self.version += 1
        self._advance_to_next_human_action()

    def play(self, player_secret: str, card_code: str) -> None:
        if self.phase != "playing":
            raise InvalidTableActionError("Card play is only allowed during the playing phase.")
        player_id = self._require_seated_human(player_secret)
        if self.state.turn != player_id:
            raise InvalidTableActionError(
                f"It is player {int(self.state.turn) if self.state.turn is not None else 'none'}'s turn."
            )
        card = _card_from_code(card_code)
        play_card(state=self.state, player_id=player_id, card=card)
        self._record_card_played(player_id=player_id, card=card)
        self.version += 1
        self._advance_to_next_human_action()

    def seat_display_name(self, player_id: PlayerId) -> str | None:
        seat_secret = self.seat_secrets[player_id]
        if seat_secret is None:
            return None
        participant = self.participants.get(seat_secret)
        return participant.display_name if participant is not None else None

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
        self._advance_to_next_human_action()

    def _advance_to_next_human_action(self) -> None:
        while True:
            progressed = False

            if self.phase == "passing":
                for player_id in PLAYER_IDS:
                    if player_id in self.pending_passes:
                        continue
                    if player_id in self.bot_seats:
                        bot = RandomBot(player_id=player_id)
                        self.pending_passes[player_id] = bot.choose_pass(
                            hand=self.state.hands[player_id],
                            state=self.state,
                            rng=self.rng,
                        )
                        progressed = True

                if len(self.pending_passes) == len(PLAYER_IDS):
                    pass_map = dict(self.pending_passes)
                    apply_pass(state=self.state, pass_map=pass_map)
                    self._record_pass_applied(pass_map=pass_map)
                    self.pending_passes.clear()
                    self.phase = "playing"
                    progressed = True
                    self.version += 1
                else:
                    break

            if self.phase == "playing":
                if is_hand_over(self.state):
                    self.phase = "hand_scoring"
                    progressed = True
                    self.version += 1

                while self.phase == "playing":
                    if is_hand_over(self.state):
                        self.phase = "hand_scoring"
                        progressed = True
                        self.version += 1
                        break

                    if self.state.turn is None:
                        raise InvalidTableActionError("Game state turn is unset during playing phase.")
                    if self.state.turn not in self.bot_seats:
                        break

                    bot_player = self.state.turn
                    bot = RandomBot(player_id=bot_player)
                    card = bot.choose_play(state=self.state, rng=self.rng)
                    play_card(state=self.state, player_id=bot_player, card=card)
                    self._record_card_played(player_id=bot_player, card=card)
                    progressed = True
                    self.version += 1

                    if is_hand_over(self.state):
                        self.phase = "hand_scoring"
                        progressed = True
                        self.version += 1
                        break

                if self.phase == "playing" and self.state.turn not in self.bot_seats:
                    break

            if self.phase == "hand_scoring":
                if not self.state.hand_scored or not is_hand_over(self.state):
                    raise InvalidTableActionError("Cannot transition from hand_scoring before hand completion.")
                self._record_hand_scored_if_needed()

                if is_game_over(self.state):
                    self.phase = "game_over"
                    self.version += 1
                    break

                deal(state=self.state, rng=self.rng)
                if self.recorder is not None:
                    self.recorder.record_hand_dealt(self.state)
                self.pending_passes.clear()
                self.phase = "playing" if self.state.pass_applied else "passing"
                self.hand_score_start = dict(self.state.scores)
                self.version += 1
                progressed = True
                continue

            if self.phase in {"lobby", "game_over"}:
                break

            if not progressed:
                break

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

    def add_bot(self, table_code: str, *, seat: int) -> None:
        table = self.get_table(table_code)
        table.add_bot(seat=seat)
        self._post_action(table)

    def submit_pass(self, table_code: str, *, player_secret: str, cards: list[str]) -> None:
        table = self.get_table(table_code)
        table.submit_pass(player_secret=player_secret, cards=cards)
        self._post_action(table)

    def play_card(self, table_code: str, *, player_secret: str, card: str) -> None:
        table = self.get_table(table_code)
        table.play(player_secret=player_secret, card_code=card)
        self._post_action(table)

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


__all__ = [
    "InvalidTableActionError",
    "Table",
    "TableError",
    "TableManager",
    "TableNotFoundError",
    "TablePhase",
    "UnauthorizedError",
]
