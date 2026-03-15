from __future__ import annotations

from copy import deepcopy

from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.engine.cards import make_deck
from hearts_ai.engine.game import is_hand_over
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import (
    HeuristicPlayoutConfig,
    build_deterministic_playout_bots,
    build_root_move_candidates,
    build_search_player_view,
    clone_determinized_state,
    sample_determinized_world,
    sample_determinized_worlds,
    simulate_root_candidate,
)


def test_build_deterministic_playout_bots_use_rollout_disabled_heuristic_v3() -> None:
    bots = build_deterministic_playout_bots(config=HeuristicPlayoutConfig())

    assert tuple(sorted(bots)) == PLAYER_IDS
    assert all(isinstance(bot, HeuristicBotV3) for bot in bots.values())
    assert all(bot.rollout_samples == 0 for bot in bots.values())
    assert all(bot.rollout_weight == 0.0 for bot in bots.values())


def test_simulate_root_candidate_is_deterministic_under_fixed_seed() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    view = build_search_player_view(state=state, player_id=PlayerId(0))
    candidate = build_root_move_candidates(view)[0]
    world = sample_determinized_world(view=view, seed=29)

    first = simulate_root_candidate(world=world, candidate=candidate, seed=101)
    second = simulate_root_candidate(world=world, candidate=candidate, seed=101)

    assert first.summary == second.summary
    assert first.final_state == second.final_state
    assert is_hand_over(first.final_state) is True
    assert first.final_state.hand_scored is True
    assert first.summary.projected_hand_points == first.summary.projected_score_deltas
    assert first.summary.root_utility == -float(first.summary.projected_score_deltas[PlayerId(0)])


def test_simulate_root_candidate_completes_each_sampled_world_legally() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    view = build_search_player_view(state=state, player_id=PlayerId(0))
    candidate = build_root_move_candidates(view)[0]
    world_set = sample_determinized_worlds(view=view, seed=43, world_count=3)

    results = [
        simulate_root_candidate(world=world, candidate=candidate)
        for world in world_set.worlds
    ]

    assert len(results) == 3
    for result in results:
        assert is_hand_over(result.final_state) is True
        assert result.final_state.hand_scored is True
        assert result.final_state.trick_number == 13
        assert all(len(result.final_state.hands[player_id]) == 0 for player_id in PLAYER_IDS)
        assert result.summary.projected_hand_points == result.summary.projected_score_deltas


def test_simulate_root_candidate_does_not_mutate_source_world_or_source_state() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    view = build_search_player_view(state=state, player_id=PlayerId(0))
    candidate = build_root_move_candidates(view)[0]
    world = sample_determinized_world(view=view, seed=17)
    world_before = deepcopy(world.state)
    hidden_before = dict(world.hidden_hands)

    cloned = clone_determinized_state(world=world)
    cloned.hands[PlayerId(0)].pop()

    assert world.state == world_before
    assert dict(world.hidden_hands) == hidden_before

    result = simulate_root_candidate(world=world, candidate=candidate, seed=203)

    assert result.final_state is not world.state
    assert world.state == world_before
    assert dict(world.hidden_hands) == hidden_before
    assert candidate.card in world.state.hands[PlayerId(0)]


def _full_state_with_rotating_hidden_hands(*, rotation: int) -> GameState:
    deck = tuple(make_deck())
    own_hand = list(deck[:13])
    hidden_chunks = [
        list(deck[13:26]),
        list(deck[26:39]),
        list(deck[39:52]),
    ]
    hidden_chunks = hidden_chunks[rotation:] + hidden_chunks[:rotation]

    state = GameState()
    state.hands = {
        PlayerId(0): sorted(own_hand),
        PlayerId(1): sorted(hidden_chunks[0]),
        PlayerId(2): sorted(hidden_chunks[1]),
        PlayerId(3): sorted(hidden_chunks[2]),
    }
    state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}
    state.scores = {player_id: 0 for player_id in PLAYER_IDS}
    state.turn = PlayerId(0)
    state.trick_number = 0
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = True
    return state
