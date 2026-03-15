from __future__ import annotations

from copy import deepcopy

from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.game import is_hand_over, score_hand
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import (
    DeterminizedWorld,
    HeuristicPlayoutConfig,
    RootMoveCandidate,
    build_deterministic_playout_bots,
    build_root_move_candidates,
    build_search_player_view,
    clone_determinized_state,
    sample_determinized_world,
    sample_determinized_worlds,
    simulate_root_candidate,
    summarize_rollout,
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
    assert first.summary.projected_raw_hand_points[PlayerId(0)] >= first.summary.projected_hand_points[PlayerId(0)]
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
        assert result.summary.projected_raw_hand_points[PlayerId(0)] >= result.summary.projected_hand_points[PlayerId(0)]


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


def test_summarize_rollout_scores_successful_moon_as_zero_delta_for_shooter() -> None:
    final_state = GameState()
    final_state.hands = {player_id: [] for player_id in PLAYER_IDS}
    final_state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}
    final_state.trick_in_progress = []
    final_state.scores = {
        PlayerId(0): 18,
        PlayerId(1): 7,
        PlayerId(2): 12,
        PlayerId(3): 20,
    }

    moon_cards = [
        Card(Suit.HEARTS, Rank.TWO),
        Card(Suit.HEARTS, Rank.THREE),
        Card(Suit.HEARTS, Rank.FOUR),
        Card(Suit.HEARTS, Rank.FIVE),
        Card(Suit.HEARTS, Rank.SIX),
        Card(Suit.HEARTS, Rank.SEVEN),
        Card(Suit.HEARTS, Rank.EIGHT),
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.TEN),
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.HEARTS, Rank.QUEEN),
        Card(Suit.HEARTS, Rank.KING),
    ]
    final_state.taken_tricks[PlayerId(0)] = [
        [(PlayerId(0), card)]
        for card in moon_cards
    ] + [[
        (PlayerId(0), Card(Suit.HEARTS, Rank.ACE)),
        (PlayerId(0), Card(Suit.SPADES, Rank.QUEEN)),
    ]]

    assert is_hand_over(final_state) is True
    starting_scores = dict(final_state.scores)
    score_hand(final_state)

    world = DeterminizedWorld(
        root_player_id=PlayerId(0),
        sample_index=0,
        sample_seed=11,
        hidden_hands={
            PlayerId(1): (),
            PlayerId(2): (),
            PlayerId(3): (),
        },
        state=final_state,
    )
    candidate = RootMoveCandidate(
        card=Card(Suit.CLUBS, Rank.TWO),
        mode="lead",
        follows_led_suit=False,
        is_point_card=False,
        trick_points_so_far=0,
    )

    summary = summarize_rollout(
        world=world,
        candidate=candidate,
        starting_scores=starting_scores,
        final_state=final_state,
    )

    assert summary.projected_raw_hand_points[PlayerId(0)] == 26
    assert summary.projected_hand_points[PlayerId(0)] == 0
    assert summary.projected_score_deltas[PlayerId(0)] == 0
    assert summary.projected_scores[PlayerId(0)] == starting_scores[PlayerId(0)]
    assert summary.root_utility == 0.0
    assert summary.projected_hand_points[PlayerId(1)] == 26
    assert summary.projected_hand_points[PlayerId(2)] == 26
    assert summary.projected_hand_points[PlayerId(3)] == 26


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
