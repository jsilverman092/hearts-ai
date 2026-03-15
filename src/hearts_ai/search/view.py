from __future__ import annotations

from types import MappingProxyType

from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId, Trick
from hearts_ai.search.knowledge import build_public_knowledge
from hearts_ai.search.models import SearchPlayerView, SeatPrivateKnowledge, VisibleTrick


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
        public_knowledge=build_public_knowledge(state=state),
        private_knowledge=private,
    )


def _freeze_trick(trick: Trick) -> VisibleTrick:
    return tuple((pid, card) for pid, card in trick)


__all__ = ["build_search_player_view"]
