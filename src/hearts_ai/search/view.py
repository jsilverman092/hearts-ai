from __future__ import annotations

from types import MappingProxyType

from hearts_ai.engine.cards import Card, Rank, Suit, make_deck
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId, Trick
from hearts_ai.search.models import PublicKnowledge, SearchPlayerView, SeatPrivateKnowledge, VisibleTrick


def build_search_player_view(
    *,
    state: GameState,
    player_id: PlayerId,
    private_knowledge: SeatPrivateKnowledge | None = None,
) -> SearchPlayerView:
    """Build a hidden-information-safe search view for one acting seat.

    This projection intentionally exposes only:
    - the acting player's own hand
    - legal moves for that player
    - public trick / score / turn state
    - public card-knowledge derived from played tricks
    - optional seat-private knowledge supplied by the caller
    """

    private = private_knowledge or SeatPrivateKnowledge()
    return SearchPlayerView(
        player_id=player_id,
        hand=tuple(state.hands[player_id]),
        legal_moves=tuple(legal_moves(state=state, player_id=player_id)),
        current_trick=_freeze_trick(state.trick_in_progress),
        taken_tricks=MappingProxyType(
            {
                pid: tuple(_freeze_trick(trick) for trick in state.taken_tricks[pid])
                for pid in PLAYER_IDS
            }
        ),
        scores=MappingProxyType({pid: state.scores[pid] for pid in PLAYER_IDS}),
        hearts_broken=state.hearts_broken,
        turn=state.turn,
        trick_number=state.trick_number,
        hand_number=state.hand_number,
        pass_direction=state.pass_direction,
        pass_applied=state.pass_applied,
        target_score=state.config.target_score,
        public_knowledge=_build_public_knowledge(state=state),
        private_knowledge=private,
    )


def _build_public_knowledge(*, state: GameState) -> PublicKnowledge:
    seen_cards = frozenset(
        card
        for trick in _all_public_tricks(state)
        for _, card in trick
    )
    unplayed_cards = frozenset(card for card in make_deck() if card not in seen_cards)
    played_count_by_suit = MappingProxyType(
        {suit: sum(1 for card in seen_cards if card.suit == suit) for suit in Suit}
    )
    unplayed_count_by_suit = MappingProxyType(
        {suit: sum(1 for card in unplayed_cards if card.suit == suit) for suit in Suit}
    )
    remaining_cards_by_player = MappingProxyType(
        {pid: len(state.hands[pid]) for pid in PLAYER_IDS}
    )
    void_suits_by_player = MappingProxyType(
        _infer_void_suits_by_player(state=state)
    )

    return PublicKnowledge(
        seen_cards=seen_cards,
        unplayed_cards=unplayed_cards,
        qs_live=Card(Suit.SPADES, Rank.QUEEN) not in seen_cards,
        played_count_by_suit=played_count_by_suit,
        unplayed_count_by_suit=unplayed_count_by_suit,
        remaining_cards_by_player=remaining_cards_by_player,
        void_suits_by_player=void_suits_by_player,
    )


def _all_public_tricks(state: GameState) -> tuple[Trick, ...]:
    taken = tuple(
        trick
        for pid in PLAYER_IDS
        for trick in state.taken_tricks[pid]
    )
    if not state.trick_in_progress:
        return taken
    return (*taken, state.trick_in_progress)


def _infer_void_suits_by_player(*, state: GameState) -> dict[PlayerId, frozenset[Suit]]:
    inferred: dict[PlayerId, set[Suit]] = {pid: set() for pid in PLAYER_IDS}
    for trick in _all_public_tricks(state):
        if len(trick) < 2:
            continue
        led_suit = trick[0][1].suit
        for pid, card in trick[1:]:
            if card.suit != led_suit:
                inferred[pid].add(led_suit)
    return {pid: frozenset(suits) for pid, suits in inferred.items()}


def _freeze_trick(trick: Trick) -> VisibleTrick:
    return tuple((pid, card) for pid, card in trick)


__all__ = ["build_search_player_view"]
