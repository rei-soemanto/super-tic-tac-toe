import random
from typing import Any

from super_tic_tac_toe.engine.rules import (
    BONUS,
    CELLS_OF,
    DRAW,
    FULL,
    IS_LINE,
    NORMAL,
    O,
    ONGOING,
    OPEN,
    X,
    won_by,
)

Placement = tuple[int, int]

_rng = random.Random(20261014)
CELL_KEYS = [[_rng.getrandbits(64) for _ in range(81)] for _ in range(2)]
ACTIVE_KEYS = [_rng.getrandbits(64) for _ in range(10)]
BONUS_KEY = _rng.getrandbits(64)
SIDE_KEY = _rng.getrandbits(64)
FREE = 9

PLAYER_NAMES = ("X", "O")
STATUS_NAMES = ("open", "X", "O", "draw")
RESULT_NAMES = ("ongoing", "X", "O", "draw")
PHASE_NAMES = ("NORMAL", "BONUS")


class IllegalMoveError(ValueError):
    def __init__(self, index: int, move: Placement, reason: str) -> None:
        self.index = index
        self.move = move
        self.reason = reason
        super().__init__(f"Move {index + 1} {list(move)} is illegal: {reason}")


class GameState:
    __slots__ = (
        "bits",
        "grid_status",
        "big",
        "closed",
        "active_grid",
        "to_move",
        "phase",
        "result",
        "history",
        "hash",
        "bonus_rule",
    )

    def __init__(self, bonus_rule: bool = True) -> None:
        self.bits = [[0] * 9, [0] * 9]
        self.grid_status = [OPEN] * 9
        self.big = [0, 0]
        self.closed = 0
        self.active_grid: int | None = None
        self.to_move = X
        self.phase = NORMAL
        self.result = ONGOING
        self.history: list[tuple] = []
        self.hash = ACTIVE_KEYS[FREE]
        self.bonus_rule = bonus_rule

    def make(self, grid: int, cell: int) -> None:
        player = self.to_move
        active = self.active_grid
        phase = self.phase
        self.history.append((grid, cell, active, player, phase, self.result, self.hash))

        own = self.bits[player]
        own[grid] |= 1 << cell
        h = self.hash ^ CELL_KEYS[player][grid * 9 + cell]
        h ^= ACTIVE_KEYS[FREE if active is None else active]
        if phase == BONUS:
            h ^= BONUS_KEY
        if player == O:
            h ^= SIDE_KEY

        won_grid = False
        if IS_LINE[own[grid]]:
            won_grid = True
            self.grid_status[grid] = won_by(player)
            self.big[player] |= 1 << grid
            self.closed |= 1 << grid
        elif own[grid] | self.bits[1 - player][grid] == FULL:
            self.grid_status[grid] = DRAW
            self.closed |= 1 << grid

        if won_grid and IS_LINE[self.big[player]]:
            self.result = won_by(player)
            self.active_grid = None
            self.phase = NORMAL
        elif self.closed == FULL:
            self.result = DRAW
            self.active_grid = None
            self.phase = NORMAL
        elif won_grid and phase == NORMAL and self.bonus_rule:
            self.phase = BONUS
            self.active_grid = None
        else:
            self.phase = NORMAL
            self.to_move = 1 - player
            self.active_grid = None if self.closed >> cell & 1 else cell

        h ^= ACTIVE_KEYS[FREE if self.active_grid is None else self.active_grid]
        if self.phase == BONUS:
            h ^= BONUS_KEY
        if self.to_move == O:
            h ^= SIDE_KEY
        self.hash = h

    def unmake(self) -> None:
        grid, cell, active, player, phase, result, h = self.history.pop()
        self.bits[player][grid] &= ~(1 << cell)
        status = self.grid_status[grid]
        if status != OPEN:
            self.grid_status[grid] = OPEN
            self.closed &= ~(1 << grid)
            if status != DRAW:
                self.big[status - 1] &= ~(1 << grid)
        self.active_grid = active
        self.to_move = player
        self.phase = phase
        self.result = result
        self.hash = h

    def empty_cells(self, grid: int) -> int:
        return FULL & ~(self.bits[X][grid] | self.bits[O][grid])

    def open_grids(self) -> tuple[int, ...]:
        if self.active_grid is not None:
            return (self.active_grid,)
        return CELLS_OF[FULL & ~self.closed]

    def legal_moves(self) -> list[Placement]:
        if self.result != ONGOING:
            return []
        return [(g, c) for g in self.open_grids() for c in CELLS_OF[self.empty_cells(g)]]

    def illegal_reason(self, grid: int, cell: int) -> str | None:
        if self.result != ONGOING:
            return "the game is already over"
        if not (0 <= grid <= 8 and 0 <= cell <= 8):
            return "grid and cell must be between 0 and 8"
        if self.closed >> grid & 1:
            return f"grid {grid} is closed"
        if self.active_grid is not None and grid != self.active_grid:
            return f"must play in grid {self.active_grid}"
        if not self.empty_cells(grid) >> cell & 1:
            return f"cell {cell} of grid {grid} is occupied"
        return None

    def placements(self) -> list[Placement]:
        return [(record[0], record[1]) for record in self.history]

    def cells(self) -> list[str | None]:
        cells: list[str | None] = [None] * 81
        for player in (X, O):
            for grid, bits in enumerate(self.bits[player]):
                for cell in CELLS_OF[bits]:
                    cells[grid * 9 + cell] = PLAYER_NAMES[player]
        return cells

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells": self.cells(),
            "gridStatus": [STATUS_NAMES[s] for s in self.grid_status],
            "activeGrid": self.active_grid,
            "toMove": PLAYER_NAMES[self.to_move],
            "phase": PHASE_NAMES[self.phase],
            "result": RESULT_NAMES[self.result],
            "legalMoves": self.legal_moves(),
            "history": self.placements(),
        }


def replay(history: list[Placement], bonus_rule: bool = True) -> GameState:
    state = GameState(bonus_rule)
    for index, (grid, cell) in enumerate(history):
        reason = state.illegal_reason(grid, cell)
        if reason:
            raise IllegalMoveError(index, (grid, cell), reason)
        state.make(grid, cell)
    return state
