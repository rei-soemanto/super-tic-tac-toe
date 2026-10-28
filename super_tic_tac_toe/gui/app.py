from pathlib import Path
from time import perf_counter

import pygame

from super_tic_tac_toe.engine.rules import X
from super_tic_tac_toe.engine.state import Placement
from super_tic_tac_toe.game import settings as settings_store
from super_tic_tac_toe.game.ai_runner import AiRunner, ProcessAiRunner
from super_tic_tac_toe.game.session import GameSession, Status
from super_tic_tac_toe.gui import marks
from super_tic_tac_toe.gui.game_screen import GameActions, GameScreen
from super_tic_tac_toe.gui.setup_screen import SetupScreen
from super_tic_tac_toe.gui.theme import LIGHT, palette
from super_tic_tac_toe.gui.widgets import Ui

TITLE = "Super Tic-Tac-Toe"
DEFAULT_SIZE = (1280, 820)
MIN_SIZE = (720, 640)
FPS = 60
WHEEL_STEP = 48


class App:
    def __init__(self, runner: AiRunner, settings_path: Path | None = None, size: tuple[int, int] = DEFAULT_SIZE):
        pygame.init()
        self.settings_path = settings_path
        settings = settings_store.load(settings_path)
        self.session = GameSession(settings)
        self.runner = runner
        self.ui = Ui()
        self.setup = SetupScreen(settings)
        self.game = GameScreen()
        self.window = pygame.Window(TITLE, size, resizable=True)
        self.window.minimum_size = MIN_SIZE
        self.window.set_icon(self._icon())
        self.running = True
        self.now = 0.0
        self.mouse = (-1, -1)
        self._cursor = pygame.SYSTEM_CURSOR_ARROW
        self._text_input = False
        pygame.key.stop_text_input()
        self.actions = GameActions(
            new_game=self.new_game,
            undo=lambda: self.session.undo(self.now),
            change_settings=self.change_settings,
            toggle_theme=self.toggle_theme,
            retry=self.session.retry,
            play=self.play,
        )

    @property
    def on_setup(self) -> bool:
        return self.session.status == Status.SETUP

    @property
    def theme(self) -> str:
        return self.setup.draft.theme if self.on_setup else self.session.settings.theme

    def start(self) -> None:
        if not self.setup.valid:
            return
        settings = self.setup.settings()
        settings_store.save(settings, self.settings_path)
        self.game.reset()
        self.session.start(settings, self.now)

    def new_game(self) -> None:
        self.game.reset()
        self.session.start(self.session.settings, self.now)

    def change_settings(self) -> None:
        self.session.change_settings()
        self.setup = SetupScreen(self.session.settings)

    def toggle_theme(self) -> None:
        theme = "light" if self.theme == "dark" else "dark"
        self.setup.with_theme(theme)
        self.session.update_settings(theme=theme)
        settings_store.save(self.session.settings, self.settings_path)

    def play(self, placement: Placement) -> None:
        self.session.play(*placement, self.now)

    def handle_event(self, event: pygame.event.Event, now: float) -> None:
        self.now = now
        if event.type in (pygame.QUIT, pygame.WINDOWCLOSE):
            self.running = False
        elif event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse = event.pos
            self._click(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            self._wheel(event.y)
        elif event.type == pygame.TEXTINPUT and self.on_setup:
            self.setup.type_text(event.text)
        elif event.type == pygame.KEYDOWN:
            self._key(event.key)

    def update(self, now: float) -> None:
        self.now = now
        self.session.tick(now)
        for outcome in self.runner.poll():
            self.session.ai_outcome(outcome, now)
        request = self.session.ai_request(now)
        if request:
            self.runner.submit(request)

    def render(self, now: float) -> None:
        surface = self.window.get_surface()
        colors = palette(self.theme)
        surface.fill(colors.paper)
        modal = not self.on_setup and self.game.dialog_open(self.session)
        self.ui.begin_frame(surface, colors, self.mouse, modal)
        if self.on_setup:
            self.setup.draw(self.ui, now, self.start, self.toggle_theme)
            wants_text = self.setup.input_focused
        else:
            self.game.draw(self.ui, self.session, now, self.theme == "dark", self.actions)
            wants_text = False
        if wants_text != self._text_input:
            self._text_input = wants_text
            (pygame.key.start_text_input if wants_text else pygame.key.stop_text_input)()
        self._update_cursor()

    def run(self) -> None:
        clock = pygame.time.Clock()
        try:
            while self.running:
                now = perf_counter()
                for event in pygame.event.get():
                    self.handle_event(event, now)
                self.update(now)
                self.render(now)
                self.window.flip()
                clock.tick(FPS)
        finally:
            self.runner.close()
            pygame.quit()

    def _click(self, pos: tuple[int, int]) -> None:
        if self.on_setup:
            self.setup.input_focused = False
        if self.ui.click(pos) or self.on_setup:
            return
        if not self.game.dialog_open(self.session):
            cell = self.game.board.cell_at(pos)
            if cell:
                self.play(cell)

    def _wheel(self, rows: int) -> None:
        height = self.window.size[1]
        if self.on_setup:
            self.setup.scroll_by(-rows * WHEEL_STEP, height)
        elif self.game.panel.history_rect.collidepoint(self.mouse):
            self.game.panel.scroll_history(-rows)
        else:
            self.game.scroll_by(-rows * WHEEL_STEP, height)

    def _key(self, key: int) -> None:
        if self.on_setup:
            if key == pygame.K_BACKSPACE:
                self.setup.backspace()
            elif key == pygame.K_ESCAPE:
                self.setup.input_focused = False
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start()
        elif self.game.dialog_open(self.session):
            if key == pygame.K_ESCAPE:
                self.game.dismiss_dialog(self.session)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.new_game()

    def _update_cursor(self) -> None:
        if self.on_setup and self.setup.input_rect.collidepoint(self.mouse):
            cursor = pygame.SYSTEM_CURSOR_IBEAM
        elif self.ui.over_clickable(self.mouse) or self.game.hover_cell(self.session, self.mouse):
            cursor = pygame.SYSTEM_CURSOR_HAND
        else:
            cursor = pygame.SYSTEM_CURSOR_ARROW
        if cursor != self._cursor:
            self._cursor = cursor
            try:
                pygame.mouse.set_cursor(cursor)
            except pygame.error:
                pass

    @staticmethod
    def _icon() -> pygame.Surface:
        icon = pygame.Surface((64, 64), pygame.SRCALPHA)
        icon.blit(marks.rounded((64, 64), 14, LIGHT.card), (0, 0))
        icon.blit(marks.mark(X, 64, LIGHT.x_ink, 0.12), (0, 0))
        return icon


def main() -> None:
    runner = ProcessAiRunner()
    runner.warm_up()
    App(runner).run()
