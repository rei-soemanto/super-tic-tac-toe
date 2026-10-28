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
from super_tic_tac_toe.gui.board_view import owner
from super_tic_tac_toe.gui.fonts import Face, measure, render
from super_tic_tac_toe.gui.widgets import Action, Ui

DIFFICULTY_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
FORCED_SCORE = 99_000
RING_SIZE = 72
PLAYER_CARD_H = 68
CARD_GAP = 12
HISTORY_ROWS = 8
HISTORY_ROW_H = 22
WIDE_PANEL = 380


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


def player_tags(session: GameSession) -> tuple[str, str]:
    """Status lines under the You and AI cards."""
    status = session.status
    winner = session.end.winner if status == Status.GAME_OVER and session.end else None
    you = "Winner" if winner == HUMAN else "Bonus move" if session.in_bonus else "To move" if status == Status.HUMAN_TURN else "Plays X"
    ai = DIFFICULTY_LABELS[session.settings.difficulty]
    if winner is not None and winner != HUMAN:
        ai = "Winner"
    elif status == Status.AI_THINKING:
        ai = "Thinking…"
    elif status == Status.ANIMATING_AI:
        ai = "Moving"
    return you, ai


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
        top = y
        y = self._players(ui, x, y, width, session) + CARD_GAP
        y = ui.card_section(x, y, width, lambda cy, w: self._turn(ui, x + 18, cy, w, session, on_new_game, on_undo, on_settings)) + CARD_GAP
        y = ui.card_section(x, y, width, lambda cy, w: self._search(ui, x + 18, cy, w, session)) + CARD_GAP
        y = ui.card_section(x, y, width, lambda cy, w: self._history(ui, x + 18, cy, w, session))
        return y - top

    def _players(self, ui: Ui, x: int, y: int, width: int, session: GameSession) -> int:
        p = ui.p
        status = session.status
        won = grids_won(session.state)
        tags = player_tags(session)
        card_w = (width - CARD_GAP) // 2
        for i, (player, name, active) in enumerate(
            ((X, "You", status == Status.HUMAN_TURN), (O, "AI", status in (Status.AI_THINKING, Status.ANIMATING_AI)))
        ):
            rect = pygame.Rect(x + i * (card_w + CARD_GAP), y, card_w, PLAYER_CARD_H)
            color = p.player(player)
            if active:
                ui.rounded(rect, 14, p.card, color, 2)
            else:
                ui.card(rect)
            mark = marks.mark(player, 36, color, 0.13)
            ui.blit(mark, (rect.x + 14, rect.centery - 18))
            tx = rect.x + 14 + 36 + 12
            ui.text(name, (tx, rect.y + 15), Face.BOLD, 15)
            ui.text(tags[i], (tx, rect.y + 36), Face.REGULAR, 12, p.muted)
            count = render(str(won[i]), Face.DISPLAY, 26, color)
            label_w = measure("grids won", Face.REGULAR, 11)[0]
            right = rect.right - 14
            ui.blit(count, (right - count.get_width(), rect.y + 10))
            ui.text("grids won", (right - label_w, rect.y + 44), Face.REGULAR, 11, p.muted)
        return y + PLAYER_CARD_H

    def _turn(
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
        p = ui.p
        y = ui.text(turn_text(session), (x, y), Face.HEADING, 22, wrap=width).bottom + 4
        summary = f"{mode_summary(session.settings)}. {DIFFICULTY_LABELS[session.settings.difficulty]} AI."
        y = ui.text(summary, (x, y), Face.REGULAR, 14, p.muted, wrap=width).bottom + 16
        clock_bottom = self._clock(ui, x, y, width, session)
        if clock_bottom is not None:
            y = clock_bottom + 16

        bx = x
        rect = None
        for label, action, primary, shown, enabled in (
            ("New game", on_new_game, True, True, True),
            ("Undo", on_undo, False, session.settings.mode == "free", session.can_undo()),
            ("Settings", on_settings, False, True, True),
        ):
            if shown:
                rect = ui.button(label, (bx, y), action, primary=primary, enabled=enabled)
                bx = rect.right + 8
        return rect.bottom

    def _clock(self, ui: Ui, x: int, y: int, width: int, session: GameSession) -> int | None:
        """Draws the mode's clock; returns its bottom, or None when there is nothing to show."""
        p = ui.p
        settings = session.settings
        now = session.clock_now

        if settings.mode == "competitive":
            limit = session.placement_limit
            status = session.status
            player = X
            if status == Status.AI_THINKING:
                left, player = remaining(limit, session.ai_requested_at, now), O
            elif status == Status.HUMAN_TURN:
                left = remaining(limit, session.placement_started_at, now)
            elif status == Status.GAME_OVER:
                timed_out = session.end.timed_out if session.end else None
                if timed_out not in (Timeout.HUMAN, Timeout.AI):
                    return None
                left, player = 0.0, O if timed_out == Timeout.AI else X
            else:
                left = limit
            low = left <= COMPETITIVE_WARNING_S
            color = p.danger if low else p.player(player)
            ui.blit(marks.ring(RING_SIZE, p.line, color, left / limit), (x, y))
            whole = math.ceil(left)
            digits = render(str(whole), Face.DISPLAY, 26, p.danger if low else p.ink)
            ui.blit(digits, digits.get_rect(center=(x + RING_SIZE // 2, y + RING_SIZE // 2)).topleft)
            seconds = "second" if whole == 1 else "seconds"
            ty = y + RING_SIZE // 2 - 20
            ui.text("You" if player == X else "AI", (x + RING_SIZE + 16, ty), Face.SEMIBOLD, 14, color)
            ui.text(f"{seconds} left for this placement", (x + RING_SIZE + 16, ty + 20), Face.REGULAR, 14, p.muted)
            return y + RING_SIZE

        if settings.mode == "time_based":
            left = remaining(session.game_limit, session.game_started_at, now)
            low = left < TIME_BASED_WARNING_S
            ui.text("Game time left", (x, y), Face.REGULAR, 14, p.muted)
            bottom = ui.text(format_clock(left), (x, y + 20), Face.DISPLAY, 44, p.danger if low else p.ink).bottom
            if low:
                warning = f"Under {TIME_BASED_WARNING_S} s"
                ww, wh = measure(warning, Face.SEMIBOLD, 13)
                ui.text(warning, (x + width - ww, bottom - wh - 6), Face.SEMIBOLD, 13, p.danger)
            return bottom

        ui.text("Elapsed", (x, y), Face.REGULAR, 14, p.muted)
        return ui.text(format_clock(now - session.game_started_at), (x, y + 20), Face.DISPLAY, 44).bottom

    def _search(self, ui: Ui, x: int, y: int, width: int, session: GameSession) -> int:
        p = ui.p
        y = ui.heading("Last AI search", (x, y)).bottom + 10
        stats = session.stats
        if stats is None:
            return ui.text("Shown after the AI moves.", (x, y), Face.REGULAR, 14, p.muted, wrap=width).bottom
        items = (
            ("Depth", str(stats.depth_reached)),
            ("Positions", f"{stats.nodes:,}"),
            ("Time", f"{round(stats.time_ms)} ms"),
            ("Evaluation", score_text(stats.score)),
        )
        columns = 4 if width >= WIDE_PANEL - 36 else 2
        col_w = (width - 10 * (columns - 1)) // columns
        bottom = y
        for i, (label, value) in enumerate(items):
            cx = x + (i % columns) * (col_w + 10)
            cy = y + (i // columns) * 52
            ui.text(label, (cx, cy), Face.REGULAR, 12, p.muted)
            bottom = max(bottom, ui.text(value, (cx, cy + 18), Face.BOLD, 16, wrap=col_w).bottom)
        return bottom

    def _history(self, ui: Ui, x: int, y: int, width: int, session: GameSession) -> int:
        p = ui.p
        y = ui.heading("Moves", (x, y)).bottom + 10
        placements = session.state.placements()
        if not placements:
            return ui.text("You play X and move first, anywhere.", (x, y), Face.REGULAR, 14, p.muted, wrap=width).bottom

        columns = 4 if width >= WIDE_PANEL - 36 else 3
        rows = (len(placements) + columns - 1) // columns
        max_scroll = max(0, rows - HISTORY_ROWS)
        if self._follow or self.history_scroll > max_scroll:
            self.history_scroll = max_scroll
        if self.history_scroll >= max_scroll:
            self._follow = True
        visible = min(rows, HISTORY_ROWS)
        self.history_rect = pygame.Rect(x, y, width, visible * HISTORY_ROW_H)

        state = session.state
        column_w = width // columns
        for row in range(self.history_scroll, self.history_scroll + visible):
            for column in range(columns):
                i = row * columns + column
                if i >= len(placements):
                    break
                grid, cell = placements[i]
                player = owner(state, grid, cell)
                cx = x + column * column_w
                cy = y + (row - self.history_scroll) * HISTORY_ROW_H
                number = str(i + 1)
                nw = measure(number, Face.REGULAR, 14)[0]
                ui.text(number, (cx + 22 - nw, cy), Face.REGULAR, 14, p.muted)
                if player is not None:
                    ui.text("X" if player == X else "O", (cx + 30, cy), Face.BOLD, 14, p.player(player))
                ui.text(f"{grid + 1}.{cell + 1}", (cx + 46, cy), Face.REGULAR, 14)
        y += visible * HISTORY_ROW_H + 8
        if max_scroll:
            ui.text("Scroll to see earlier moves.", (x, y), Face.REGULAR, 12, p.muted)
            y += 18
        return ui.text("Grid.cell, each numbered 1 to 9 from the top left.", (x, y), Face.REGULAR, 12, p.muted, wrap=width).bottom
