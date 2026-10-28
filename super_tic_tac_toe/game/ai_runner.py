"""Runs the AI search off the UI thread.

The search is CPU-bound pure Python, so it runs in a separate process: the window keeps its
frame rate and the search keeps a full core. The worker receives the placement history and
replays it, the same stateless shape the AI had behind the old HTTP API.
"""

from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from typing import Protocol

from super_tic_tac_toe.ai.agent import play_turn
from super_tic_tac_toe.engine.state import Placement, replay
from super_tic_tac_toe.game.settings import Difficulty


@dataclass(frozen=True)
class AiRequest:
    request_id: int
    history: tuple[Placement, ...]
    difficulty: Difficulty
    time_budget_ms: int | None
    game_time_left_ms: int | None


@dataclass(frozen=True)
class AiTurn:
    moves: tuple[Placement, ...]
    depth_reached: int
    nodes: int
    time_ms: float
    score: int


@dataclass(frozen=True)
class AiOutcome:
    request_id: int
    turn: AiTurn | None
    error: str | None = None


def compute_turn(request: AiRequest) -> AiTurn:
    turn = play_turn(
        replay(list(request.history)),
        request.difficulty,
        request.time_budget_ms,
        request.game_time_left_ms,
    )
    return AiTurn(tuple(turn.moves), turn.depth_reached, turn.nodes, turn.time_ms, turn.score)


class AiRunner(Protocol):
    def submit(self, request: AiRequest) -> None: ...
    def poll(self) -> list[AiOutcome]: ...
    def close(self) -> None: ...


class SyncAiRunner:
    """Computes on submit; used by tests."""

    def __init__(self) -> None:
        self._done: list[AiOutcome] = []

    def submit(self, request: AiRequest) -> None:
        try:
            self._done.append(AiOutcome(request.request_id, compute_turn(request)))
        except Exception as error:
            self._done.append(AiOutcome(request.request_id, None, f"The AI failed: {error}"))

    def poll(self) -> list[AiOutcome]:
        done, self._done = self._done, []
        return done

    def close(self) -> None:
        pass


class ProcessAiRunner:
    def __init__(self) -> None:
        self._pool = ProcessPoolExecutor(max_workers=1)
        self._futures: list[tuple[int, Future[AiTurn]]] = []

    def warm_up(self) -> None:
        self._pool.submit(int)

    def submit(self, request: AiRequest) -> None:
        try:
            future = self._pool.submit(compute_turn, request)
        except BrokenProcessPool:
            self._restart()
            future = self._pool.submit(compute_turn, request)
        self._futures.append((request.request_id, future))

    def poll(self) -> list[AiOutcome]:
        outcomes = []
        pending = []
        for request_id, future in self._futures:
            if not future.done():
                pending.append((request_id, future))
                continue
            try:
                outcomes.append(AiOutcome(request_id, future.result()))
            except BrokenProcessPool:
                self._restart()
                outcomes.append(AiOutcome(request_id, None, "The AI stopped unexpectedly."))
            except Exception as error:
                outcomes.append(AiOutcome(request_id, None, f"The AI failed: {error}"))
        self._futures = pending
        return outcomes

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _restart(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._pool = ProcessPoolExecutor(max_workers=1)
