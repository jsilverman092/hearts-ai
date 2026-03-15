from __future__ import annotations

import random

from hearts_ai.bots.heuristic import HeuristicBotV3
from hearts_ai.bots.search import SearchBotConfig, SearchBotV1, SearchPlayDecisionReason
from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId

_SCENARIO_WORLD_COUNT = 16
_DECISION_SEED = 12345

_RANK_BY_CODE = {
    "2": Rank.TWO,
    "3": Rank.THREE,
    "4": Rank.FOUR,
    "5": Rank.FIVE,
    "6": Rank.SIX,
    "7": Rank.SEVEN,
    "8": Rank.EIGHT,
    "9": Rank.NINE,
    "10": Rank.TEN,
    "J": Rank.JACK,
    "Q": Rank.QUEEN,
    "K": Rank.KING,
    "A": Rank.ACE,
}
_SUIT_BY_CODE = {
    "C": Suit.CLUBS,
    "D": Suit.DIAMONDS,
    "H": Suit.HEARTS,
    "S": Suit.SPADES,
}


def test_search_scenario_agrees_with_heuristic_on_late_safe_spade_lead() -> None:
    state = _make_state(
        hands={
            PlayerId(0): ["6C", "8C", "JH", "6S"],
            PlayerId(1): ["7C", "2S", "9S", "KS"],
            PlayerId(2): ["4D", "7D", "3H", "7S"],
            PlayerId(3): ["3C", "5C", "7H", "QH"],
        },
        hearts_broken=True,
        turn=PlayerId(0),
        trick_number=9,
        taken_tricks={
            PlayerId(0): [
                [(PlayerId(2), "8S"), (PlayerId(3), "JS"), (PlayerId(0), "AS"), (PlayerId(1), "3S")],
                [(PlayerId(0), "KC"), (PlayerId(1), "JC"), (PlayerId(2), "QC"), (PlayerId(3), "10C")],
                [(PlayerId(1), "10S"), (PlayerId(2), "5S"), (PlayerId(3), "4S"), (PlayerId(0), "QS")],
                [(PlayerId(2), "9H"), (PlayerId(3), "6H"), (PlayerId(0), "KH"), (PlayerId(1), "2H")],
            ],
            PlayerId(1): [
                [(PlayerId(0), "JD"), (PlayerId(1), "AD"), (PlayerId(2), "3D"), (PlayerId(3), "5D")],
                [(PlayerId(3), "2D"), (PlayerId(0), "AH"), (PlayerId(1), "QD"), (PlayerId(2), "6D")],
            ],
            PlayerId(2): [
                [(PlayerId(3), "2C"), (PlayerId(0), "9C"), (PlayerId(1), "4C"), (PlayerId(2), "AC")],
                [(PlayerId(0), "5H"), (PlayerId(1), "8H"), (PlayerId(2), "10H"), (PlayerId(3), "4H")],
            ],
            PlayerId(3): [
                [(PlayerId(1), "10D"), (PlayerId(2), "9D"), (PlayerId(3), "KD"), (PlayerId(0), "8D")],
            ],
        },
    )

    heuristic_card = _heuristic_choice(state)
    search_card, search_reason = _search_choice(state)

    assert heuristic_card == _card("6S")
    assert search_card == _card("6S")
    assert search_reason.baseline_comparison is not None
    assert search_reason.baseline_comparison.agrees_with_search is True


def test_search_scenario_avoids_early_qs_lead_at_higher_world_count() -> None:
    # Frozen from deterministic replay (seed=1, steps=12) after the tie-order fix.
    state = _make_state(
        hands={
            PlayerId(0): ["6C", "8C", "8D", "JD", "5H", "JH", "KH", "AH", "6S", "QS"],
            PlayerId(1): ["7C", "10D", "QD", "AD", "2H", "8H", "2S", "9S", "10S", "KS"],
            PlayerId(2): ["3D", "4D", "6D", "7D", "9D", "3H", "9H", "10H", "5S", "7S"],
            PlayerId(3): ["3C", "5C", "2D", "5D", "KD", "4H", "6H", "7H", "QH", "4S"],
        },
        hearts_broken=False,
        turn=PlayerId(0),
        trick_number=3,
        taken_tricks={
            PlayerId(0): [
                [(PlayerId(2), "8S"), (PlayerId(3), "JS"), (PlayerId(0), "AS"), (PlayerId(1), "3S")],
                [(PlayerId(0), "KC"), (PlayerId(1), "JC"), (PlayerId(2), "QC"), (PlayerId(3), "10C")],
            ],
            PlayerId(1): [],
            PlayerId(2): [
                [(PlayerId(3), "2C"), (PlayerId(0), "9C"), (PlayerId(1), "4C"), (PlayerId(2), "AC")],
            ],
            PlayerId(3): [],
        },
    )

    heuristic_card = _heuristic_choice(state)
    search_card, search_reason = _search_choice(state)

    assert heuristic_card == _card("8D")
    assert search_card == _card("6S")
    assert search_card != _card("QS")
    assert search_reason.baseline_comparison is not None
    assert search_reason.baseline_comparison.agrees_with_search is False


