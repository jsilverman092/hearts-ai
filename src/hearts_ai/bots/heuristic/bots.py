from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from hearts_ai.bots.heuristic.models import (
    PassCandidateReason,
    PassDecisionReason,
    PlayDecisionReason,
)
from hearts_ai.bots.heuristic.scoring import (
    _choose_follow_or_discard,
    _choose_lead,
    _score_discard_base,
    _score_discard_v3,
    _score_follow_base,
    _score_follow_v3,
    _score_lead_base,
    _score_lead_v3,
    _score_pass_base,
    _score_pass_v3,
)
from hearts_ai.bots.heuristic.shared import _choose_play_with_reason
from hearts_ai.engine.cards import Card
from hearts_ai.engine.errors import InvalidStateError
from hearts_ai.engine.rules import legal_moves
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import Hand, PlayerId


@dataclass(slots=True, frozen=True)
class HeuristicBot:
    player_id: PlayerId

    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        del rng
        pass_count = state.config.pass_count
        if state.pass_direction == "hold" or pass_count == 0:
            return []
        if pass_count > len(hand):
            raise InvalidStateError(
                f"Cannot pass {pass_count} cards from hand of size {len(hand)} for player {int(self.player_id)}."
            )

        by_risk = sorted(hand, key=_score_pass_base, reverse=True)
        return sorted(by_risk[:pass_count])

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        del rng
        moves = legal_moves(state=state, player_id=self.player_id)
        if not moves:
            raise InvalidStateError(f"No legal moves available for player {int(self.player_id)}.")

        if not state.trick_in_progress:
            return _choose_lead(moves)
        return _choose_follow_or_discard(
            trick=state.trick_in_progress,
            legal=moves,
            first_trick=state.trick_number == 0,
        )


@dataclass(slots=True)
class _HeuristicScoringBotBase:
    player_id: PlayerId
    rollout_samples: int = 12
    rollout_weight: float = 0.35
    moon_defense_threshold: int = 12
    _last_pass_reason: PassDecisionReason | None = field(init=False, default=None, repr=False)
    _last_play_reason: PlayDecisionReason | None = field(init=False, default=None, repr=False)

    def choose_play(self, state: GameState, rng: random.Random) -> Card:
        chosen_card, play_reason = _choose_play_with_reason(
            state=state,
            player_id=self.player_id,
            rollout_samples=self.rollout_samples,
            rollout_weight=self.rollout_weight,
            moon_defense_threshold=self.moon_defense_threshold,
            score_play_candidate=self._score_play_candidate,
            rng=rng,
        )
        self._last_play_reason = play_reason
        return chosen_card

    # Internal hooks for future debug UI integration.
    def _peek_last_pass_reason(self) -> PassDecisionReason | None:
        return self._last_pass_reason

    def _peek_last_play_reason(self) -> PlayDecisionReason | None:
        return self._last_play_reason

    def _score_lead_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        legal: list[Card],
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        del state, player_id, legal, card, moon_target
        raise NotImplementedError

    def _score_play_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        legal: list[Card],
        card: Card,
        mode: Literal["lead", "follow", "discard"],
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        if mode == "lead":
            return self._score_lead_candidate(
                state=state,
                player_id=player_id,
                legal=legal,
                card=card,
                moon_target=moon_target,
            )
        if mode == "follow":
            return self._score_follow_candidate(
                state=state,
                player_id=player_id,
                card=card,
                moon_target=moon_target,
            )
        return self._score_discard_candidate(
            state=state,
            player_id=player_id,
            card=card,
            moon_target=moon_target,
        )

    def _score_follow_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        return _score_follow_base(
            state=state,
            player_id=player_id,
            card=card,
            moon_target=moon_target,
        )

    def _score_discard_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        del state, player_id, card, moon_target
        raise NotImplementedError


@dataclass(slots=True)
class HeuristicBotV2(_HeuristicScoringBotBase):
    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        del rng
        pass_count = state.config.pass_count
        if state.pass_direction == "hold" or pass_count == 0:
            self._last_pass_reason = PassDecisionReason(selected_cards=(), candidates=())
            return []
        if pass_count > len(hand):
            raise InvalidStateError(
                f"Cannot pass {pass_count} cards from hand of size {len(hand)} for player {int(self.player_id)}."
            )

        ranked = sorted(hand, key=_score_pass_base, reverse=True)
        selected = tuple(sorted(ranked[:pass_count]))
        self._last_pass_reason = PassDecisionReason(
            selected_cards=selected,
            candidates=tuple(PassCandidateReason(card=card, score=_score_pass_base(card)) for card in ranked),
        )
        return list(selected)

    def _score_lead_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        legal: list[Card],
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        del player_id, moon_target
        return _score_lead_base(
            state=state,
            legal=legal,
            card=card,
        )

    def _score_discard_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        del player_id
        return _score_discard_base(
            state=state,
            card=card,
            moon_target=moon_target,
        )


@dataclass(slots=True)
class HeuristicBotV3(_HeuristicScoringBotBase):
    def choose_pass(self, hand: Hand, state: GameState, rng: random.Random) -> list[Card]:
        del rng
        pass_count = state.config.pass_count
        if state.pass_direction == "hold" or pass_count == 0:
            self._last_pass_reason = PassDecisionReason(selected_cards=(), candidates=())
            return []
        if pass_count > len(hand):
            raise InvalidStateError(
                f"Cannot pass {pass_count} cards from hand of size {len(hand)} for player {int(self.player_id)}."
            )

        ranked = sorted(hand, key=lambda card: _score_pass_v3(card=card, hand=hand), reverse=True)
        selected = tuple(sorted(ranked[:pass_count]))
        self._last_pass_reason = PassDecisionReason(
            selected_cards=selected,
            candidates=tuple(
                PassCandidateReason(card=card, score=_score_pass_v3(card=card, hand=hand))
                for card in ranked
            ),
        )
        return list(selected)

    def _score_lead_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        legal: list[Card],
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        return _score_lead_v3(
            state=state,
            player_id=player_id,
            legal=legal,
            hand=state.hands[player_id],
            card=card,
            moon_target=moon_target,
        )

    def _score_follow_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        return _score_follow_v3(
            state=state,
            player_id=player_id,
            card=card,
            moon_target=moon_target,
        )

    def _score_discard_candidate(
        self,
        state: GameState,
        player_id: PlayerId,
        card: Card,
        moon_target: PlayerId | None,
    ) -> tuple[float, list[str]]:
        return _score_discard_v3(
            state=state,
            player_id=player_id,
            card=card,
            moon_target=moon_target,
        )
