from dataclasses import replace

import pytest

from super_tic_tac_toe.engine.rules import BONUS, O, ONGOING, X
from super_tic_tac_toe.engine.state import GameState, Placement, replay
from super_tic_tac_toe.game.ai_runner import AiOutcome, AiRequest, AiTurn, compute_turn
from super_tic_tac_toe.game.clock import timeout_winner
from super_tic_tac_toe.game.session import AI_REVEAL_S, GameEnd, GameSession, Status, Timeout
from super_tic_tac_toe.game.settings import Settings
from tests.helpers import BONUS_SEQ, find_game, forced_grid_win

COMPETITIVE = Settings(mode="competitive", competitive_seconds=10)
TIME_BASED = Settings(mode="time_based", time_based_minutes=1)
FREE = Settings(mode="free")


def started(settings: Settings = COMPETITIVE, history: list[Placement] | None = None) -> GameSession:
    session = GameSession(settings)
    session.start(settings, now=0.0)
    if history:
        session.state = replay(history)
        session.turn_starts = [len(history)]
    return session


def turn(*moves: Placement) -> AiTurn:
    return AiTurn(moves=moves, depth_reached=4, nodes=1200, time_ms=30.0, score=12)


def answer(session: GameSession, now: float, *moves: Placement) -> None:
    session.ai_outcome(AiOutcome(session.request_id, turn(*moves)), now)


def bonus_position() -> tuple[GameState, AiTurn]:
    """O to move with a forced grid win, and the real two-placement AI turn from there."""
    state = find_game(forced_grid_win, seed=2, tries=20000)
    ai = compute_turn(AiRequest(1, tuple(state.placements()), "easy", None, None))
    assert len(ai.moves) == 2
    return state, ai


def at_ai_turn(settings: Settings, state: GameState, now: float) -> GameSession:
    session = started(settings)
    session.state = replay(state.placements())
    session.status = Status.AI_THINKING
    session.request_id = 1
    session.ai_requested_at = now
    return session


class TestTurnFlow:
    def test_starts_on_human_turn(self) -> None:
        session = started()
        assert session.status == Status.HUMAN_TURN
        assert session.turn_starts == [0]

    def test_hands_over_to_ai_after_a_normal_placement(self) -> None:
        session = started()
        assert session.play(4, 2, now=1.0)
        assert session.status == Status.AI_THINKING
        assert session.request_id == 1
        assert session.ai_requested_at == 1.0

    def test_ai_request_is_issued_once(self) -> None:
        session = started()
        session.play(4, 2, now=1.0)
        request = session.ai_request(now=1.0)
        assert request is not None
        assert request.history == ((4, 2),)
        assert request.time_budget_ms == 9500
        assert request.game_time_left_ms is None
        assert session.ai_request(now=1.1) is None

    def test_bonus_keeps_human_with_fresh_clock(self) -> None:
        session = started(history=BONUS_SEQ[:-1])
        assert session.play(0, 0, now=4.0)
        assert session.state.phase == BONUS
        assert session.status == Status.HUMAN_TURN
        assert session.in_bonus
        assert session.placement_started_at == 4.0

    def test_illegal_click_flashes_without_moving(self) -> None:
        session = started()
        session.play(4, 2, now=1.0)
        answer(session, 1.5, (2, 4))
        assert not session.play(3, 0, now=2.0)
        assert session.flash_at == 2.0
        assert len(session.state.history) == 2

    def test_single_ai_placement_returns_to_human(self) -> None:
        session = started()
        session.play(4, 2, now=1.0)
        answer(session, 1.5, (2, 4))
        assert session.status == Status.HUMAN_TURN
        assert session.stats is not None
        assert session.placement_started_at == 1.5
        assert session.turn_starts == [0, 2]

    def test_two_ai_placements_are_revealed_one_at_a_time(self) -> None:
        state, ai = bonus_position()
        session = at_ai_turn(FREE, state, now=1.0)
        before = len(session.state.history)
        session.ai_outcome(AiOutcome(1, ai), now=1.5)
        assert session.status == Status.ANIMATING_AI
        assert len(session.state.history) == before + 1
        session.tick(1.5 + AI_REVEAL_S / 2)
        assert len(session.state.history) == before + 1
        session.tick(1.5 + AI_REVEAL_S + 0.01)
        assert len(session.state.history) == before + 2
        assert session.status in (Status.HUMAN_TURN, Status.GAME_OVER)

    def test_stale_ai_result_is_ignored(self) -> None:
        session = started()
        session.play(4, 2, now=1.0)
        session.ai_outcome(AiOutcome(0, turn((2, 4))), now=1.5)
        assert session.status == Status.AI_THINKING
        assert len(session.state.history) == 1

    def test_ai_error_can_be_retried_with_a_new_request(self) -> None:
        session = started(FREE)
        session.play(4, 2, now=1.0)
        session.ai_request(now=1.0)
        session.ai_outcome(AiOutcome(1, None, "The AI stopped unexpectedly."), now=1.2)
        assert session.error == "The AI stopped unexpectedly."
        assert session.ai_request(now=1.3) is None
        session.retry()
        assert session.error is None
        assert session.ai_request(now=1.4).request_id == 2

    def test_win_ends_the_game(self) -> None:
        state = find_game(lambda s: s.result == ONGOING and s.to_move == X and _x_wins_now(s), seed=3)
        move = next(m for m in state.legal_moves() if _wins(state, m))
        session = started(history=state.placements())
        session.play(*move, now=2.0)
        assert session.status == Status.GAME_OVER
        assert session.end == GameEnd("win", X)


