import json
from pathlib import Path

from super_tic_tac_toe.engine.rules import O, X
from super_tic_tac_toe.engine.state import GameState, replay
from super_tic_tac_toe.game import settings as settings_module
from super_tic_tac_toe.game.clock import format_clock, grids_won, remaining, timeout_winner
from super_tic_tac_toe.game.settings import DEFAULTS, Settings
from super_tic_tac_toe.game.time_budget import empty_cells_in_open_grids, time_budget_ms
from tests.helpers import BONUS_SEQ


class TestClock:
    def test_formats_rounding_up_to_the_second(self) -> None:
        assert format_clock(600) == "10:00"
        assert format_clock(59.001) == "1:00"
        assert format_clock(0.001) == "0:01"
        assert format_clock(-5) == "0:00"

    def test_remaining_from_timestamps(self) -> None:
        assert remaining(10, 1, 4) == 7
        assert remaining(10, 1, 20) == 0

    def test_grids_won_and_timeout_winner(self) -> None:
        state = replay(BONUS_SEQ)
        assert grids_won(state) == (1, 0)
        assert timeout_winner(state) == X
        assert timeout_winner(GameState()) is None
        state.big[O] = 0b11
        assert timeout_winner(state) == O


class TestTimeBudget:
    def test_free_mode_uses_the_difficulty_limit(self) -> None:
        assert time_budget_ms(Settings(mode="free", difficulty="easy"), GameState()) is None
        assert time_budget_ms(Settings(mode="free", difficulty="hard"), GameState()) == 2000

    def test_competitive_keeps_a_half_second_margin(self) -> None:
        state = GameState()
        assert time_budget_ms(Settings(competitive_seconds=5, difficulty="medium"), state) == 4500
        assert time_budget_ms(Settings(competitive_seconds=5, difficulty="hard"), state) == 2000
        assert time_budget_ms(Settings(competitive_seconds=2, difficulty="hard"), state) == 1500

    def test_time_based_divides_by_moves_left(self) -> None:
        state = GameState()
        assert empty_cells_in_open_grids(state) == 81
        assert time_budget_ms(Settings(mode="time_based", difficulty="medium"), state, 81_000) == 2000
        assert time_budget_ms(Settings(mode="time_based", difficulty="hard"), state, 600_000) == 2000

    def test_time_based_assumes_at_least_ten_moves_left(self) -> None:
        state = GameState()
        state.closed = 0b011111111
        assert empty_cells_in_open_grids(state) == 9
        assert time_budget_ms(Settings(mode="time_based"), state, 5000) == 500

    def test_never_below_one_millisecond(self) -> None:
        assert time_budget_ms(Settings(mode="time_based"), GameState(), 0) == 1


class TestSettings:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "settings.json"
        saved = Settings(mode="free", competitive_seconds=30, time_based_minutes=3, difficulty="hard", theme="dark")
        settings_module.save(saved, path)
        assert settings_module.load(path) == saved

    def test_missing_file_gives_defaults(self, tmp_path: Path) -> None:
        assert settings_module.load(tmp_path / "absent.json") == DEFAULTS

    def test_corrupt_file_gives_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("{not json", encoding="utf-8")
        assert settings_module.load(path) == DEFAULTS

    def test_invalid_fields_fall_back_individually(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"mode": "free", "competitive_seconds": 999, "difficulty": "impossible", "theme": "dark"}),
            encoding="utf-8",
        )
        loaded = settings_module.load(path)
        assert loaded == Settings(mode="free", theme="dark")
