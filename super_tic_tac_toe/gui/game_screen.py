from collections.abc import Callable
from dataclasses import dataclass

import pygame

from super_tic_tac_toe.engine.state import Placement
from super_tic_tac_toe.game.clock import grids_won
from super_tic_tac_toe.game.session import GameEnd, GameSession, Status
from super_tic_tac_toe.gui import marks
from super_tic_tac_toe.gui.board_view import BoardView
from super_tic_tac_toe.gui.dialog import draw_game_over
from super_tic_tac_toe.gui.fonts import Face, measure, render
from super_tic_tac_toe.gui.panel import Panel
from super_tic_tac_toe.gui.widgets import Action, Ui

MAX_WIDTH = 1152  # content width cap
PANEL_WIDTH = 420
PANEL_GAP = 56
WIDE_MIN = 1040  # side-by-side layout from this width
TOP = 76  # space for the header row
SLOT_HEIGHT = 56  # banner/hint area above the board
BONUS_TEXT = "Bonus move! Place anywhere open."


def board_hint(session: GameSession) -> str:  # explains why those grids are highlighted
    """The line above the board on a normal human turn: why the highlighted grids are open."""
    if session.status != Status.HUMAN_TURN or session.in_bonus:
        return ""
    state = session.state
    last = session.last_move
    if last is None:
        return "You move first, anywhere."
    grid, cell = last
    if state.active_grid is not None:
        return f"AI played {grid + 1}.{cell + 1}, so you play in grid {state.active_grid + 1}."
    return f"AI played {grid + 1}.{cell + 1}. Grid {cell + 1} is closed, so play in any open grid."


@dataclass
class GameActions:  # button callbacks supplied by App
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
        self.scroll = 0  # vertical page scroll for small windows
        self.content_height = 0
        self.dismissed: GameEnd | None = None  # end state whose dialog was closed via View board

    def reset(self) -> None:
        self.board.reset_animation()
        self.panel = Panel()
        self.scroll = 0
        self.dismissed = None

    def dialog_open(self, session: GameSession) -> bool:  # game-over dialog visible?
        return session.status == Status.GAME_OVER and session.end is not None and session.end is not self.dismissed

    def dismiss_dialog(self, session: GameSession) -> None:
        self.dismissed = session.end

    def scroll_by(self, pixels: int, view_height: int) -> None:
        self.scroll = max(0, min(self.scroll + pixels, max(0, self.content_height - view_height)))

    def hover_cell(self, session: GameSession, mouse: tuple[int, int]) -> Placement | None:  # no hover when it's not the human's turn
        if session.status != Status.HUMAN_TURN or self.dialog_open(session):
            return None
        return self.board.cell_at(mouse)

    def draw(self, ui: Ui, session: GameSession, now: float, theme_dark: bool, actions: GameActions) -> None:
        surface = ui.surface
        p = ui.p
        width, height = surface.get_size()
        self.scroll_by(0, height)  # re-clamp scroll after a resize
        pad = 32 if width >= 900 else 24
        cw = min(MAX_WIDTH, width - 2 * pad)
        x0 = (width - cw) // 2
        top = TOP - self.scroll

        logo_right = ui.logo((x0, 26 - self.scroll), 24)
        ui.text("Super Tic-Tac-Toe", (logo_right + 12, 24 - self.scroll), Face.DISPLAY, 22)
        ui.toggle("Dark theme", (x0 + cw, 26 - self.scroll), theme_dark, actions.toggle_theme)

        wide = width >= WIDE_MIN  # wide: panel beside board; narrow: panel below
        board_top = top + SLOT_HEIGHT + 8
        if wide:
            column = cw - PANEL_WIDTH - PANEL_GAP
            size = max(240, min(column, height - TOP - SLOT_HEIGHT - 8 - 24))
            board_x = x0 + (column - size) // 2
            panel_x, panel_y, panel_w = x0 + column + PANEL_GAP, board_top, PANEL_WIDTH
            # column_x = x0 + PANEL_WIDTH + PANEL_GAP  # board column now starts after the panel
            # board_x = column_x + (column - size) // 2  # board centered in its column
            # panel_x, panel_y, panel_w = x0, board_top, PANEL_WIDTH
        else:
            size = max(240, min(cw, height - TOP - SLOT_HEIGHT - 8 - 24))
            board_x = x0 + (cw - size) // 2
            panel_x, panel_y, panel_w = board_x, board_top + size + 32, size

        self._slot(ui, session, board_x, top, size, actions.retry)  # error / bonus / hint line
        self.board.layout(pygame.Rect(board_x, board_top, size, size))  # compute grid and cell rects
        self.board.track(session.state, now)  # detect new moves for animations
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
        self.content_height = bottom + self.scroll  # total height, for scroll limits

        if self.dialog_open(session):  # game-over dialog drawn last, on top
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
        """The space above the board: an AI error, the bonus banner, or a hint about where to play."""
        p = ui.p
        if session.error:  # AI failure: show retry banner
            ui.banner(session.error, x, y, width, "Retry", retry)
        elif session.in_bonus:  # bonus move banner
            rect = pygame.Rect(x, y + 6, width, SLOT_HEIGHT - 12)
            ui.rounded(rect, 10, p.x_ink)
            text = render(BONUS_TEXT, Face.SEMIBOLD, 16, p.on_ink)
            star = marks.icon("star", 18, p.on_ink)
            left = rect.centerx - (text.get_width() + 28) // 2
            ui.blit(star, (left, rect.centery - 9))
            ui.blit(text, (left + 28, rect.centery - text.get_height() // 2))
        else:
            hint = board_hint(session)
            if hint:
                th = measure(hint, Face.REGULAR, 14)[1]
                ui.text(hint, (x, y + SLOT_HEIGHT - th - 12), Face.REGULAR, 14, p.muted, wrap=width)
