import random
from collections.abc import Iterator

import pytest

from super_tic_tac_toe.ai.agent import choose_turn
from super_tic_tac_toe.ai.search import SearchConfig, Searcher
from super_tic_tac_toe.engine.rules import BONUS, NORMAL, O, ONGOING, X, won_by
from super_tic_tac_toe.engine.state import GameState, Placement
from tests.helpers import find_game

MINIMAX = SearchConfig(alphabeta=False, ordering=False, tt=False)
VARIANTS = [
    SearchConfig(alphabeta=True, ordering=False, tt=False),
    SearchConfig(alphabeta=True, ordering=True, tt=False),
    SearchConfig(alphabeta=True, ordering=True, tt=True),
]


def random_positions(count: int, seed: int, max_moves: int = 40) -> Iterator[GameState]:
    rng = random.Random(seed)
    produced = 0
    while produced < count:
        state = GameState()
        for _ in range(rng.randrange(1, max_moves)):
            if state.result != ONGOING:
                break
            state.make(*rng.choice(state.legal_moves()))
        if state.result == ONGOING:
            produced += 1
            yield state


def turns(state: GameState) -> list[list[Placement]]:
    """Every complete turn (one placement, or two with a bonus) for the side to move."""
    player = state.to_move
    result = []
    for move in state.legal_moves():
        state.make(*move)
        if state.result == ONGOING and state.to_move == player and state.phase == BONUS:
            result.extend([move, second] for second in state.legal_moves())
        else:
            result.append([move])
        state.unmake()
    return result


def wins_this_turn(state: GameState) -> bool:
    player = state.to_move
    for turn in turns(state):
        for move in turn:
            state.make(*move)
        won = state.result == won_by(player)
        for _ in turn:
            state.unmake()
        if won:
            return True
    return False


@pytest.mark.parametrize("config", VARIANTS, ids=["alphabeta", "ordering", "tt"])
def test_pruning_matches_plain_minimax(config: SearchConfig) -> None:
    for state in random_positions(12, seed=3):
        depth = 4 if state.active_grid is not None and len(state.legal_moves()) <= 6 else 3
        expected, _ = Searcher(MINIMAX).search_depth(state, depth)
        actual, _ = Searcher(config).search_depth(state, depth)
        assert actual == expected


def test_takes_an_immediate_win() -> None:
    def o_can_win(state: GameState) -> bool:
        return (
            state.result == ONGOING
            and state.to_move == O
            and state.phase == NORMAL
            and state.active_grid is not None
            and wins_this_turn(state)
        )

    state = find_game(o_can_win, seed=11)
    turn = choose_turn(state, "easy")
    assert turn.state.result == won_by(O)


def test_blocks_the_opponents_win() -> None:
    def must_block(state: GameState) -> bool:
        if state.result != ONGOING or state.to_move != O or state.phase != NORMAL:
            return False
        if state.active_grid is None or wins_this_turn(state):
            return False
        threatened = safe = False
        for turn in turns(state):
            for move in turn:
                state.make(*move)
            if state.result == ONGOING and state.to_move == X:
                if wins_this_turn(state):
                    threatened = True
                else:
                    safe = True
            for _ in turn:
                state.unmake()
        return threatened and safe

    state = find_game(must_block, seed=5)
    turn = choose_turn(state, "medium")
    assert turn.state.result != ONGOING or not wins_this_turn(turn.state)


@pytest.mark.parametrize("budget_ms", [100, 300])
def test_search_respects_time_budget(budget_ms: int) -> None:
    for state in random_positions(3, seed=9, max_moves=10):
        result = Searcher().search(state, 64, budget_ms)
        assert result.time_ms <= budget_ms + 150
        assert result.depth >= 1
