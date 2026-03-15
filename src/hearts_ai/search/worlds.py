from __future__ import annotations

import random
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias

from hearts_ai.engine.cards import Card, Suit
from hearts_ai.engine.state import GameState
from hearts_ai.engine.types import PLAYER_IDS, PlayerId, Trick
from hearts_ai.search.models import SearchPlayerView

SampledHiddenHands: TypeAlias = Mapping[PlayerId, tuple[Card, ...]]

_MAX_SAMPLE_SEED = 2**63 - 1


class ImpossibleWorldError(ValueError):
    """Raised when search constraints do not admit any legal hidden world."""


@dataclass(slots=True, frozen=True)
class DeterminizedWorld:
    """One sampled hidden-information completion for a root search seat."""

    root_player_id: PlayerId
    sample_index: int
    sample_seed: int
    hidden_hands: SampledHiddenHands
    state: GameState


@dataclass(slots=True, frozen=True)
class DeterminizedWorldSet:
    """Ordered sampled worlds intended for reuse across root move evaluation."""

    root_player_id: PlayerId
    base_seed: int
    worlds: tuple[DeterminizedWorld, ...]


def sample_determinized_world(
    *,
    view: SearchPlayerView,
    seed: int,
    sample_index: int = 0,
) -> DeterminizedWorld:
    """Sample one hidden world from a search-safe player view."""

    rng = random.Random(seed)
    hidden_hands = _sample_hidden_hands(view=view, rng=rng)
    return DeterminizedWorld(
        root_player_id=view.player_id,
        sample_index=sample_index,
        sample_seed=seed,
        hidden_hands=hidden_hands,
        state=_build_determinized_state(view=view, hidden_hands=hidden_hands),
    )


def sample_determinized_worlds(
    *,
    view: SearchPlayerView,
    seed: int,
    world_count: int,
) -> DeterminizedWorldSet:
    """Build a deterministic ordered world set for common-random-number reuse."""

    if world_count < 0:
        raise ValueError(f"world_count must be >= 0, got {world_count}.")

    base_rng = random.Random(seed)
    worlds = tuple(
        sample_determinized_world(
            view=view,
            seed=base_rng.randrange(_MAX_SAMPLE_SEED + 1),
            sample_index=index,
        )
        for index in range(world_count)
    )
    return DeterminizedWorldSet(
        root_player_id=view.player_id,
        base_seed=seed,
        worlds=worlds,
    )


