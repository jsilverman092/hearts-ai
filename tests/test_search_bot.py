import random
from copy import deepcopy

import pytest

import hearts_ai.bots.search.bots as search_bot_module
from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.bots.search import SearchBotConfig, SearchBotV1, SearchPlayDecisionReason
from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import (
    RootCandidateEvaluation,
    RootMoveEvaluationSet,
    SearchRolloutSummary,
    build_root_move_candidates,
)
from hearts_ai.search.worlds import DeterminizedWorldSet
from hearts_ai.search.worlds import ImpossibleWorldError


def test_search_bot_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        SearchBotConfig(world_count=0)

    with pytest.raises(ValueError):
        SearchBotConfig(playout_seed_offset=-1)

    defaults = SearchBotConfig()
    assert defaults.world_count == 1
    assert defaults.fallback_to_heuristic_v3_on_impossible_world is True
    assert defaults.fallback_to_heuristic_v3_on_empty_world_set is True


def test_search_bot_v1_choose_pass_matches_heuristic_v3() -> None:
    state = GameState()
    state.pass_direction = "left"
    hand = [
        Card(Suit.SPADES, Rank.QUEEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.TWO),
    ]
    search_bot = SearchBotV1(player_id=PlayerId(0))
    heuristic_bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0, rollout_weight=0.0)

    search_pass = search_bot.choose_pass(hand=hand, state=state, rng=random.Random(7))
    heuristic_pass = heuristic_bot.choose_pass(hand=hand, state=state, rng=random.Random(7))

    assert search_pass == heuristic_pass
    assert search_bot.peek_last_decision_reason("pass") == heuristic_bot.peek_last_decision_reason("pass")


def test_search_bot_v1_choose_play_returns_legal_move() -> None:
    deck = tuple(make_deck())
    state = GameState()
    state.hands = {
        PlayerId(0): sorted(deck[:13]),
        PlayerId(1): sorted(deck[13:26]),
        PlayerId(2): sorted(deck[26:39]),
        PlayerId(3): sorted(deck[39:52]),
    }
    state.taken_tricks = {player_id: [] for player_id in PLAYER_IDS}
    state.hearts_broken = True
    state.turn = PlayerId(0)
    state.trick_number = 3
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = True

    bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=2))
    card = bot.choose_play(state=state, rng=random.Random(123))

    assert card in legal_moves(state=state, player_id=PlayerId(0))


