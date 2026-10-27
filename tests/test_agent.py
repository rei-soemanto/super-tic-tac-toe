import pytest

from super_tic_tac_toe.ai import agent
from super_tic_tac_toe.ai.agent import NotAiTurnError, placement_budget, play_turn, time_pressure
from super_tic_tac_toe.ai.search import Searcher
from super_tic_tac_toe.engine.rules import O, ONGOING
from super_tic_tac_toe.engine.state import GameState, replay
from tests.helpers import find_game, forced_grid_win


def test_bonus_turn_returns_two_placements() -> None:
    state = find_game(forced_grid_win, seed=2, tries=20000)
    forced = state.legal_moves()[0]
    turn = play_turn(state, "easy")
    assert len(turn.moves) == 2
    assert turn.moves[0] == forced
    assert turn.state.to_move != O or turn.state.result != ONGOING


def test_rejects_when_not_ai_turn() -> None:
    with pytest.raises(NotAiTurnError):
        play_turn(GameState(), "easy")


def test_falls_back_to_first_legal_move_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(Searcher, "search", broken)
    turn = play_turn(replay([(4, 2)]), "hard")
    assert turn.moves == [(2, 0)]


def test_hard_returns_within_budget() -> None:
    turn = play_turn(replay([(4, 4)]), "hard", time_budget_ms=400)
    assert turn.time_ms <= 400 * len(turn.moves) + 150


def test_placement_budget() -> None:
    assert placement_budget("easy", None) is None
    assert placement_budget("medium", 1500) == 1500
    assert placement_budget("hard", None) == agent.LIMITS["hard"][1]
    assert placement_budget("hard", 9500) == 2000
    assert placement_budget("hard", 800) == 800


def test_time_pressure() -> None:
    assert time_pressure(None) == 0
    assert time_pressure(120_000) == 0
    assert time_pressure(30_000) == pytest.approx(0.5)
    assert time_pressure(0) == 1
