import math

from super_tic_tac_toe.engine.rules import O, X
from super_tic_tac_toe.engine.state import GameState

COMPETITIVE_WARNING_S = 3  # the clock turns red in the last 3 s of a placement
TIME_BASED_WARNING_S = 30  # the game clock turns red under 30 s


def remaining(limit: float, started_at: float, now: float) -> float:
    """Time left, worked out from timestamps each time it is asked (nothing counts down)."""
    return max(0.0, limit - (now - started_at))


def format_clock(seconds: float) -> str:
    """m:ss, rounded up so 0:00 only shows when time is really up."""
    total = math.ceil(max(0.0, seconds))
    return f"{total // 60}:{total % 60:02d}"


def grids_won(state: GameState) -> tuple[int, int]:
    """Small grids won by (X, O): the set bits of each big-grid bitboard."""
    return state.big[X].bit_count(), state.big[O].bit_count()


def timeout_winner(state: GameState) -> int | None:
    """Time-based mode: whoever has won more small grids when the clock runs out."""
    x, o = grids_won(state)
    if x == o:
        return None
    return X if x > o else O