def _sample_hidden_hands(
    *,
    view: SearchPlayerView,
    rng: random.Random,
) -> SampledHiddenHands:
    own_hand = tuple(sorted(view.hand))
    own_hand_set = frozenset(own_hand)
    public = view.public_knowledge

    expected_own_count = public.remaining_cards_by_player.get(view.player_id, 0)
    if expected_own_count != len(own_hand):
        raise ImpossibleWorldError(
            "Search view own-hand size does not match public remaining-card count."
        )
    if any(card not in public.unplayed_cards for card in own_hand):
        raise ImpossibleWorldError("Search view hand must be a subset of public unplayed cards.")

    hidden_players = tuple(player_id for player_id in PLAYER_IDS if player_id != view.player_id)
    forced_cards_by_player: dict[PlayerId, list[Card]] = {player_id: [] for player_id in hidden_players}
    forced_unplayed_cards: set[Card] = set()

    for recipient, cards in sorted(
        view.private_knowledge.passed_cards_by_recipient.items(),
        key=lambda item: int(item[0]),
    ):
        if recipient == view.player_id:
            if any(card in public.unplayed_cards for card in cards):
                raise ImpossibleWorldError("Root player cannot still own a card marked as passed away.")
            continue
        if recipient not in hidden_players:
            if any(card in public.unplayed_cards for card in cards):
                raise ImpossibleWorldError(f"Unknown pass recipient for unplayed card: {recipient!r}.")
            continue
        for card in cards:
            if card in public.seen_cards:
                continue
            if card not in public.unplayed_cards:
                raise ImpossibleWorldError(f"Passed card {card} is neither seen nor unplayed.")
            if card in own_hand_set:
                raise ImpossibleWorldError(f"Passed card {card} cannot still be in the root hand.")
            if card in forced_unplayed_cards:
                raise ImpossibleWorldError(f"Passed card {card} was assigned to multiple recipients.")
            if public.player_is_void(player_id=recipient, suit=card.suit):
                raise ImpossibleWorldError(
                    f"Recipient player {int(recipient)} is publicly void in {card.suit.name}."
                )
            forced_cards_by_player[recipient].append(card)
            forced_unplayed_cards.add(card)

    remaining_pool = tuple(sorted(card for card in public.unplayed_cards if card not in own_hand_set and card not in forced_unplayed_cards))
    remaining_capacity_by_player = {
        player_id: public.remaining_cards_by_player.get(player_id, 0) - len(forced_cards_by_player[player_id])
        for player_id in hidden_players
    }
    for player_id, capacity in remaining_capacity_by_player.items():
        if capacity < 0:
            raise ImpossibleWorldError(
                f"Player {int(player_id)} was forced to hold more cards than their remaining hand size."
            )
    if sum(remaining_capacity_by_player.values()) != len(remaining_pool):
        raise ImpossibleWorldError("Public remaining-card counts do not match the unallocated hidden pool.")

    remaining_cards_by_suit = {
        suit: tuple(card for card in remaining_pool if card.suit == suit)
        for suit in Suit
    }
    suit_allocations = _sample_suit_allocations(
        view=view,
        hidden_players=hidden_players,
        remaining_capacity_by_player=remaining_capacity_by_player,
        remaining_cards_by_suit=remaining_cards_by_suit,
        rng=rng,
    )

    sampled_hands: dict[PlayerId, tuple[Card, ...]] = {}
    for player_id in hidden_players:
        cards = list(forced_cards_by_player[player_id])
        sampled_hands[player_id] = tuple(sorted(cards))

    for suit in Suit:
        suit_cards = list(remaining_cards_by_suit[suit])
        rng.shuffle(suit_cards)
        cursor = 0
        for player_id in hidden_players:
            count = suit_allocations[suit].get(player_id, 0)
            if count <= 0:
                continue
            current_cards = list(sampled_hands[player_id])
            current_cards.extend(suit_cards[cursor : cursor + count])
            sampled_hands[player_id] = tuple(sorted(current_cards))
            cursor += count
        if cursor != len(suit_cards):
            raise ImpossibleWorldError(f"Failed to allocate all remaining {suit.name} cards.")

    return MappingProxyType(sampled_hands)


def _sample_suit_allocations(
    *,
    view: SearchPlayerView,
    hidden_players: tuple[PlayerId, ...],
    remaining_capacity_by_player: Mapping[PlayerId, int],
    remaining_cards_by_suit: Mapping[Suit, tuple[Card, ...]],
    rng: random.Random,
) -> dict[Suit, dict[PlayerId, int]]:
    capacities = dict(remaining_capacity_by_player)
    allocations: dict[Suit, dict[PlayerId, int]] = {}
    ordered_suits = tuple(
        sorted(
            Suit,
            key=lambda suit: (
                len(_allowed_players_for_suit(view=view, hidden_players=hidden_players, suit=suit)),
                -len(remaining_cards_by_suit[suit]),
                int(suit),
            ),
        )
    )

    def backtrack(index: int) -> bool:
        if index >= len(ordered_suits):
            return all(capacity == 0 for capacity in capacities.values())

        suit = ordered_suits[index]
        suit_cards = remaining_cards_by_suit[suit]
        allowed_players = _allowed_players_for_suit(
            view=view,
            hidden_players=hidden_players,
            suit=suit,
        )
        distributions = _feasible_distributions(
            total=len(suit_cards),
            players=allowed_players,
            capacities=capacities,
        )
        if not distributions:
            return False
        rng.shuffle(distributions)

        for distribution in distributions:
            for player_id, count in distribution.items():
                capacities[player_id] -= count
            if _remaining_suits_still_feasible(
                view=view,
                hidden_players=hidden_players,
                ordered_suits=ordered_suits,
                start_index=index + 1,
                remaining_capacity_by_player=capacities,
                remaining_cards_by_suit=remaining_cards_by_suit,
            ):
                allocations[suit] = distribution
                if backtrack(index + 1):
                    return True
                allocations.pop(suit, None)
            for player_id, count in distribution.items():
                capacities[player_id] += count
        return False

    if not backtrack(0):
        raise ImpossibleWorldError("No hidden-hand assignment satisfies the public and private constraints.")
    return allocations


