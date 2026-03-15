import random

import pytest

import hearts_ai.bots.search.bots as search_bot_module
from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.bots.search import SearchBotConfig, SearchBotV1
from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import RootCandidateEvaluation, RootMoveEvaluationSet, build_root_move_candidates
from hearts_ai.search.worlds import DeterminizedWorldSet


def test_search_bot_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        SearchBotConfig(world_count=0)

    with pytest.raises(ValueError):
        SearchBotConfig(playout_seed_offset=-1)


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
        return RootMoveEvaluationSet(
            root_player_id=view.player_id,
            base_seed=seed,
            world_set=DeterminizedWorldSet(
                root_player_id=view.player_id,
                base_seed=seed,
                worlds=(),
            ),
            candidate_evaluations=(
                RootCandidateEvaluation(
                    candidate=candidates[0],
                    rollout_summaries=(),
                    average_projected_hand_points=7.0,
                    average_projected_score_delta=7.0,
                    average_projected_total_score=7.0,
                    average_root_utility=-7.0,
                ),
                RootCandidateEvaluation(
                    candidate=candidates[1],
                    rollout_summaries=(),
                    average_projected_hand_points=2.0,
                    average_projected_score_delta=2.0,
                    average_projected_total_score=2.0,
                    average_root_utility=-2.0,
                ),
            ),
        )

    monkeypatch.setattr(search_bot_module, "evaluate_root_candidates", fake_evaluate_root_candidates)

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