def test_search_bot_v1_choose_play_uses_search_evaluation_and_private_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.FIVE), Card(Suit.SPADES, Rank.ACE)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.trick_in_progress = []
    state.hearts_broken = True
    state.turn = PlayerId(0)
    state.trick_number = 3
    state.pass_direction = "left"
    state.pass_applied = True

    seen: dict[str, object] = {}

    def fake_evaluate_root_candidates(
        *,
        view,
        seed: int,
        world_count: int,
        playout_seed_offset: int = 0,
        playout_config=None,
    ) -> RootMoveEvaluationSet:
        candidates = build_root_move_candidates(view)
        seen["seed"] = seed
        seen["world_count"] = world_count
        seen["playout_seed_offset"] = playout_seed_offset
        seen["playout_config"] = playout_config
        seen["passed_card_seen"] = view.private_knowledge.has_passed_card(
            card=Card(Suit.HEARTS, Rank.ACE),
            recipient=PlayerId(1),
        )
        first_summary_a = _rollout_summary(candidate=candidates[0], sample_index=0, score_delta=8, hand_points=8)
        first_summary_b = _rollout_summary(candidate=candidates[0], sample_index=1, score_delta=6, hand_points=6)
        second_summary_a = _rollout_summary(candidate=candidates[1], sample_index=0, score_delta=3, hand_points=3)
        second_summary_b = _rollout_summary(candidate=candidates[1], sample_index=1, score_delta=1, hand_points=1)
        return RootMoveEvaluationSet(
            root_player_id=view.player_id,
            base_seed=seed,
            world_set=DeterminizedWorldSet(
                root_player_id=view.player_id,
                base_seed=seed,
                worlds=(object(), object()),
            ),
            candidate_evaluations=(
                RootCandidateEvaluation(
                    candidate=candidates[0],
                    candidate_index=0,
                    rollout_summaries=(first_summary_a, first_summary_b),
                    average_projected_hand_points=7.0,
                    average_projected_score_delta=7.0,
                    average_projected_total_score=7.0,
                    average_root_utility=-7.0,
                ),
                RootCandidateEvaluation(
                    candidate=candidates[1],
                    candidate_index=1,
                    rollout_summaries=(second_summary_a, second_summary_b),
                    average_projected_hand_points=2.0,
                    average_projected_score_delta=2.0,
                    average_projected_total_score=2.0,
                    average_root_utility=-2.0,
                ),
            ),
        )

    monkeypatch.setattr(search_bot_module, "evaluate_root_candidates", fake_evaluate_root_candidates)
    monkeypatch.setattr(
        search_bot_module,
        "_choose_baseline_heuristic_card",
        lambda **kwargs: Card(Suit.CLUBS, Rank.FIVE),
    )

    bot = SearchBotV1(
        player_id=PlayerId(0),
        config=SearchBotConfig(world_count=5, playout_seed_offset=17),
    )
    bot.on_new_hand(state)
    bot.on_own_pass_selected(
        state=state,
        selected_cards=(Card(Suit.HEARTS, Rank.ACE),),
        recipient=PlayerId(1),
    )

    chosen = bot.choose_play(state=state, rng=random.Random(123))

    assert chosen == Card(Suit.SPADES, Rank.ACE)
    assert seen["world_count"] == 5
    assert seen["playout_seed_offset"] == 17
    assert seen["passed_card_seen"] is True
    assert isinstance(seen["seed"], int)
    reason = bot.peek_last_decision_reason("play")
    assert isinstance(reason, SearchPlayDecisionReason)
    assert reason.chosen_card == Card(Suit.SPADES, Rank.ACE)
    assert reason.legal_move_count == 2
    assert reason.evaluated_candidate_count == 2
    assert reason.current_trick_size == 0
    assert reason.led_suit is None
    assert reason.chosen.card == Card(Suit.SPADES, Rank.ACE)
    assert reason.chosen.mode == "lead"
    assert reason.chosen.candidate_index == 1
    assert reason.chosen.follows_led_suit is False
    assert reason.chosen.is_point_card is False
    assert reason.chosen.trick_points_so_far == 0
    assert reason.chosen.average_projected_hand_points == 2.0
    assert reason.chosen.average_projected_score_delta == 2.0
    assert reason.chosen.average_projected_total_score == 2.0
    assert reason.chosen.average_root_utility == -2.0
    assert reason.requested_world_count == 5
    assert reason.world_count == 2
    assert reason.selection_source == "search"
    assert reason.fallback_message is None
    assert reason.baseline_comparison is not None
    assert reason.baseline_comparison.baseline_bot_name == "heuristic_v3"
    assert reason.baseline_comparison.agrees_with_search is False
    assert reason.baseline_comparison.baseline.card == Card(Suit.CLUBS, Rank.FIVE)
    assert reason.baseline_comparison.baseline.selection_rank == 2
    assert reason.baseline_comparison.mean_projected_score_delta_advantage == 5.0
    assert reason.baseline_comparison.mean_root_utility_gain == 5.0
    assert reason.baseline_comparison.worlds_search_better == 2
    assert reason.baseline_comparison.worlds_tied == 0
    assert reason.baseline_comparison.worlds_baseline_better == 0
    assert reason.baseline_comparison.worst_case_root_utility_loss == 0.0
    assert reason.baseline_comparison.best_case_root_utility_gain == 5.0
    assert reason.candidates[0].selected is True
    assert reason.candidates[0].card == Card(Suit.SPADES, Rank.ACE)
    assert reason.candidates[0].selection_rank == 1


