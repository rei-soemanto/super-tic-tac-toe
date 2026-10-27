"""Bit-level rule primitives shared by the engine, evaluation and search.

A 3x3 grid is a 9-bit mask; bit i is cell i (0-8, left to right, top to bottom).
The same encoding is used for small grids and for the big grid.
"""

X, O = 0, 1

OPEN, DRAW = 0, 3
ONGOING = 0

NORMAL, BONUS = 0, 1

FULL = 0x1FF
CENTER = 4

LINES = (
    0b000000111,
    0b000111000,
    0b111000000,
    0b001001001,
    0b010010010,
    0b100100100,
    0b100010001,
    0b001010100,
)

POSITION_WEIGHT = (1.2, 1.0, 1.2, 1.0, 1.5, 1.0, 1.2, 1.0, 1.2)


def won_by(player: int) -> int:
    """Grid status / game result code for a grid or game won by `player`."""
    return player + 1


def _build_tables() -> tuple[list[bool], list[tuple[int, ...]], list[int], list[int], list[int]]:
    is_line = [any(mask & line == line for line in LINES) for mask in range(512)]
    cells_of = [tuple(i for i in range(9) if mask >> i & 1) for mask in range(512)]

    size = 1 << 18
    two_open = [0] * size
    one_open = [0] * size
    win_cells = [0] * size
    for own in range(512):
        for opp in range(512):
            if own & opp:
                continue
            twos = ones = wins = 0
            for line in LINES:
                if line & opp:
                    continue
                count = (own & line).bit_count()
                if count == 2:
                    twos += 1
                    wins |= line & ~own
                elif count == 1:
                    ones += 1
            index = own | opp << 9
            two_open[index] = twos
            one_open[index] = ones
            win_cells[index] = wins
    return is_line, cells_of, two_open, one_open, win_cells


IS_LINE, CELLS_OF, TWO_OPEN, ONE_OPEN, WIN_CELLS = _build_tables()
"""Lookup tables.

IS_LINE[mask]          mask contains a complete line
CELLS_OF[mask]         indices of the set bits
TWO_OPEN[own|opp<<9]   lines with two `own` marks and the third cell free of `opp`
ONE_OPEN[own|opp<<9]   lines with one `own` mark and two cells free of `opp`
WIN_CELLS[own|opp<<9]  mask of empty cells that complete a line for `own`
"""
