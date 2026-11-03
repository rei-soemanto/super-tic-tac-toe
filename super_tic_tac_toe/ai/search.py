from dataclasses import dataclass, field
from time import perf_counter

from super_tic_tac_toe.ai.evaluate import Evaluator, evaluate
from super_tic_tac_toe.ai.ttable import EXACT, LOWER, MATE, MATE_BOUND, UPPER, TranspositionTable
from super_tic_tac_toe.engine.rules import CENTER, DRAW, ONGOING, WIN_CELLS
from super_tic_tac_toe.engine.state import GameState, Placement

INF = 1_000_000
CHECK_EVERY = 2048


class SearchTimeout(Exception):
    pass


# Feature switches; tests and benchmarks turn them off to compare against plain minimax.
@dataclass(frozen=True)
class SearchConfig:
    alphabeta: bool = True
    ordering: bool = True
    tt: bool = True


@dataclass
class SearchResult:
    move: Placement
    score: int
    depth: int
    nodes: int
    time_ms: float
    completed: list[int] = field(default_factory=list)


class Searcher:
    """Negamax over placements. The score sign flips only when the side to move changes."""

    def __init__(
        self,
        config: SearchConfig = SearchConfig(),
        evaluator: Evaluator = evaluate,
        time_pressure: float = 0.0,
    ) -> None:
        self.config = config
        self.evaluator = evaluator
        self.time_pressure = time_pressure
        self.tt = TranspositionTable()
        self.nodes = 0
        self.deadline: float | None = None
        self.root_hint: Placement | None = None
        self.root_move: Placement | None = None

    def search(self, state: GameState, max_depth: int, time_limit_ms: float | None = None) -> SearchResult:
        start = perf_counter()
        self.nodes = 0
        moves = state.legal_moves()
        if not moves:
            raise ValueError("no legal moves")
        if len(moves) == 1:
            return SearchResult(moves[0], self.evaluator(state, self.time_pressure), 0, 0, 0.0)

        deadline = start + time_limit_ms / 1000 if time_limit_ms is not None else None
        max_depth = min(max_depth, 81 - len(state.history))
        best, score, depth_done = moves[0], 0, 0
        completed: list[int] = []
        root_len = len(state.history)
        self.root_hint = None
        try:
            # Iterative deepening: search depth 1, 2, 3 ... until the depth limit or the deadline.
            for depth in range(1, max_depth + 1):
                self.deadline = deadline if depth > 1 else None # depth 1 always finishes
                try:
                    score = self.negamax(state, depth, -INF, INF, 0)
                except SearchTimeout:
                    break # out of time: keep the best move of the last finished depth
                best = self.root_move or best
                depth_done = depth
                completed.append(self.nodes)
                self.root_hint = best # searched first in the next, deeper pass
                if abs(score) > MATE_BOUND:
                    break # forced win or loss found: looking deeper cannot change it
                if deadline is not None and perf_counter() >= deadline:
                    break
        finally:
            while len(state.history) > root_len: # undo placements left by an aborted pass
                state.unmake()
            self.deadline = None

        elapsed = (perf_counter() - start) * 1000
        return SearchResult(best, score, depth_done, self.nodes, elapsed, completed)

    def search_depth(self, state: GameState, depth: int) -> tuple[int, Placement | None]:
        """Single fixed-depth search with no time limit, used by tests and benchmarks."""
        self.nodes = 0
        self.root_hint = None
        self.root_move = None
        score = self.negamax(state, depth, -INF, INF, 0)
        return score, self.root_move

    def negamax(self, state: GameState, depth: int, alpha: int, beta: int, ply: int) -> int:
        """Minimax in negamax form with alpha-beta: the score for the side to move."""
        self.nodes += 1
        if self.deadline is not None and self.nodes % CHECK_EVERY == 0 and perf_counter() > self.deadline:
            raise SearchTimeout

        result = state.result
        if result != ONGOING: # finished game: faster wins score higher (MATE - ply)
            if result == DRAW:
                return 0
            return MATE - ply if result - 1 == state.to_move else -MATE + ply
        if depth == 0: # depth limit reached: estimate the position instead of looking further
            return self.evaluator(state, self.time_pressure)

        config = self.config
        alpha_start = alpha
        tt_move = None
        if config.tt: # transposition table: reuse a result stored under this position's key
            entry = self.tt.probe(state.hash, ply)
            if entry is not None:
                entry_depth, entry_score, flag, tt_move = entry
                if entry_depth >= depth and ply > 0:
                    if flag == EXACT:
                        return entry_score
                    if flag == LOWER:
                        alpha = max(alpha, entry_score)
                    elif flag == UPPER:
                        beta = min(beta, entry_score)
                    if alpha >= beta:
                        return entry_score

        moves = state.legal_moves()
        if config.ordering: # move ordering: promising moves first so alpha-beta cuts more
            moves = self.order(state, moves, tt_move, self.root_hint if ply == 0 else None)

        player = state.to_move
        best = -INF
        best_move = None
        for move in moves:
            state.make(*move)
            if state.to_move == player: # bonus placement: same player, so no sign flip
                score = self.negamax(state, depth - 1, alpha, beta, ply + 1)
            else: # turn passes: the opponent's score is negated and the window flipped
                score = -self.negamax(state, depth - 1, -beta, -alpha, ply + 1)
            state.unmake() # take the move back; the board is never copied
            if score > best:
                best = score
                best_move = move
                if config.alphabeta: # alpha-beta pruning
                    if best > alpha:
                        alpha = best
                    if alpha >= beta: # the opponent already has a better option elsewhere: stop
                        break

        if ply == 0:
            self.root_move = best_move # the move the AI will play
        if config.tt: # store the result: an exact score, or only a bound if alpha-beta cut it short
            if not config.alphabeta or alpha_start < best < beta:
                flag = EXACT
            elif best <= alpha_start:
                flag = UPPER
            else:
                flag = LOWER
            self.tt.store(state.hash, depth, best, flag, best_move, ply)
        return best

    @staticmethod
    def order(
        state: GameState, moves: list[Placement], tt_move: Placement | None, hint: Placement | None
    ) -> list[Placement]:
        """Move ordering: TT move, previous best, grid wins, blocks, centre cells, then the rest."""
        mine = state.bits[state.to_move]
        theirs = state.bits[1 - state.to_move]

        def key(move: Placement) -> int:
            if move == tt_move:
                return 5
            if move == hint:
                return 4
            grid, cell = move
            a, b = mine[grid], theirs[grid]
            if WIN_CELLS[a | b << 9] >> cell & 1:
                return 3
            if WIN_CELLS[b | a << 9] >> cell & 1:
                return 2
            return 1 if cell == CENTER else 0

        return sorted(moves, key=key, reverse=True)