def test_search_bot_v1_marks_baseline_comparison_agreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.FIVE), Card(Suit.SPADES, Rank.ACE)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.trick_in_progress = []
    state.hearts_broken = True
    state.turn = PlayerId(0)
    state.trick_number = 3
    state.pass_direction = "left"
    state.pass_applied = True

    def fake_evaluate_root_candidates(**kwargs) -> RootMoveEvaluationSet:
        candidates = build_root_move_candidates(kwargs["view"])
        first_summary = _rollout_summary(candidate=candidates[0], sample_index=0, score_delta=4, hand_points=4)
        second_summary = _rollout_summary(candidate=candidates[1], sample_index=0, score_delta=1, hand_points=1)
        return RootMoveEvaluationSet(
            root_player_id=kwargs["view"].player_id,
            base_seed=kwargs["seed"],
            world_set=DeterminizedWorldSet(
                root_player_id=kwargs["view"].player_id,
                base_seed=kwargs["seed"],
                worlds=(object(),),
            ),
            candidate_evaluations=(
                RootCandidateEvaluation(
                    candidate=candidates[0],
                    candidate_index=0,
                    rollout_summaries=(first_summary,),
                    average_projected_hand_points=4.0,
                    average_projected_score_delta=4.0,
                    average_projected_total_score=4.0,
                    average_root_utility=-4.0,
                ),
                RootCandidateEvaluation(
                    candidate=candidates[1],
                    candidate_index=1,
                    rollout_summaries=(second_summary,),
                    average_projected_hand_points=1.0,
                    average_projected_score_delta=1.0,
                    average_projected_total_score=1.0,
                    average_root_utility=-1.0,
                ),
            ),
        )

    monkeypatch.setattr(search_bot_module, "evaluate_root_candidates", fake_evaluate_root_candidates)
    monkeypatch.setattr(
        search_bot_module,
        "_choose_baseline_heuristic_card",
        lambda **kwargs: Card(Suit.SPADES, Rank.ACE),
    )

    bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=3))
    chosen = bot.choose_play(state=state, rng=random.Random(151))

    assert chosen == Card(Suit.SPADES, Rank.ACE)
    reason = bot.peek_last_decision_reason("play")
    assert isinstance(reason, SearchPlayDecisionReason)
    assert reason.baseline_comparison is not None
    assert reason.baseline_comparison.agrees_with_search is True
    assert reason.baseline_comparison.baseline.card == Card(Suit.SPADES, Rank.ACE)
    assert reason.baseline_comparison.baseline.selection_rank == 1
    assert reason.baseline_comparison.mean_projected_score_delta_advantage == 0.0
    assert reason.baseline_comparison.mean_root_utility_gain == 0.0
    assert reason.baseline_comparison.worlds_search_better == 0
    assert reason.baseline_comparison.worlds_tied == 1
    assert reason.baseline_comparison.worlds_baseline_better == 0
    assert reason.baseline_comparison.worst_case_root_utility_loss == 0.0
    assert reason.baseline_comparison.best_case_root_utility_gain == 0.0


def test_search_bot_v1_choose_play_is_deterministic_under_fixed_seed() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)

    first_bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=3))
    second_bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=3))

    first_card = first_bot.choose_play(state=deepcopy(state), rng=random.Random(211))
    second_card = second_bot.choose_play(state=deepcopy(state), rng=random.Random(211))

    assert first_card == second_card
    assert first_bot.peek_last_decision_reason("play") == second_bot.peek_last_decision_reason("play")


def test_search_bot_v1_choose_play_is_invariant_to_hidden_live_assignment() -> None:
    first_state = _full_state_with_rotating_hidden_hands(rotation=0)
    second_state = _full_state_with_rotating_hidden_hands(rotation=1)

    first_bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=3))
    second_bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=3))

    first_card = first_bot.choose_play(state=first_state, rng=random.Random(307))
    second_card = second_bot.choose_play(state=second_state, rng=random.Random(307))

    assert first_card == second_card
    assert first_bot.peek_last_decision_reason("play") == second_bot.peek_last_decision_reason("play")


def test_search_bot_v1_falls_back_to_heuristic_v3_on_impossible_world() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    impossible_card = state.hands[PlayerId(0)][0]

    search_bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=2))
    heuristic_bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0, rollout_weight=0.0)
    search_bot.on_new_hand(state)
    search_bot.on_own_pass_selected(
        state=state,
        selected_cards=(impossible_card,),
        recipient=PlayerId(1),
    )

    search_card = search_bot.choose_play(state=deepcopy(state), rng=random.Random(401))
    heuristic_card = heuristic_bot.choose_play(state=deepcopy(state), rng=random.Random(401))

    assert search_card == heuristic_card
    reason = search_bot.peek_last_decision_reason("play")
    assert isinstance(reason, SearchPlayDecisionReason)
    assert reason.selection_source == "heuristic_fallback_impossible_world"
    assert reason.legal_move_count == 1
    assert reason.evaluated_candidate_count == 0
    assert reason.current_trick_size == 0
    assert reason.led_suit is None
    assert reason.world_count == 0
    assert reason.requested_world_count == 2
    assert reason.chosen.card == search_card
    assert reason.chosen.average_projected_score_delta is None
    assert reason.chosen.average_projected_hand_points is None
    assert reason.chosen.average_projected_total_score is None
    assert reason.chosen.average_root_utility is None
    assert reason.baseline_comparison is None
    assert reason.candidates == ()
    assert "cannot still be in the root hand" in (reason.fallback_message or "")