def test_search_scenario_avoids_early_ks_lead_at_higher_world_count() -> None:
    # Frozen from deterministic replay (seed=206, steps=12).
    state = _make_state(
        hands={
            PlayerId(0): ["10C", "JD", "KD", "2H", "6H", "JH", "QH", "KH", "3S", "KS"],
            PlayerId(1): ["JC", "QC", "7D", "9D", "5H", "AH", "4S", "6S", "8S", "AS"],
            PlayerId(2): ["4C", "3H", "4H", "7H", "8H", "10H", "2S", "5S", "7S", "QS"],
            PlayerId(3): ["AC", "2D", "3D", "4D", "5D", "10D", "9H", "9S", "10S", "JS"],
        },
        hearts_broken=False,
        turn=PlayerId(0),
        trick_number=3,
        taken_tricks={
            PlayerId(0): [
                [(PlayerId(3), "8D"), (PlayerId(0), "AD"), (PlayerId(1), "QD"), (PlayerId(2), "6D")],
            ],
            PlayerId(1): [],
            PlayerId(2): [
                [(PlayerId(0), "2C"), (PlayerId(1), "6C"), (PlayerId(2), "9C"), (PlayerId(3), "5C")],
            ],
            PlayerId(3): [
                [(PlayerId(2), "8C"), (PlayerId(3), "KC"), (PlayerId(0), "7C"), (PlayerId(1), "3C")],
            ],
        },
    )

    heuristic_card = _heuristic_choice(state)
    search_card, _search_reason = _search_choice(state)

    assert heuristic_card == _card("10C")
    assert search_card != _card("KS")


def test_search_scenario_late_hand_counting_prefers_lower_following_diamond() -> None:
    # Frozen from deterministic replay (seed=2, steps=37).
    state = _make_state(
        hands={
            PlayerId(0): ["4C", "7C", "JD", "KD"],
            PlayerId(1): ["8C", "3S", "7S", "8S"],
            PlayerId(2): ["3D", "4H", "8H", "9H"],
            PlayerId(3): ["3C", "QC", "QD"],
        },
        hearts_broken=True,
        turn=PlayerId(0),
        trick_number=9,
        trick_in_progress=[(PlayerId(3), "2D")],
        taken_tricks={
            PlayerId(0): [
                [(PlayerId(2), "10S"), (PlayerId(3), "KS"), (PlayerId(0), "AS"), (PlayerId(1), "QS")],
                [(PlayerId(0), "10D"), (PlayerId(1), "7D"), (PlayerId(2), "6D"), (PlayerId(3), "8D")],
            ],
            PlayerId(1): [],
            PlayerId(2): [
                [(PlayerId(3), "2C"), (PlayerId(0), "JC"), (PlayerId(1), "6C"), (PlayerId(2), "AC")],
                [(PlayerId(0), "4D"), (PlayerId(1), "9D"), (PlayerId(2), "AD"), (PlayerId(3), "5D")],
                [(PlayerId(3), "5S"), (PlayerId(0), "2H"), (PlayerId(1), "9S"), (PlayerId(2), "JS")],
            ],
            PlayerId(3): [
                [(PlayerId(2), "2S"), (PlayerId(3), "6S"), (PlayerId(0), "10H"), (PlayerId(1), "4S")],
                [(PlayerId(3), "KH"), (PlayerId(0), "QH"), (PlayerId(1), "6H"), (PlayerId(2), "JH")],
                [(PlayerId(3), "KC"), (PlayerId(0), "5C"), (PlayerId(1), "10C"), (PlayerId(2), "9C")],
                [(PlayerId(2), "3H"), (PlayerId(3), "AH"), (PlayerId(0), "5H"), (PlayerId(1), "7H")],
            ],
        },
    )

    heuristic_card = _heuristic_choice(state)
    search_card, _search_reason = _search_choice(state)

    assert heuristic_card == _card("KD")
    assert search_card == _card("JD")


def _search_choice(state: GameState) -> tuple[Card, SearchPlayDecisionReason]:
    bot = SearchBotV1(
        player_id=PlayerId(0),
        config=SearchBotConfig(world_count=_SCENARIO_WORLD_COUNT),
    )
    chosen = bot.choose_play(state=state, rng=random.Random(_DECISION_SEED))
    reason = bot.peek_last_decision_reason("play")
    if not isinstance(reason, SearchPlayDecisionReason):
        raise AssertionError("search_v1 did not expose a structured play reason.")
    return chosen, reason


def _heuristic_choice(state: GameState) -> Card:
    bot = HeuristicBotV3(player_id=PlayerId(0), rollout_samples=0, rollout_weight=0.0)
    return bot.choose_play(state=state, rng=random.Random(_DECISION_SEED))


def _make_state(
    *,
    hands: dict[PlayerId, list[str]],
    turn: PlayerId,
    trick_number: int,
    hearts_broken: bool,
    trick_in_progress: list[tuple[PlayerId, str]] | None = None,
    taken_tricks: dict[PlayerId, list[list[tuple[PlayerId, str]]]] | None = None,
) -> GameState:
    state = GameState()
    state.hands = {
        player_id: sorted(_card(code) for code in hands[player_id])
        for player_id in PLAYER_IDS
    }
    state.taken_tricks = {
        player_id: [
            [(_pid, _card(card_code)) for _pid, card_code in trick]
            for trick in (taken_tricks or {}).get(player_id, [])
        ]
        for player_id in PLAYER_IDS
    }
    state.scores = {player_id: 0 for player_id in PLAYER_IDS}
    state.hearts_broken = hearts_broken
    state.turn = turn
    state.trick_number = trick_number
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = True
    state.trick_in_progress = [
        (player_id, _card(card_code))
        for player_id, card_code in (trick_in_progress or [])
    ]
    return state


def _card(code: str) -> Card:
    rank_code = code[:-1]
    suit_code = code[-1]
    return Card(_SUIT_BY_CODE[suit_code], _RANK_BY_CODE[rank_code])
