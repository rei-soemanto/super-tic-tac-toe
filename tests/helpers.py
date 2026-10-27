import random
from collections.abc import Callable

from super_tic_tac_toe.engine.rules import IS_LINE, NORMAL, O, ONGOING
from super_tic_tac_toe.engine.state import GameState, Placement

# X wins grid 0 with its last placement and is owed a bonus.
BONUS_SEQ: list[Placement] = [(0, 1), (1, 0), (0, 2), (2, 0), (0, 0)]

# X wins grid 0, then the bonus placement (4, 5) also wins grid 4.
NO_CHAIN_SEQ: list[Placement] = [
    (4, 3), (3, 4), (4, 4), (4, 0), (0, 1), (1, 0), (0, 2), (2, 0), (0, 0), (4, 5),
]


def play(moves: list[Placement], state: GameState | None = None) -> GameState:
    state = state or GameState()
    for move in moves:
        assert state.illegal_reason(*move) is None, move
        state.make(*move)
    return state


def random_game(rng: random.Random, max_moves: int = 200) -> GameState:
    state = GameState()
    while state.result == ONGOING and len(state.history) < max_moves:
        state.make(*rng.choice(state.legal_moves()))
    return state


def find_game(predicate: Callable[[GameState], bool], seed: int = 0, tries: int = 5000) -> GameState:
    """Plays seeded random games, stopping at the first position where `predicate` holds."""
    rng = random.Random(seed)
    for _ in range(tries):
        state = GameState()
        while state.result == ONGOING:
            state.make(*rng.choice(state.legal_moves()))
            if predicate(state):
                return state
    raise AssertionError("no random game satisfied the predicate")


def snapshot(state: GameState) -> tuple:
    return (
        [row[:] for row in state.bits],
        state.grid_status[:],
        state.big[:],
        state.closed,
        state.active_grid,
        state.to_move,
        state.phase,
        state.result,
        len(state.history),
        state.hash,
    )


def forced_grid_win(state: GameState) -> bool:
    """O to move with a single legal placement that wins a small grid but not the game."""
    if state.result != ONGOING or state.to_move != O or state.phase != NORMAL:
        return False
    moves = state.legal_moves()
    if len(moves) != 1:
        return False
    grid, cell = moves[0]
    bits = state.bits[O][grid] | 1 << cell
    return IS_LINE[bits] and not IS_LINE[state.big[O] | 1 << grid]
