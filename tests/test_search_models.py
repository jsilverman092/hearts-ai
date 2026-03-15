from hearts_ai.engine.state import GameState
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


def test_build_search_player_view_projects_only_acting_hand_and_public_state() -> None:
    state = GameState()
    state.hands = {
        PlayerId(0): [
            Card(Suit.CLUBS, Rank.THREE),
            Card(Suit.HEARTS, Rank.NINE),
        ],
        PlayerId(1): [Card(Suit.DIAMONDS, Rank.FOUR)],
        PlayerId(2): [Card(Suit.SPADES, Rank.FIVE)],
        PlayerId(3): [Card(Suit.CLUBS, Rank.SIX)],
    }
    state.taken_tricks = {
        PlayerId(0): [],
        PlayerId(1): [],
        PlayerId(2): [
            [
                (PlayerId(0), Card(Suit.DIAMONDS, Rank.TWO)),
                (PlayerId(1), Card(Suit.DIAMONDS, Rank.FIVE)),
                (PlayerId(2), Card(Suit.HEARTS, Rank.THREE)),
                (PlayerId(3), Card(Suit.DIAMONDS, Rank.SEVEN)),
            ],
            [
                (PlayerId(1), Card(Suit.SPADES, Rank.TEN)),
                (PlayerId(2), Card(Suit.SPADES, Rank.ACE)),
                (PlayerId(3), Card(Suit.SPADES, Rank.QUEEN)),
                (PlayerId(0), Card(Suit.SPADES, Rank.KING)),
            ],
        ],
        PlayerId(3): [],
    }
    state.trick_in_progress = [
        (PlayerId(1), Card(Suit.CLUBS, Rank.ACE)),
    ]
    state.hearts_broken = True
    state.turn = PlayerId(0)
    state.trick_number = 2
    state.hand_number = 1
    state.pass_direction = "left"
    state.pass_applied = True
    state.scores = {player_id: int(player_id) * 10 for player_id in PLAYER_IDS}

    view = build_search_player_view(state=state, player_id=PlayerId(0))

    assert view.player_id == PlayerId(0)
    assert view.hand == (
        Card(Suit.CLUBS, Rank.THREE),
        Card(Suit.HEARTS, Rank.NINE),
    )
    assert view.legal_moves == (Card(Suit.CLUBS, Rank.THREE),)
    assert view.current_trick == ((PlayerId(1), Card(Suit.CLUBS, Rank.ACE)),)
    assert view.turn == PlayerId(0)
    assert view.hearts_broken is True
    assert view.target_score == state.config.target_score
    assert view.public_knowledge.qs_live is False
    assert Card(Suit.CLUBS, Rank.ACE) in view.public_knowledge.seen_cards
    assert Card(Suit.SPADES, Rank.QUEEN) in view.public_knowledge.seen_cards
    assert Card(Suit.HEARTS, Rank.NINE) in view.public_knowledge.unplayed_cards
    assert view.public_knowledge.remaining_cards_by_player[PlayerId(0)] == 2
    assert view.public_knowledge.remaining_cards_by_player[PlayerId(1)] == 1
    assert view.public_knowledge.void_suits_by_player[PlayerId(2)] == frozenset({Suit.DIAMONDS})


def test_build_search_player_view_keeps_supplied_private_knowledge() -> None:
    state = GameState()
    private = SeatPrivateKnowledge(
        passed_cards_by_recipient={PlayerId(1): (Card(Suit.SPADES, Rank.QUEEN),)}
    )

    view = build_search_player_view(state=state, player_id=PlayerId(0), private_knowledge=private)

    assert view.private_knowledge is private
