from hearts_ai.engine.cards import Card, Rank, Suit
from hearts_ai.engine.types import PLAYER_IDS, PlayerId
from hearts_ai.search import PublicKnowledge, SearchPlayerView, SeatPrivateKnowledge, build_search_player_view


def test_search_player_view_models_are_instantiable() -> None:
    knowledge = PublicKnowledge(
        seen_cards=frozenset({Card(Suit.CLUBS, Rank.TWO)}),
        unplayed_cards=frozenset({Card(Suit.CLUBS, Rank.THREE)}),
        qs_live=True,
        played_count_by_suit={suit: 0 for suit in Suit},
        unplayed_count_by_suit={suit: 13 for suit in Suit},
        remaining_cards_by_player={player_id: 13 for player_id in PLAYER_IDS},
        void_suits_by_player={player_id: frozenset() for player_id in PLAYER_IDS},
    )
    private = SeatPrivateKnowledge(
        passed_cards_by_recipient={PlayerId(1): (Card(Suit.SPADES, Rank.QUEEN),)}
    )
    view = SearchPlayerView(
        player_id=PlayerId(0),
        hand=(Card(Suit.CLUBS, Rank.FOUR),),
        legal_moves=(Card(Suit.CLUBS, Rank.FOUR),),
        current_trick=((PlayerId(1), Card(Suit.CLUBS, Rank.TWO)),),
        taken_tricks={player_id: () for player_id in PLAYER_IDS},
        scores={player_id: 0 for player_id in PLAYER_IDS},
        hearts_broken=False,
        turn=PlayerId(0),
        trick_number=0,
        hand_number=1,
        pass_direction="left",
        pass_applied=True,
        target_score=50,
        public_knowledge=knowledge,
        private_knowledge=private,
    )

    assert view.player_id == PlayerId(0)
    assert view.public_knowledge is knowledge
    assert view.private_knowledge is private
    assert view.current_trick[0][0] == PlayerId(1)


def test_search_view_builder_api_is_exposed() -> None:
    assert callable(build_search_player_view)