def _allowed_players_for_suit(
    *,
    view: SearchPlayerView,
    hidden_players: tuple[PlayerId, ...],
    suit: Suit,
) -> tuple[PlayerId, ...]:
    return tuple(
        player_id
        for player_id in hidden_players
        if not view.public_knowledge.player_is_void(player_id=player_id, suit=suit)
    )


def _feasible_distributions(
    *,
    total: int,
    players: tuple[PlayerId, ...],
    capacities: Mapping[PlayerId, int],
) -> list[dict[PlayerId, int]]:
    if total == 0:
        return [{player_id: 0 for player_id in players}]
    if not players:
        return []

    distributions: list[dict[PlayerId, int]] = []

    def build(index: int, remaining: int, partial: dict[PlayerId, int]) -> None:
        if index == len(players):
            if remaining == 0:
                distributions.append(dict(partial))
            return

        player_id = players[index]
        remaining_capacity_after = sum(capacities[other] for other in players[index + 1 :])
        min_count = max(0, remaining - remaining_capacity_after)
        max_count = min(capacities[player_id], remaining)
        for count in range(min_count, max_count + 1):
            partial[player_id] = count
            build(index + 1, remaining - count, partial)
        partial.pop(player_id, None)

    build(0, total, {})
    return distributions


def _remaining_suits_still_feasible(
    *,
    view: SearchPlayerView,
    hidden_players: tuple[PlayerId, ...],
    ordered_suits: tuple[Suit, ...],
    start_index: int,
    remaining_capacity_by_player: Mapping[PlayerId, int],
    remaining_cards_by_suit: Mapping[Suit, tuple[Card, ...]],
) -> bool:
    if any(capacity < 0 for capacity in remaining_capacity_by_player.values()):
        return False

    remaining_suits = ordered_suits[start_index:]
    remaining_total = sum(len(remaining_cards_by_suit[suit]) for suit in remaining_suits)
    if remaining_total != sum(remaining_capacity_by_player.values()):
        return False

    for player_id in hidden_players:
        max_available = sum(
            len(remaining_cards_by_suit[suit])
            for suit in remaining_suits
            if not view.public_knowledge.player_is_void(player_id=player_id, suit=suit)
        )
        if remaining_capacity_by_player[player_id] > max_available:
            return False

    return True


def _build_determinized_state(
    *,
    view: SearchPlayerView,
    hidden_hands: SampledHiddenHands,
) -> GameState:
    state = GameState(config=deepcopy(view.config))
    state.hands = {
        player_id: _build_hand_for_player(
            player_id=player_id,
            view=view,
            hidden_hands=hidden_hands,
        )
        for player_id in PLAYER_IDS
    }
    state.trick_in_progress = _thaw_trick(view.current_trick)
    state.taken_tricks = {
        player_id: [_thaw_trick(trick) for trick in view.taken_tricks[player_id]]
        for player_id in PLAYER_IDS
    }
    state.scores = {player_id: view.scores[player_id] for player_id in PLAYER_IDS}
    state.hearts_broken = view.hearts_broken
    state.turn = view.turn
    state.trick_number = view.trick_number
    state.hand_number = view.hand_number
    state.pass_direction = view.pass_direction
    state.pass_applied = view.pass_applied
    state.hand_scored = False
    return state


def _build_hand_for_player(
    *,
    player_id: PlayerId,
    view: SearchPlayerView,
    hidden_hands: SampledHiddenHands,
) -> list[Card]:
    if player_id == view.player_id:
        return list(sorted(view.hand))
    return list(hidden_hands.get(player_id, ()))


def _thaw_trick(trick: Trick | tuple[tuple[PlayerId, Card], ...]) -> Trick:
    return [(player_id, card) for player_id, card in trick]


__all__ = [
    "DeterminizedWorld",
    "DeterminizedWorldSet",
    "ImpossibleWorldError",
    "SampledHiddenHands",
    "sample_determinized_world",
    "sample_determinized_worlds",
]
