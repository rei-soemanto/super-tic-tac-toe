import time
from pathlib import Path

import pygame
import pytest

from super_tic_tac_toe.game import settings as settings_store
from super_tic_tac_toe.game.ai_runner import AiRunner, ProcessAiRunner, SyncAiRunner
from super_tic_tac_toe.game.session import Status
from super_tic_tac_toe.gui.app import App
from super_tic_tac_toe.gui.theme import DARK, LIGHT


class Driver:
    def __init__(self, runner: AiRunner, settings_path: Path) -> None:
        self.app = App(runner, settings_path)
        self.now = 0.0
        self.frame()

    def frame(self, advance: float = 0.0) -> None:
        self.now += advance
        self.app.update(self.now)
        self.app.render(self.now)

    def event(self, kind: int, **attrs: object) -> None:
        self.app.handle_event(pygame.event.Event(kind, **attrs), self.now)
        self.frame()

    def click_at(self, pos: tuple[int, int]) -> None:
        self.event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)

    def press(self, label: str) -> None:
        rect = self.app.ui.find(label)
        assert rect is not None, f"no clickable '{label}' on screen"
        self.click_at(rect.center)

    def has(self, label: str) -> bool:
        return self.app.ui.find(label) is not None

    def pixel(self, pos: tuple[int, int]) -> tuple[int, int, int]:
        return tuple(self.app.window.get_surface().get_at(pos))[:3]

    def start(self, mode: str, difficulty: str = "Easy") -> None:
        self.press(mode)
        self.press(difficulty)
        self.press("Start game")


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


@pytest.fixture
def driver(settings_path: Path):
    driver = Driver(SyncAiRunner(), settings_path)
    yield driver
    driver.app.window.destroy()


@pytest.mark.parametrize(
    ("label", "mode"), [("Competitive", "competitive"), ("Time-based", "time_based"), ("Free", "free")]
)
def test_setup_starts_each_mode_and_remembers_it(driver: Driver, settings_path: Path, label: str, mode: str) -> None:
    driver.start(label)
    assert driver.app.session.status == Status.HUMAN_TURN
    assert driver.app.session.settings.mode == mode
    assert settings_store.load(settings_path).mode == mode


@pytest.mark.parametrize(("label", "shown"), [("Competitive", False), ("Time-based", False), ("Free", True)])
def test_undo_only_in_free_mode(driver: Driver, label: str, shown: bool) -> None:
    driver.start(label)
    board = driver.app.game.board
    driver.click_at(board.cell_rects[4][4].center)
    driver.frame(1.0)
    assert driver.has("Undo") is shown


def test_clicking_a_cell_plays_and_the_ai_replies(driver: Driver) -> None:
    driver.start("Free")
    driver.click_at(driver.app.game.board.cell_rects[4][2].center)
    driver.frame(0.5)
    session = driver.app.session
    assert session.state.placements()[0] == (4, 2)
    assert len(session.state.history) >= 2
    assert session.status == Status.HUMAN_TURN


def test_theme_toggle_switches_palette_and_is_saved(driver: Driver, settings_path: Path) -> None:
    assert driver.pixel((2, 2)) == LIGHT.paper
    driver.press("Dark theme")
    assert driver.pixel((2, 2)) == DARK.paper
    assert settings_store.load(settings_path).theme == "dark"


def test_invalid_custom_time_disables_start(driver: Driver) -> None:
    driver.press("Custom")
    driver.event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)
    driver.event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)
    driver.event(pygame.TEXTINPUT, text="999")
    assert not driver.has("Start game")
    driver.event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)
    assert driver.has("Start game")
    driver.press("Start game")
    assert driver.app.session.settings.competitive_seconds == 99


def test_game_over_dialog_keys(driver: Driver) -> None:
    driver.start("Competitive")
    driver.frame(10.5)
    assert driver.app.session.status == Status.GAME_OVER
    assert driver.has("Play again")
    driver.event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    assert not driver.has("Play again")
    assert driver.has("New game")
    driver.press("New game")
    assert driver.app.session.status == Status.HUMAN_TURN


def test_full_free_game_against_easy_with_the_process_runner(settings_path: Path) -> None:
    driver = Driver(ProcessAiRunner(), settings_path)
    try:
        driver.start("Free")
        deadline = time.perf_counter() + 60
        while driver.app.session.status != Status.GAME_OVER:
            assert time.perf_counter() < deadline, "game did not finish"
            session = driver.app.session
            if session.status == Status.HUMAN_TURN:
                grid, cell = session.state.legal_moves()[0]
                driver.click_at(driver.app.game.board.cell_rects[grid][cell].center)
            time.sleep(0.02)
            driver.frame(0.05)
        assert driver.has("Play again")
        assert driver.has("Undo")
    finally:
        driver.app.runner.close()
        driver.app.window.destroy()