def test_search_bot_v1_raises_on_impossible_world_when_fallback_disabled() -> None:
    state = _full_state_with_rotating_hidden_hands(rotation=0)
    impossible_card = state.hands[PlayerId(0)][0]

    bot = SearchBotV1(
        player_id=PlayerId(0),
        config=SearchBotConfig(
            world_count=2,
            fallback_to_heuristic_v3_on_impossible_world=False,
        ),
    )
    bot.on_new_hand(state)
    bot.on_own_pass_selected(
        state=state,
        selected_cards=(impossible_card,),
        recipient=PlayerId(1),
    )

    with pytest.raises(ImpossibleWorldError):
        bot.choose_play(state=deepcopy(state), rng=random.Random(409))


def test_search_bot_v1_falls_back_to_heuristic_v3_on_empty_world_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.FIVE), Card(Suit.SPADES, Rank.ACE)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.trick_in_progress = []
    state.hearts_broken = True
    state.turn = PlayerId(0)
    state.trick_number = 3
    state.pass_direction = "left"
    state.pass_applied = True

    monkeypatch.setattr(
        search_bot_module,
        "evaluate_root_candidates",
        lambda **kwargs: RootMoveEvaluationSet(
            root_player_id=kwargs["view"].player_id,
            base_seed=kwargs["seed"],
            world_set=DeterminizedWorldSet(
                root_player_id=kwargs["view"].player_id,
                base_seed=kwargs["seed"],
                worlds=(),
            ),
            candidate_evaluations=(),
        ),
    )

    search_bot = SearchBotV1(player_id=PlayerId(0), config=SearchBotConfig(world_count=4))
    heuristic_bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0, rollout_weight=0.0)

    search_card = search_bot.choose_play(state=deepcopy(state), rng=random.Random(419))
    heuristic_card = heuristic_bot.choose_play(state=deepcopy(state), rng=random.Random(419))

    assert search_card == heuristic_card
    reason = search_bot.peek_last_decision_reason("play")
    assert isinstance(reason, SearchPlayDecisionReason)
    assert reason.selection_source == "heuristic_fallback_empty_world_set"
    assert reason.legal_move_count == 2
    assert reason.evaluated_candidate_count == 0
    assert reason.current_trick_size == 0
    assert reason.led_suit is None
    assert reason.requested_world_count == 4
    assert reason.world_count == 0
    assert reason.chosen.card == search_card
    assert reason.chosen.average_projected_score_delta is None
    assert reason.baseline_comparison is None
    assert reason.candidates == ()


def test_search_bot_v1_raises_on_empty_world_set_when_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [Card(Suit.CLUBS, Rank.FIVE), Card(Suit.SPADES, Rank.ACE)],
        PlayerId(1): [Card(Suit.CLUBS, Rank.TWO)],
        PlayerId(2): [Card(Suit.CLUBS, Rank.THREE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.FOUR)],
    }
    state.trick_in_progress = []
    state.hearts_broken = True
    state.turn = PlayerId(0)
    state.trick_number = 3
    state.pass_direction = "left"
    state.pass_applied = True

    monkeypatch.setattr(
        search_bot_module,
        "evaluate_root_candidates",
        lambda **kwargs: RootMoveEvaluationSet(
            root_player_id=kwargs["view"].player_id,
            base_seed=kwargs["seed"],
            world_set=DeterminizedWorldSet(
                root_player_id=kwargs["view"].player_id,
                base_seed=kwargs["seed"],
                worlds=(),
            ),
            candidate_evaluations=(),
        ),
    )

    bot = SearchBotV1(
        player_id=PlayerId(0),
        config=SearchBotConfig(
            world_count=4,
            fallback_to_heuristic_v3_on_empty_world_set=False,
        ),
    )

    with pytest.raises(ValueError, match="no sampled worlds"):
        bot.choose_play(state=deepcopy(state), rng=random.Random(421))


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


def _rollout_summary(
    *,
    candidate,
    sample_index: int,
    score_delta: int,
    hand_points: int,
) -> SearchRolloutSummary:
    projected_scores = {player_id: 0 for player_id in PLAYER_IDS}
    projected_score_deltas = {player_id: 0 for player_id in PLAYER_IDS}
    projected_hand_points = {player_id: 0 for player_id in PLAYER_IDS}
    projected_scores[PlayerId(0)] = score_delta
    projected_score_deltas[PlayerId(0)] = score_delta
    projected_hand_points[PlayerId(0)] = hand_points
    return SearchRolloutSummary(
        world_sample_index=sample_index,
        world_sample_seed=100 + sample_index,
        root_player_id=PlayerId(0),
        candidate=candidate,
        projected_hand_points=projected_hand_points,
        projected_score_deltas=projected_score_deltas,
        projected_scores=projected_scores,
        root_utility=-float(score_delta),
    )
