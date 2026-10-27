import logging
from dataclasses import dataclass
from typing import Literal

from super_tic_tac_toe.ai.evaluate import Evaluator, evaluate
from super_tic_tac_toe.ai.search import SearchResult, Searcher
from super_tic_tac_toe.engine.rules import BONUS, O, ONGOING
from super_tic_tac_toe.engine.state import GameState, Placement

logger = logging.getLogger(__name__)

Difficulty = Literal["easy", "medium", "hard"]

LIMITS: dict[str, tuple[int, float | None]] = {
    "easy": (2, None),
    "medium": (4, None),
    "hard": (64, 2000),
}
LOW_TIME_MS = 60_000


class NotAiTurnError(ValueError):
    pass


@dataclass
class TurnResult:
    moves: list[Placement]
    state: GameState
    depth_reached: int
    nodes: int
    time_ms: float
    score: int


def time_pressure(game_time_left_ms: float | None) -> float:
    if game_time_left_ms is None:
        return 0.0
    return max(0.0, min(1.0, 1 - game_time_left_ms / LOW_TIME_MS))


def placement_budget(difficulty: Difficulty, time_budget_ms: float | None) -> float | None:
    limit = LIMITS[difficulty][1]
    budgets = [b for b in (limit, time_budget_ms) if b is not None]
    return min(budgets) if budgets else None


def choose_turn(
    state: GameState,
    difficulty: Difficulty,
    time_budget_ms: float | None = None,
    game_time_left_ms: float | None = None,
    evaluator: Evaluator = evaluate,
) -> TurnResult:
    """Plays every placement of the side to move's turn (1, or 2 with a bonus) on `state`."""
    max_depth = LIMITS[difficulty][0]
    budget = placement_budget(difficulty, time_budget_ms)
    searcher = Searcher(evaluator=evaluator, time_pressure=time_pressure(game_time_left_ms))
    player = state.to_move

    moves: list[Placement] = []
    results: list[SearchResult] = []
    while state.result == ONGOING and state.to_move == player and (not moves or state.phase == BONUS):
        try:
            result = searcher.search(state, max_depth, budget)
        except Exception:
            logger.exception("AI search failed; falling back to the first legal move")
            result = SearchResult(state.legal_moves()[0], 0, 0, 0, 0.0)
        state.make(*result.move)
        moves.append(result.move)
        results.append(result)

    return TurnResult(
        moves=moves,
        state=state,
        depth_reached=min(r.depth for r in results),
        nodes=sum(r.nodes for r in results),
        time_ms=sum(r.time_ms for r in results),
        score=results[-1].score,
    )


def play_turn(
    state: GameState,
    difficulty: Difficulty,
    time_budget_ms: float | None = None,
    game_time_left_ms: float | None = None,
) -> TurnResult:
    if state.result != ONGOING or state.to_move != O:
        raise NotAiTurnError("It is not the AI's turn")
    return choose_turn(state, difficulty, time_budget_ms, game_time_left_ms)
