from __future__ import annotations

import argparse
import random
from typing import Sequence

from hearts_ai.bots.random_bot import RandomBot
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.game import apply_pass, deal, is_game_over, is_hand_over, new_game, play_card
from hearts_ai.engine.state import GameConfig, GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId


def simulate_games(seed: int, games: int, target_score: int) -> list[str]:
    if games <= 0:
        raise ValueError(f"games must be > 0, got {games}")
    if target_score <= 0:
        raise ValueError(f"target_score must be > 0, got {target_score}")

    rng = random.Random(seed)
    output_lines: list[str] = []

    for game_index in range(1, games + 1):
        config = GameConfig(target_score=target_score)
        state = new_game(rng=rng, config=config)
        bots = {player_id: RandomBot(player_id=player_id) for player_id in PLAYER_IDS}

        while True:
            hand_number = state.hand_number
            pass_direction = state.pass_direction
            score_before = dict(state.scores)
            _play_hand(state=state, bots=bots, rng=rng)
            hand_delta = {player_id: state.scores[player_id] - score_before[player_id] for player_id in PLAYER_IDS}
            output_lines.append(
                f"GAME {game_index} HAND {hand_number} PASS {pass_direction} "
                f"DELTA {_format_scores(hand_delta)} TOTAL {_format_scores(state.scores)}"
            )

            if is_game_over(state):
                winners = _winner_ids(state.scores)
                winner_label = ",".join(f"P{player_id}" for player_id in winners)
                output_lines.append(
                    f"GAME {game_index} FINAL {_format_scores(state.scores)} WINNER {winner_label}"
                )
                break

            deal(state=state, rng=rng)

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

    args = parser.parse_args(argv)
    if args.command == "play":
        lines = simulate_games(seed=args.seed, games=args.games, target_score=args.target_score)
        for line in lines:
            print(line)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _play_hand(state: GameState, bots: dict[PlayerId, RandomBot], rng: random.Random) -> None:
    if not state.pass_applied:
        pass_map = {
            player_id: bots[player_id].choose_pass(hand=state.hands[player_id], state=state, rng=rng)
            for player_id in PLAYER_IDS
        }
        apply_pass(state=state, pass_map=pass_map)

    while not is_hand_over(state):
        player_id = state.turn
        if player_id is None:
            raise InvalidStateError("State turn is unset during active hand.")
        card = bots[player_id].choose_play(state=state, rng=rng)
        play_card(state=state, player_id=player_id, card=card)


def _format_scores(scores: dict[PlayerId, int]) -> str:
    return " ".join(f"P{int(player_id)}={scores[player_id]}" for player_id in PLAYER_IDS)


def _winner_ids(scores: dict[PlayerId, int]) -> list[int]:
    best_score = min(scores.values())
    return [int(player_id) for player_id in PLAYER_IDS if scores[player_id] == best_score]


__all__ = ["main", "simulate_games"]