class TestCompetitive:
    def test_human_loses_when_placement_clock_runs_out(self) -> None:
        session = started()
        session.tick(10.0)
        assert session.end == GameEnd("timeout", O, Timeout.HUMAN)

    def test_move_after_expiry_is_rejected(self) -> None:
        session = started()
        assert not session.play(4, 2, now=10.0)
        assert session.end == GameEnd("timeout", O, Timeout.HUMAN)

    def test_ai_loses_when_its_result_arrives_late(self) -> None:
        session = started()
        session.play(4, 2, now=0.0)
        answer(session, 10.01, (2, 4))
        assert session.end == GameEnd("timeout", X, Timeout.AI)

    def test_ai_gets_one_limit_per_placement(self) -> None:
        state, ai = bonus_position()
        session = at_ai_turn(COMPETITIVE, state, now=0.0)
        session.ai_outcome(AiOutcome(1, ai), now=15.0)
        assert session.status == Status.ANIMATING_AI

    def test_ai_loses_when_it_never_answers(self) -> None:
        session = started()
        session.play(4, 2, now=0.0)
        session.tick(19.9)
        assert session.status == Status.AI_THINKING
        session.tick(20.0)
        assert session.end == GameEnd("timeout", X, Timeout.AI)


class TestTimeBased:
    def test_more_small_grids_wins(self) -> None:
        session = started(TIME_BASED, history=BONUS_SEQ)
        session.tick(60.0)
        assert session.end == GameEnd("timeout", X, Timeout.GAME)

    def test_equal_small_grids_is_a_draw(self) -> None:
        session = started(TIME_BASED)
        session.tick(60.0)
        assert session.end == GameEnd("timeout", None, Timeout.GAME)

    def test_ai_moves_already_animating_count(self) -> None:
        state, ai = bonus_position()
        session = at_ai_turn(TIME_BASED, state, now=59.0)
        session.ai_outcome(AiOutcome(1, ai), now=59.8)
        session.tick(60.0)
        assert len(session.state.history) == len(state.history) + 2
        assert session.status == Status.GAME_OVER
        if session.end.reason == "timeout":
            assert session.end.winner == timeout_winner(session.state)

    def test_ai_result_after_time_is_up_is_discarded(self) -> None:
        session = started(TIME_BASED)
        session.play(4, 2, now=1.0)
        session.tick(60.0)
        answer(session, 60.1, (2, 4))
        assert len(session.state.history) == 1

    def test_no_per_placement_limit(self) -> None:
        session = started(TIME_BASED)
        session.tick(59.0)
        assert session.status == Status.HUMAN_TURN

    def test_ai_request_carries_game_time_left(self) -> None:
        session = started(TIME_BASED)
        session.play(4, 2, now=20.0)
        request = session.ai_request(now=20.0)
        assert request.game_time_left_ms == 40_000


class TestFreeMode:
    def test_has_no_timeouts(self) -> None:
        session = started(FREE)
        session.tick(10_000.0)
        assert session.status == Status.HUMAN_TURN

    def test_undo_takes_back_human_turn_and_ai_reply(self) -> None:
        session = started(FREE)
        session.play(4, 2, now=1.0)
        answer(session, 1.5, (2, 4))
        assert session.can_undo()
        session.undo(now=2.0)
        assert session.state.history == []
        assert session.turn_starts == [0]
        assert not session.can_undo()

    def test_undo_restores_the_exact_position(self) -> None:
        session = started(FREE)
        session.play(4, 2, now=1.0)
        answer(session, 1.5, (2, 4))
        before = session.state.to_dict()
        session.play(4, 0, now=2.0)
        answer(session, 2.5, (0, 4))
        session.undo(now=3.0)
        assert session.state.to_dict() == before

    def test_undo_after_game_over(self) -> None:
        state = find_game(lambda s: s.result == ONGOING and s.to_move == X and _x_wins_now(s), seed=3)
        move = next(m for m in state.legal_moves() if _wins(state, m))
        session = started(FREE, history=state.placements())
        session.play(*move, now=2.0)
        assert session.can_undo()
        session.undo(now=3.0)
        assert session.status == Status.HUMAN_TURN
        assert session.end is None
        assert session.state.placements() == state.placements()

    def test_cannot_undo_while_ai_thinks(self) -> None:
        session = started(FREE)
        session.play(4, 2, now=1.0)
        assert not session.can_undo()

    @pytest.mark.parametrize("settings", [COMPETITIVE, TIME_BASED])
    def test_undo_disabled_in_timed_modes(self, settings: Settings) -> None:
        session = started(settings)
        session.play(4, 2, now=1.0)
        answer(session, 1.5, (2, 4))
        assert not session.can_undo()
        session.undo(now=2.0)
        assert len(session.state.history) == 2


def test_change_settings_returns_to_setup_and_keeps_settings() -> None:
    session = started(replace(FREE, difficulty="hard"))
    session.change_settings()
    assert session.status == Status.SETUP
    assert session.settings.difficulty == "hard"


def _wins(state: GameState, move: Placement) -> bool:
    state.make(*move)
    won = state.result == X + 1
    state.unmake()
    return won


def _x_wins_now(state: GameState) -> bool:
    return any(_wins(state, m) for m in state.legal_moves())
