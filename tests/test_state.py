import random

from super_tic_tac_toe.engine.rules import BONUS, O, ONGOING
from super_tic_tac_toe.engine.state import ACTIVE_KEYS, BONUS_KEY, CELL_KEYS, FREE, SIDE_KEY, GameState
from tests.helpers import snapshot


def full_hash(state: GameState) -> int:
    h = 0
    for player in range(2):
        for grid in range(9):
            for cell in range(9):
                if state.bits[player][grid] >> cell & 1:
                    h ^= CELL_KEYS[player][grid * 9 + cell]
    h ^= ACTIVE_KEYS[FREE if state.active_grid is None else state.active_grid]
    if state.phase == BONUS:
        h ^= BONUS_KEY
    if state.to_move == O:
        h ^= SIDE_KEY
    return h


def test_make_unmake_restores_everything() -> None:
    rng = random.Random(7)
    for _ in range(200):
        state = GameState()
        snapshots = []
        while state.result == ONGOING:
            snapshots.append(snapshot(state))
            state.make(*rng.choice(state.legal_moves()))
            assert state.hash == full_hash(state)
        while snapshots:
            state.unmake()
            assert snapshot(state) == snapshots.pop()


def test_to_dict_shape() -> None:
    state = GameState()
    state.make(4, 2)
    data = state.to_dict()
    assert data["cells"][4 * 9 + 2] == "X"
    assert data["cells"].count(None) == 80
    assert data["gridStatus"] == ["open"] * 9
    assert data["activeGrid"] == 2
    assert data["toMove"] == "O"
    assert data["phase"] == "NORMAL"
    assert data["result"] == "ongoing"
    assert data["history"] == [(4, 2)]
    assert len(data["legalMoves"]) == 9
