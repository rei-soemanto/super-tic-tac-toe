import math

import pygame

from super_tic_tac_toe.engine.rules import O, X
from super_tic_tac_toe.game.clock import (
    COMPETITIVE_WARNING_S,
    TIME_BASED_WARNING_S,
    format_clock,
    grids_won,
    remaining,
)
from super_tic_tac_toe.game.session import HUMAN, GameSession, Status, Timeout
from super_tic_tac_toe.game.settings import Settings
from super_tic_tac_toe.gui import marks
from super_tic_tac_toe.gui.fonts import Face, measure, render
from super_tic_tac_toe.gui.widgets import Action, Ui

DIFFICULTY_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
FORCED_SCORE = 99_000
RING_SIZE = 96
HISTORY_ROWS = 8
HISTORY_ROW_H = 22


def mode_summary(settings: Settings) -> str:
    if settings.mode == "competitive":
        return f"Competitive, {settings.competitive_seconds} s per placement"
    if settings.mode == "time_based":
        return f"Time-based, {settings.time_based_minutes} min game"
    return "Free"


def turn_text(session: GameSession) -> str:
    state = session.state
    match session.status:
        case Status.HUMAN_TURN:
            if session.in_bonus:
                return "Your bonus move"
            if state.active_grid is None:
                return "Your move, any open grid"
            return f"Your move in grid {state.active_grid + 1}"
        case Status.AI_THINKING:
            return "AI is thinking…"
        case Status.ANIMATING_AI:
            return "AI is moving"
        case Status.GAME_OVER:
            end = session.end
            if end is None or end.winner is None:
                return "Game over, draw"
            return "Game over, you won" if end.winner == HUMAN else "Game over, AI won"
    return ""


def score_text(score: int) -> str:
    if score > FORCED_SCORE:
        return "Forced win for AI"
    if score < -FORCED_SCORE:
        return "Forced win for you"
    return f"+{score}" if score > 0 else str(score)


