"""Game flow: turns, clocks, timeouts, AI hand-off and undo.

Every method takes `now` in seconds (time.perf_counter), so the session is deterministic
and has no knowledge of pygame.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from super_tic_tac_toe.engine.rules import BONUS, DRAW, ONGOING, O, X
from super_tic_tac_toe.engine.state import GameState, Placement
from super_tic_tac_toe.game.ai_runner import AiOutcome, AiRequest, AiTurn
from super_tic_tac_toe.game.clock import remaining, timeout_winner
from super_tic_tac_toe.game.settings import Settings
from super_tic_tac_toe.game.time_budget import time_budget_ms

HUMAN, AI = X, O
MAX_AI_PLACEMENTS = 2
AI_REVEAL_S = 0.4


class Status(StrEnum):
    SETUP = "setup"
    HUMAN_TURN = "human_turn"
    AI_THINKING = "ai_thinking"
    ANIMATING_AI = "animating_ai"
    GAME_OVER = "game_over"


class Timeout(StrEnum):
    HUMAN = "human"
    AI = "ai"
    GAME = "game"


@dataclass(frozen=True)
class GameEnd:
    reason: str
    winner: int | None
    timed_out: Timeout | None = None


class GameSession:
    def __init__(self, settings: Settings) -> None:
        self._reset(settings)

    def _reset(self, settings: Settings) -> None:
        self.settings = settings
        self.status = Status.SETUP
        self.state = GameState()
        self.turn_starts: list[int] = []
        self.request_id = 0
        self.requested = False
        self.pending: list[Placement] = []
        self.stats: AiTurn | None = None
        self.end: GameEnd | None = None
        self.error: str | None = None
        self.flash_at: float | None = None
        self.game_started_at = 0.0
        self.placement_started_at = 0.0
        self.ai_requested_at = 0.0
        self.revealed_at = 0.0
        self.ended_at: float | None = None
        self.now = 0.0

    @property
    def placement_limit(self) -> float:
        return float(self.settings.competitive_seconds)

    @property
    def game_limit(self) -> float:
        return self.settings.time_based_minutes * 60.0

    @property
    def clock_now(self) -> float:
        return self.ended_at if self.ended_at is not None else self.now

    @property
    def last_move(self) -> Placement | None:
        history = self.state.history
        return (history[-1][0], history[-1][1]) if history else None

    @property
    def in_bonus(self) -> bool:
        return self.status == Status.HUMAN_TURN and self.state.phase == BONUS

    def start(self, settings: Settings, now: float) -> None:
        self._reset(settings)
        self.status = Status.HUMAN_TURN
        self.turn_starts = [0]
        self.game_started_at = self.placement_started_at = self.ai_requested_at = now
        self.now = now

    def change_settings(self) -> None:
        self._reset(self.settings)

    def update_settings(self, **changes: object) -> None:
        self.settings = replace(self.settings, **changes)

    def play(self, grid: int, cell: int, now: float) -> bool:
        if self.status != Status.HUMAN_TURN:
            return False
        if self.expired_clock(now):
            self.tick(now)
            return False
        if self.state.illegal_reason(grid, cell):
            self.flash_at = now
            return False

        self.now = now
        self.state.make(grid, cell)
        if self.state.result != ONGOING:
            self._finish(self._end_from_result(), now)
        elif self.state.to_move == HUMAN:
            self.placement_started_at = now
        else:
            self.status = Status.AI_THINKING
            self.request_id += 1
            self.requested = False
            self.ai_requested_at = now
        return True

    def ai_request(self, now: float) -> AiRequest | None:
        """The next AI search to run, once per request id."""
        if self.status != Status.AI_THINKING or self.requested or self.error:
            return None
        self.requested = True
        left = None
        if self.settings.mode == "time_based":
            left = int(remaining(self.game_limit, self.game_started_at, now) * 1000)
        return AiRequest(
            request_id=self.request_id,
            history=tuple(self.state.placements()),
            difficulty=self.settings.difficulty,
            time_budget_ms=time_budget_ms(self.settings, self.state, left),
            game_time_left_ms=left,
        )

    def ai_outcome(self, outcome: AiOutcome, now: float) -> None:
        if self.status != Status.AI_THINKING or outcome.request_id != self.request_id:
            return
        if outcome.turn is None:
            self.error = outcome.error or "The AI failed."
            return

        turn = outcome.turn
        elapsed = now - self.ai_requested_at
        if self.settings.mode == "competitive" and elapsed > self.placement_limit * len(turn.moves):
            self._timeout(Timeout.AI, now)
            return

        self.stats = turn
        self.error = None
        self.pending = list(turn.moves)
        self._reveal(now)
        if self.pending:
            self.status = Status.ANIMATING_AI

    def retry(self) -> None:
        if self.status == Status.AI_THINKING and self.error:
            self.error = None
            self.request_id += 1
            self.requested = False

    def tick(self, now: float) -> None:
        if self.status in (Status.SETUP, Status.GAME_OVER):
            return
        self.now = now
        expired = self.expired_clock(now)
        if expired:
            self._timeout(expired, now)
        elif self.status == Status.ANIMATING_AI and now - self.revealed_at >= AI_REVEAL_S:
            self._reveal(now)

    def expired_clock(self, now: float) -> Timeout | None:
        if self.status in (Status.SETUP, Status.GAME_OVER):
            return None
        mode = self.settings.mode
        if mode == "time_based" and now - self.game_started_at >= self.game_limit:
            return Timeout.GAME
        if mode == "competitive":
            limit = self.placement_limit
            if self.status == Status.HUMAN_TURN and now - self.placement_started_at >= limit:
                return Timeout.HUMAN
            if self.status == Status.AI_THINKING and now - self.ai_requested_at >= limit * MAX_AI_PLACEMENTS:
                return Timeout.AI
        return None

    def can_undo(self) -> bool:
        if self.settings.mode != "free" or self.status not in (Status.HUMAN_TURN, Status.GAME_OVER):
            return False
        return len(self.state.history) > self.turn_starts[-1] or len(self.turn_starts) > 1

    def undo(self, now: float) -> None:
        """Takes back the human's last turn (bonus included) and the AI's reply."""
        if not self.can_undo():
            return
        if len(self.state.history) <= self.turn_starts[-1]:
            self.turn_starts.pop()
        while len(self.state.history) > self.turn_starts[-1]:
            self.state.unmake()
        self.status = Status.HUMAN_TURN
        self.end = None
        self.error = None
        self.ended_at = None
        self.placement_started_at = now
        self.now = now

    def _reveal(self, now: float) -> None:
        if self.pending:
            self.state.make(*self.pending.pop(0))
            self.revealed_at = now
        if not self.pending:
            self._begin_human_turn(now)

    def _begin_human_turn(self, now: float) -> None:
        if self.state.result != ONGOING:
            self._finish(self._end_from_result(), now)
            return
        self.status = Status.HUMAN_TURN
        self.turn_starts.append(len(self.state.history))
        self.placement_started_at = now

    def _timeout(self, kind: Timeout, now: float) -> None:
        if kind == Timeout.HUMAN:
            self._finish(GameEnd("timeout", AI, kind), now)
        elif kind == Timeout.AI:
            self._finish(GameEnd("timeout", HUMAN, kind), now)
        else:
            while self.pending and self.state.result == ONGOING:
                self.state.make(*self.pending.pop(0))
            if self.state.result != ONGOING:
                self._finish(self._end_from_result(), now)
            else:
                self._finish(GameEnd("timeout", timeout_winner(self.state), kind), now)

    def _end_from_result(self) -> GameEnd:
        if self.state.result == DRAW:
            return GameEnd("draw", None)
        return GameEnd("win", self.state.result - 1)

    def _finish(self, end: GameEnd, now: float) -> None:
        self.status = Status.GAME_OVER
        self.end = end
        self.pending = []
        self.error = None
        self.ended_at = now
        self.now = now
