from __future__ import annotations

from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PlayerId
from hearts_ai.search.models import SearchPlayerView, SeatPrivateKnowledge


def build_search_player_view(
    *,
    state: GameState,
    player_id: PlayerId,
    private_knowledge: SeatPrivateKnowledge | None = None,
) -> SearchPlayerView:
    """Build a hidden-information-safe search view for one acting seat.

    Phase 0 / Step 1 / Sub-step 1 defines this boundary API only. The actual
    projection from full-engine state to the search-side view is implemented in
    the next sub-step.
    """

    del state, player_id, private_knowledge
    raise NotImplementedError(
        "build_search_player_view() is defined but not implemented yet. "
        "Phase 0 / Step 1 / Sub-step 2 will add the concrete hidden-information-safe view."
    )


__all__ = ["build_search_player_view"]
