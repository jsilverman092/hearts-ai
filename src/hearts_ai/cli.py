from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Sequence

from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.game import apply_pass, deal, is_game_over, is_hand_over, new_game, play_card
from hearts_ai.engine.record import GameRecorder, replay_jsonl
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId


def simulate_games(
    seed: int,
    games: int,
    target_score: int,
    record_path: str | None = None,
) -> list[str]:
    if games <= 0:
        raise ValueError(f"games must be > 0, got {games}")
    if target_score <= 0:
        raise ValueError(f"target_score must be > 0, got {target_score}")

    rng = random.Random(seed)
    output_lines: list[str] = []
    record_file = Path(record_path) if record_path is not None else None
    if record_file is not None:
        record_file.parent.mkdir(parents=True, exist_ok=True)
        record_file.write_text("", encoding="utf-8")

    for game_index in range(1, games + 1):
        config = GameConfig(target_score=target_score)
        state = new_game(rng=rng, config=config)
        bots = {player_id: RandomBot(player_id=player_id) for player_id in PLAYER_IDS}
        recorder = (
            GameRecorder(path=record_file, game_id=f"game-{game_index}") if record_file is not None else None
        )
        if recorder is not None:
            recorder.record_game_created(config=config, seed=seed)
            recorder.record_hand_dealt(state)

        while True:
            hand_number = state.hand_number
            pass_direction = state.pass_direction
            score_before = dict(state.scores)
            _play_hand(state=state, bots=bots, rng=rng, recorder=recorder)
            hand_delta = {player_id: state.scores[player_id] - score_before[player_id] for player_id in PLAYER_IDS}
            if recorder is not None:
                recorder.record_hand_scored(
                    hand_index=hand_number,
                    delta_scores=hand_delta,
                    total_scores=state.scores,
                )
            output_lines.append(
                f"GAME {game_index} HAND {hand_number} PASS {pass_direction} "
                f"DELTA {_format_scores(hand_delta)} TOTAL {_format_scores(state.scores)}"
            )

            if is_game_over(state):
                if recorder is not None:
                    recorder.record_game_ended(final_scores=state.scores)
                winners = _winner_ids(state.scores)
                winner_label = ",".join(f"P{player_id}" for player_id in winners)
                output_lines.append(
                    f"GAME {game_index} FINAL {_format_scores(state.scores)} WINNER {winner_label}"
                )
                break

            deal(state=state, rng=rng)
            if recorder is not None:
                recorder.record_hand_dealt(state)

    return output_lines


def replay_records(path: str) -> list[str]:
    results = replay_jsonl(path)
    output_lines: list[str] = []
    for game_id, state in results:
        winners = _winner_ids(state.scores)
        winner_label = ",".join(f"P{player_id}" for player_id in winners)
        output_lines.append(
            f"REPLAY {game_id} HANDS {state.hand_number} "
            f"FINAL {_format_scores(state.scores)} WINNER {winner_label}"
        )
    return output_lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hearts_ai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    play_parser = subparsers.add_parser("play", help="Run one or more Hearts game simulations.")
    play_parser.add_argument("--seed", type=int, default=1, help="Random seed for deterministic games.")
    play_parser.add_argument("--games", type=int, default=1, help="Number of games to simulate.")
    play_parser.add_argument(
        "--target-score",
        type=int,
        default=50,
        help="Game ends when any player reaches this score.",
    )
    play_parser.add_argument(
        "--record",
        type=str,
        default=None,
        help="Optional JSONL path to record replayable game events.",
    )

    replay_parser = subparsers.add_parser("replay", help="Replay and verify one or more recorded games.")
    replay_parser.add_argument("path", type=str, help="Path to replay JSONL file.")

    serve_parser = subparsers.add_parser("serve", help="Run local multiplayer server.")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Server bind host.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Server bind port.")

    args = parser.parse_args(argv)
    if args.command == "play":
        lines = simulate_games(
            seed=args.seed,
            games=args.games,
            target_score=args.target_score,
            record_path=args.record,
        )
        for line in lines:
            print(line)
        return 0

    if args.command == "replay":
        lines = replay_records(path=args.path)
        for line in lines:
            print(line)
        return 0

    if args.command == "serve":
        try:
            from hearts_ai.server.app import run_server
        except ImportError as exc:
            parser.error(
                "Server dependencies are not installed. Install with: "
                'python -m pip install -e ".[server]"'
            )
            raise AssertionError("unreachable") from exc
        run_server(host=args.host, port=args.port)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _play_hand(
    state: GameState,
    bots: dict[PlayerId, RandomBot],
    rng: random.Random,
    recorder: GameRecorder | None = None,
) -> None:
    if not state.pass_applied:
        pass_map = {
            player_id: bots[player_id].choose_pass(hand=state.hands[player_id], state=state, rng=rng)
            for player_id in PLAYER_IDS
        }
        apply_pass(state=state, pass_map=pass_map)
        if recorder is not None:
            recorder.record_pass_applied(hand_index=state.hand_number, pass_map=pass_map)

    while not is_hand_over(state):
        player_id = state.turn
        if player_id is None:
            raise InvalidStateError("State turn is unset during active hand.")
        card = bots[player_id].choose_play(state=state, rng=rng)
        play_card(state=state, player_id=player_id, card=card)
        if recorder is not None:
            recorder.record_card_played(hand_index=state.hand_number, player_id=player_id, card=card)


def _format_scores(scores: dict[PlayerId, int]) -> str:
    return " ".join(f"P{int(player_id)}={scores[player_id]}" for player_id in PLAYER_IDS)


def _winner_ids(scores: dict[PlayerId, int]) -> list[int]:
    best_score = min(scores.values())
    return [int(player_id) for player_id in PLAYER_IDS if scores[player_id] == best_score]


__all__ = ["main", "replay_records", "simulate_games"]
