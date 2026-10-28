import math

from super_tic_tac_toe.engine.rules import CELLS_OF, FULL
from super_tic_tac_toe.engine.state import GameState
from super_tic_tac_toe.game.settings import Difficulty, Settings

HARD_LIMIT_MS = 2000
SAFETY_MARGIN_MS = 500
MIN_MOVES_LEFT = 10


def difficulty_limit_ms(difficulty: Difficulty) -> int | None:
    return HARD_LIMIT_MS if difficulty == "hard" else None


def empty_cells_in_open_grids(state: GameState) -> int:
    return sum(state.empty_cells(g).bit_count() for g in CELLS_OF[FULL & ~state.closed])


def time_budget_ms(settings: Settings, state: GameState, game_time_left_ms: float | None = None) -> int | None:
    """Search budget for each AI placement (spec 6.3)."""
    limit = difficulty_limit_ms(settings.difficulty)
    if settings.mode == "free":
        return limit

    cap = math.inf if limit is None else limit
    if settings.mode == "competitive":
        budget = min(cap, settings.competitive_seconds * 1000 - SAFETY_MARGIN_MS)
    else:
        moves_left = max(MIN_MOVES_LEFT, empty_cells_in_open_grids(state) / 2)
        budget = min(cap, (game_time_left_ms or 0) / moves_left)
    return max(1, math.floor(budget))
