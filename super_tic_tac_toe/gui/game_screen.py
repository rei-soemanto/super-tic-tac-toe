from collections.abc import Callable
from dataclasses import dataclass

import pygame

from super_tic_tac_toe.engine.state import Placement
from super_tic_tac_toe.game.clock import grids_won
from super_tic_tac_toe.game.session import GameEnd, GameSession, Status
from super_tic_tac_toe.gui.board_view import BoardView
from super_tic_tac_toe.gui.dialog import draw_game_over
from super_tic_tac_toe.gui.fonts import Face, render
from super_tic_tac_toe.gui.panel import Panel
from super_tic_tac_toe.gui.widgets import Action, Ui

MAX_WIDTH = 1152
PANEL_WIDTH = 320
WIDE_MIN = 1040
TOP = 76
SLOT_HEIGHT = 56
BONUS_TEXT = "Bonus move! Place anywhere open."


@dataclass
class GameActions:
    new_game: Action
    undo: Action
    change_settings: Action
    toggle_theme: Action
    retry: Action
    play: Callable[[Placement], None]


class GameScreen:
    def __init__(self) -> None:
        self.board = BoardView()
        self.panel = Panel()
        self.scroll = 0
        self.content_height = 0
        self.dismissed: GameEnd | None = None

    def reset(self) -> None:
        self.board.reset_animation()
        self.panel = Panel()
        self.scroll = 0
        self.dismissed = None

    def dialog_open(self, session: GameSession) -> bool:
        return session.status == Status.GAME_OVER and session.end is not None and session.end is not self.dismissed

    def dismiss_dialog(self, session: GameSession) -> None:
        self.dismissed = session.end

    def scroll_by(self, pixels: int, view_height: int) -> None:
        self.scroll = max(0, min(self.scroll + pixels, max(0, self.content_height - view_height)))

    def hover_cell(self, session: GameSession, mouse: tuple[int, int]) -> Placement | None:
        if session.status != Status.HUMAN_TURN or self.dialog_open(session):
            return None
        return self.board.cell_at(mouse)

    def draw(self, ui: Ui, session: GameSession, now: float, theme_dark: bool, actions: GameActions) -> None:
        surface = ui.surface
        p = ui.p
        width, height = surface.get_size()
        self.scroll_by(0, height)
        pad = 32 if width >= 900 else 24
        cw = min(MAX_WIDTH, width - 2 * pad)
        x0 = (width - cw) // 2
        top = TOP - self.scroll

        ui.text("Super Tic-Tac-Toe", (x0, 24 - self.scroll), Face.DISPLAY, 24)
        ui.toggle("Dark theme", (x0 + cw, 26 - self.scroll), theme_dark, actions.toggle_theme)

        wide = width >= WIDE_MIN
        board_top = top + SLOT_HEIGHT + 12
        if wide:
            column = cw - PANEL_WIDTH - 48
            size = max(240, min(column, height - TOP - SLOT_HEIGHT - 12 - 24))
            board_x = x0 + (column - size) // 2
            panel_x, panel_y, panel_w = x0 + column + 48, top, PANEL_WIDTH
        else:
            size = max(240, min(cw, height - TOP - SLOT_HEIGHT - 12 - 24))
            board_x = x0 + (cw - size) // 2
            panel_x, panel_y, panel_w = board_x, board_top + size + 32, size

        self._slot(ui, session, board_x, top, size, actions.retry)
        self.board.layout(pygame.Rect(board_x, board_top, size, size))
        self.board.track(session.state, now)
        self.board.draw(
            surface,
            p,
            session.state,
            session.status == Status.HUMAN_TURN,
            now,
            self.hover_cell(session, ui.mouse),
            session.flash_at,
        )

        panel_h = self.panel.draw(
            ui, panel_x, panel_y, panel_w, session, actions.new_game, actions.undo, actions.change_settings
        )
        bottom = max(board_top + size, panel_y + panel_h) + 32
        self.content_height = bottom + self.scroll

        if self.dialog_open(session):
            draw_game_over(
                ui,
                session.end,
                grids_won(session.state),
                session.can_undo(),
                actions.new_game,
                actions.change_settings,
                actions.undo,
                lambda: self.dismiss_dialog(session),
            )

    @staticmethod
    def _slot(ui: Ui, session: GameSession, x: int, y: int, width: int, retry: Action) -> None:
        """The space above the board: an AI error, the bonus banner, or nothing."""
        p = ui.p
        if session.error:
            ui.banner(session.error, x, y, width, "Retry", retry)
        elif session.in_bonus:
            rect = pygame.Rect(x, y + 6, width, SLOT_HEIGHT - 12)
            ui.fill(rect, p.ink)
            text = render(BONUS_TEXT, Face.SEMIBOLD, 16, p.paper)
            ui.surface.blit(text, text.get_rect(center=rect.center))
