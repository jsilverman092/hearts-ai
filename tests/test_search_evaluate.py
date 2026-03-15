from __future__ import annotations

from statistics import fmean

from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import (
    RootCandidateEvaluation,
    RootMoveEvaluationSet,
    build_root_move_candidates,
    build_search_player_view,
    evaluate_root_candidates,
    rank_root_candidate_evaluations,
    select_best_root_candidate,
)
from hearts_ai.search.candidates import RootMoveCandidate
from hearts_ai.search.worlds import DeterminizedWorldSet


def test_evaluate_root_candidates_is_deterministic_under_fixed_seed() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    view = build_search_player_view(state=state, player_id=PlayerId(0))

    first = evaluate_root_candidates(view=view, seed=41, world_count=4)
    second = evaluate_root_candidates(view=view, seed=41, world_count=4)

    assert first == second


def test_evaluate_root_candidates_is_invariant_to_hidden_live_assignment() -> None:
    first_state = _full_state_with_rotating_hidden_hands(rotation=0)
    second_state = _full_state_with_rotating_hidden_hands(rotation=1)

    first_view = build_search_player_view(state=first_state, player_id=PlayerId(0))
    second_view = build_search_player_view(state=second_state, player_id=PlayerId(0))

    first = evaluate_root_candidates(view=first_view, seed=73, world_count=3)
    second = evaluate_root_candidates(view=second_view, seed=73, world_count=3)

    assert first == second


def test_evaluate_root_candidates_aggregates_root_metrics_from_rollouts() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    view = build_search_player_view(state=state, player_id=PlayerId(0))

    evaluation = evaluate_root_candidates(view=view, seed=19, world_count=3)

    assert len(evaluation.world_set.worlds) == 3
    assert len(evaluation.candidate_evaluations) == len(build_root_move_candidates(view))

    for candidate_evaluation in evaluation.candidate_evaluations:
        summaries = candidate_evaluation.rollout_summaries
        assert len(summaries) == 3
        assert candidate_evaluation.average_projected_raw_hand_points == fmean(
            summary.projected_raw_hand_points[PlayerId(0)]
            for summary in summaries
        )
        assert candidate_evaluation.average_projected_hand_points == fmean(
            summary.projected_hand_points[PlayerId(0)]
            for summary in summaries
        )
        assert candidate_evaluation.average_projected_score_delta == fmean(
            summary.projected_score_deltas[PlayerId(0)]
            for summary in summaries
        )
        assert candidate_evaluation.average_projected_total_score == fmean(
            summary.projected_scores[PlayerId(0)]
            for summary in summaries
        )
        assert candidate_evaluation.average_root_utility == fmean(
            summary.root_utility
            for summary in summaries
        )


def test_select_best_root_candidate_uses_stable_metric_tiebreak_order() -> None:
    first = _candidate_evaluation(
        card=Card(Suit.CLUBS, Rank.FIVE),
        candidate_index=0,
        score_delta=3.0,
        hand_points=2.0,
        total_score=9.0,
    )
    second = _candidate_evaluation(
        card=Card(Suit.CLUBS, Rank.SIX),
        candidate_index=1,
        score_delta=3.0,
        hand_points=1.0,
        total_score=9.0,
    )
    third = _candidate_evaluation(
        card=Card(Suit.CLUBS, Rank.SEVEN),
        candidate_index=2,
        score_delta=2.0,
        hand_points=8.0,
        total_score=9.0,
    )
    evaluation_set = RootMoveEvaluationSet(
        root_player_id=PlayerId(0),
        base_seed=11,
        world_set=DeterminizedWorldSet(root_player_id=PlayerId(0), base_seed=11, worlds=()),
        candidate_evaluations=(first, second, third),
    )

    ranked = rank_root_candidate_evaluations(evaluation_set)

    assert ranked == (third, second, first)
    assert select_best_root_candidate(evaluation_set) == third


def test_select_best_root_candidate_breaks_exact_ties_by_original_candidate_index() -> None:
    first = _candidate_evaluation(
        card=Card(Suit.SPADES, Rank.THREE),
        candidate_index=0,
        score_delta=4.0,
        hand_points=4.0,
        total_score=12.0,
    )
    second = _candidate_evaluation(
        card=Card(Suit.SPADES, Rank.FOUR),
        candidate_index=1,
        score_delta=4.0,
        hand_points=4.0,
        total_score=12.0,
    )
    evaluation_set = RootMoveEvaluationSet(
        root_player_id=PlayerId(0),
        base_seed=13,
        world_set=DeterminizedWorldSet(root_player_id=PlayerId(0), base_seed=13, worlds=()),
        candidate_evaluations=(second, first),
    )

    assert rank_root_candidate_evaluations(evaluation_set) == (first, second)
    assert select_best_root_candidate(evaluation_set) == first


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


def _candidate_evaluation(
    *,
    card: Card,
    candidate_index: int,
    score_delta: float,
    raw_hand_points: float | None = None,
    hand_points: float,
    total_score: float,
) -> RootCandidateEvaluation:
    average_projected_raw_hand_points = hand_points if raw_hand_points is None else raw_hand_points
    return RootCandidateEvaluation(
        candidate=RootMoveCandidate(
            card=card,
            mode="lead",
            follows_led_suit=False,
            is_point_card=False,
            trick_points_so_far=0,
        ),
        candidate_index=candidate_index,
        rollout_summaries=(),
        average_projected_raw_hand_points=average_projected_raw_hand_points,
        average_projected_hand_points=hand_points,
        average_projected_score_delta=score_delta,
        average_projected_total_score=total_score,
        average_root_utility=-score_delta,
    )