class Panel:
    def __init__(self) -> None:
        self.history_scroll = 0
        self.history_rect = pygame.Rect(0, 0, 0, 0)
        self._follow = True

    def scroll_history(self, rows: int) -> None:
        self.history_scroll = max(0, self.history_scroll + rows)
        self._follow = False

    def draw(
        self,
        ui: Ui,
        x: int,
        y: int,
        width: int,
        session: GameSession,
        on_new_game: Action,
        on_undo: Action,
        on_settings: Action,
    ) -> int:
        """Draws the panel from (x, y); returns its height."""
        p = ui.p
        top = y
        y = ui.text(turn_text(session), (x, y), Face.HEADING, 24, wrap=width).bottom + 4
        summary = f"{mode_summary(session.settings)}. {DIFFICULTY_LABELS[session.settings.difficulty]} AI."
        y = ui.text(summary, (x, y), Face.REGULAR, 14, p.muted, wrap=width).bottom + 24

        y = self._clock(ui, x, y, width, session) + 24

        bx = x
        for label, action, primary, shown, enabled in (
            ("New game", on_new_game, True, True, True),
            ("Undo", on_undo, False, session.settings.mode == "free", session.can_undo()),
            ("Settings", on_settings, False, True, True),
        ):
            if shown:
                rect = ui.button(label, (bx, y), action, primary=primary, enabled=enabled)
                bx = rect.right + 8
        y = rect.bottom + 24

        ui.rule(x, y, width)
        y = ui.text("Last AI search", (x, y + 16), Face.SEMIBOLD, 16).bottom + 8
        stats = session.stats
        if stats is None:
            y = ui.text("Shown after the AI moves.", (x, y), Face.REGULAR, 14, p.muted).bottom
        else:
            depth = f"{stats.depth_reached} placement{'' if stats.depth_reached == 1 else 's'}"
            for label, value in (
                ("Depth reached", depth),
                ("Positions searched", f"{stats.nodes:,}"),
                ("Time", f"{round(stats.time_ms)} ms"),
                ("Evaluation", score_text(stats.score)),
            ):
                ui.text(label, (x, y), Face.REGULAR, 14, p.muted)
                value_w = measure(value, Face.REGULAR, 14)[0]
                y = ui.text(value, (x + width - value_w, y), Face.REGULAR, 14).bottom + 4
        y += 20

        ui.rule(x, y, width)
        y = ui.text("Moves", (x, y + 16), Face.SEMIBOLD, 16).bottom + 8
        y = self._history(ui, x, y, width, session)
        return y - top

    def _clock(self, ui: Ui, x: int, y: int, width: int, session: GameSession) -> int:
        p = ui.p
        settings = session.settings
        now = session.clock_now

        if settings.mode == "competitive":
            limit = session.placement_limit
            status = session.status
            owner = "You"
            if status == Status.AI_THINKING:
                left, owner = remaining(limit, session.ai_requested_at, now), "AI"
            elif status == Status.HUMAN_TURN:
                left = remaining(limit, session.placement_started_at, now)
            elif status == Status.GAME_OVER:
                timed_out = session.end.timed_out if session.end else None
                if timed_out not in (Timeout.HUMAN, Timeout.AI):
                    return y - 24
                left, owner = 0.0, "AI" if timed_out == Timeout.AI else "You"
            else:
                left = limit
            color = p.danger if left <= COMPETITIVE_WARNING_S else p.ink
            ui.surface.blit(marks.ring(RING_SIZE, p.rule, color, left / limit), (x, y))
            whole = math.ceil(left)
            digits = render(str(whole), Face.DISPLAY, 30, color)
            ui.surface.blit(digits, digits.get_rect(center=(x + RING_SIZE // 2, y + RING_SIZE // 2)))
            seconds = "second" if whole == 1 else "seconds"
            ty = y + RING_SIZE // 2 - 20
            ui.text(owner, (x + RING_SIZE + 16, ty), Face.SEMIBOLD, 14)
            ui.text(f"{seconds} left for this placement", (x + RING_SIZE + 16, ty + 20), Face.REGULAR, 14, p.muted)
            return y + RING_SIZE

        if settings.mode == "time_based":
            left = remaining(session.game_limit, session.game_started_at, now)
            ui.text("Game time left", (x, y), Face.REGULAR, 14, p.muted)
            color = p.danger if left < TIME_BASED_WARNING_S else p.ink
            bottom = ui.text(format_clock(left), (x, y + 20), Face.DISPLAY, 48, color).bottom
            won_x, won_o = grids_won(session.state)
            for i, (label, count) in enumerate((("You", won_x), ("AI", won_o))):
                column = x + width - 48 * (2 - i)
                ui.text(label, (column, y + 14), Face.REGULAR, 14, p.muted)
                ui.text(str(count), (column, y + 34), Face.BOLD, 24)
            return bottom

        ui.text("Elapsed", (x, y), Face.REGULAR, 14, p.muted)
        return ui.text(format_clock(now - session.game_started_at), (x, y + 20), Face.DISPLAY, 48).bottom

    def _history(self, ui: Ui, x: int, y: int, width: int, session: GameSession) -> int:
        p = ui.p
        placements = session.state.placements()
        if not placements:
            return ui.text("You play X and move first, anywhere.", (x, y), Face.REGULAR, 14, p.muted, wrap=width).bottom

        rows = (len(placements) + 2) // 3
        max_scroll = max(0, rows - HISTORY_ROWS)
        if self._follow or self.history_scroll > max_scroll:
            self.history_scroll = max_scroll
        if self.history_scroll >= max_scroll:
            self._follow = True
        visible = min(rows, HISTORY_ROWS)
        self.history_rect = pygame.Rect(x, y, width, visible * HISTORY_ROW_H)

        state = session.state
        column_w = width // 3
        for row in range(self.history_scroll, self.history_scroll + visible):
            for column in range(3):
                i = row * 3 + column
                if i >= len(placements):
                    break
                grid, cell = placements[i]
                player = "X" if state.bits[X][grid] >> cell & 1 else "O" if state.bits[O][grid] >> cell & 1 else ""
                cx = x + column * column_w
                cy = y + (row - self.history_scroll) * HISTORY_ROW_H
                number = str(i + 1)
                nw = measure(number, Face.REGULAR, 14)[0]
                ui.text(number, (cx + 22 - nw, cy), Face.REGULAR, 14, p.muted)
                ui.text(player, (cx + 30, cy), Face.BOLD, 14)
                ui.text(f"{grid + 1}.{cell + 1}", (cx + 46, cy), Face.REGULAR, 14)
        y += visible * HISTORY_ROW_H + 8
        if max_scroll:
            ui.text("Scroll to see earlier moves.", (x, y), Face.REGULAR, 12, p.muted)
            y += 18
        return ui.text("Grid.cell, each numbered 1 to 9 from the top left.", (x, y), Face.REGULAR, 12, p.muted, wrap=width).bottom

