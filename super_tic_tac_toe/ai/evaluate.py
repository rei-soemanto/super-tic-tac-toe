from dataclasses import dataclass

from super_tic_tac_toe.engine.rules import CELLS_OF, FULL, NORMAL, ONE_OPEN, POSITION_WEIGHT, TWO_OPEN
from super_tic_tac_toe.engine.state import GameState


@dataclass(frozen=True)
class Weights:
    grid_won: float = 100
    big_two: float = 200
    big_one: float = 30
    small_two: float = 10
    centre: float = 3
    bonus_threat: float = 60
    time_grid: float = 400


class Evaluator:
    """Static evaluation from the side to move: own score minus the opponent's."""

    def __init__(self, weights: Weights = Weights()) -> None:
        self.weights = weights
        self._grid_won = [
            weights.grid_won * sum(POSITION_WEIGHT[g] for g in CELLS_OF[mask]) for mask in range(512)
        ]
        self._small_two = [weights.small_two * w for w in POSITION_WEIGHT]

    def __call__(self, state: GameState, time_pressure: float = 0.0) -> int:
        w = self.weights
        me = state.to_move
        mine, theirs = state.bits[me], state.bits[1 - me]
        my_big, their_big = state.big[me], state.big[1 - me]
        closed = state.closed

        score = self._grid_won[my_big] - self._grid_won[their_big]

        my_index = my_big | (closed ^ my_big) << 9
        their_index = their_big | (closed ^ their_big) << 9
        score += w.big_two * (TWO_OPEN[my_index] - TWO_OPEN[their_index])
        score += w.big_one * (ONE_OPEN[my_index] - ONE_OPEN[their_index])

        small_two = self._small_two
        for g in CELLS_OF[FULL & ~closed]:
            a, b = mine[g], theirs[g]
            twos = TWO_OPEN[a | b << 9] - TWO_OPEN[b | a << 9]
            if twos:
                score += twos * small_two[g]
            score += w.centre * ((a >> 4 & 1) - (b >> 4 & 1))

        if state.phase == NORMAL and state.bonus_rule:
            for g in state.open_grids():
                if TWO_OPEN[mine[g] | theirs[g] << 9]:
                    score += w.bonus_threat
                    break

        if time_pressure:
            score += time_pressure * w.time_grid * (my_big.bit_count() - their_big.bit_count())

        return int(score)


evaluate = Evaluator()
