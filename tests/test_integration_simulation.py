import random

from hearts_ai.bots.factory import create_bots, resolve_bot_names
from hearts_ai.engine.game import apply_pass, deal, is_game_over, is_hand_over, new_game, play_card
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameConfig
from hearts_ai.engine.types import PLAYER_IDS


def _run_full_game(seed: int, target_score: int, bot_spec: str = "random") -> tuple[dict[int, int], int]:
    rng = random.Random(seed)
    state = new_game(rng=rng, config=GameConfig(target_score=target_score))
    bots = create_bots(resolve_bot_names(bot_spec))
    hands_played = 0

    while True:
        hands_played += 1
        assert all(len(state.hands[player_id]) == 13 for player_id in PLAYER_IDS)
        if not state.pass_applied:
            pass_map = {
                player_id: bots[player_id].choose_pass(state.hands[player_id], state=state, rng=rng)
                for player_id in PLAYER_IDS
            }
            apply_pass(state=state, pass_map=pass_map)

        cards_played = 0
        while not is_hand_over(state):
            player_id = state.turn
            assert player_id is not None
            card = bots[player_id].choose_play(state=state, rng=rng)
            assert card in legal_moves(state=state, player_id=player_id)
            play_card(state=state, player_id=player_id, card=card)
            cards_played += 1

        assert cards_played == 52
        assert state.hand_scored is True
        assert state.trick_number == 13
        assert all(len(state.hands[player_id]) == 0 for player_id in PLAYER_IDS)

        if is_game_over(state):
            break
        deal(state=state, rng=rng)

    return {int(player_id): state.scores[player_id] for player_id in PLAYER_IDS}, hands_played


def test_engine_full_game_deterministic_with_random_bots() -> None:
    result_one = _run_full_game(seed=11, target_score=50)
    result_two = _run_full_game(seed=11, target_score=50)

    assert result_one == result_two
    final_scores, hands_played = result_one
    assert hands_played >= 1
    assert any(score >= 50 for score in final_scores.values())


def test_engine_full_game_fixed_seed_snapshot() -> None:
    final_scores, hands_played = _run_full_game(seed=1, target_score=50)

    assert hands_played == 7
    assert final_scores == {0: 49, 1: 30, 2: 51, 3: 52}


def test_engine_full_game_deterministic_with_heuristic_bots() -> None:
    result_one = _run_full_game(seed=11, target_score=50, bot_spec="heuristic")
    result_two = _run_full_game(seed=11, target_score=50, bot_spec="heuristic")

    assert result_one == result_two
    final_scores, hands_played = result_one
    assert hands_played >= 1
    assert any(score >= 50 for score in final_scores.values())


def test_engine_full_game_fixed_seed_snapshot_with_heuristic_bots() -> None:
    final_scores, hands_played = _run_full_game(seed=1, target_score=50, bot_spec="heuristic")

    assert hands_played == 6
    assert final_scores == {0: 41, 1: 22, 2: 35, 3: 58}
