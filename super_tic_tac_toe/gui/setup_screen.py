from dataclasses import replace

import pygame

from super_tic_tac_toe.engine.rules import O, X
from super_tic_tac_toe.game.settings import (
    COMPETITIVE_PRESETS,
    COMPETITIVE_RANGE,
    TIME_BASED_PRESETS,
    TIME_BASED_RANGE,
    Settings,
)
from super_tic_tac_toe.gui import marks
from super_tic_tac_toe.gui.fonts import Face, measure, render
from super_tic_tac_toe.gui.widgets import Action, Ui, option_height

MODES = (
    ("competitive", "Competitive", "Each placement has its own clock. Run out and you lose.", "stopwatch"),
    ("time_based", "Time-based", "One clock for the whole game. When it runs out, most small grids won wins.", "hourglass"),
    ("free", "Free", "No clock. Undo your turn whenever you like.", "infinity"),
)

DIFFICULTIES = (
    ("easy", "Easy", "Looks 2 placements ahead", 2),
    ("medium", "Medium", "Looks 4 placements ahead", 4),
    ("hard", "Hard", "Searches as deep as it can in 2 seconds", 6),
)

TIME_OPTIONS = {
    "competitive": ("Time per placement", "s", COMPETITIVE_PRESETS, COMPETITIVE_RANGE, "competitive_seconds"),
    "time_based": ("Game length", "min", TIME_BASED_PRESETS, TIME_BASED_RANGE, "time_based_minutes"),
}

RULES = (
    "You are X and move first, anywhere. The AI is O.",
    "The cell you play in decides which small grid your opponent plays in next.",
    "Win a small grid and you immediately place one extra mark in any open small grid. "
    "That bonus never earns another bonus.",
    "Sent to a grid that is won or full? Play in any open grid.",
    "Win three small grids in a row to win the game.",
)

INTRO = (
    "Nine boards inside one. Every move decides where your opponent plays next, and winning a small "
    "board earns you a bonus mark. The AI searches several placements ahead."
)

CREDITS = (
    "Rei Putra Soemanto",
    "Louie Nathaniel Christopher",
    "Nevandio Hera Joevandy",
    "Muhammad Dzaky Nabil Amin",
)

DIFFICULTY_LABELS = {value: title for value, title, _, _ in DIFFICULTIES}

MAX_WIDTH = 1152
SIDE_WIDTH = 340
TWO_COLUMN_MIN = 900
GAP = 24
CARD_GAP = 12


def logo_mark(title_size: int) -> int:
    """Size of each logo mark beside a title of `title_size`."""
    return round(title_size * 0.7)


class SetupScreen:
    def __init__(self, settings: Settings) -> None:
        self.draft = settings
        self.custom = {
            mode: getattr(settings, key) not in presets for mode, (_, _, presets, _, key) in TIME_OPTIONS.items()
        }
        self.text = {mode: str(getattr(settings, key)) for mode, (*_, key) in TIME_OPTIONS.items()}
        self.input_focused = False
        self.input_rect = pygame.Rect(0, 0, 0, 0)
        self.scroll = 0
        self.content_height = 0

    def with_theme(self, theme: str) -> None:
        self.draft = replace(self.draft, theme=theme)

    def custom_value(self, mode: str) -> int | None:
        _, _, _, (low, high), _ = TIME_OPTIONS[mode]
        text = self.text[mode]
        if not text.isdigit():
            return None
        value = int(text)
        return value if low <= value <= high else None

    @property
    def valid(self) -> bool:
        mode = self.draft.mode
        return mode == "free" or not self.custom[mode] or self.custom_value(mode) is not None

    def settings(self) -> Settings:
        mode = self.draft.mode
        if mode != "free" and self.custom[mode]:
            return replace(self.draft, **{TIME_OPTIONS[mode][4]: self.custom_value(mode)})
        return self.draft

    def clock_summary(self) -> str:
        mode = self.draft.mode
        if mode == "free":
            return "no clock"
        _, unit, _, _, key = TIME_OPTIONS[mode]
        value = self.custom_value(mode) if self.custom[mode] else getattr(self.draft, key)
        if value is None:
            return "custom time"
        return f"{value} s per placement" if mode == "competitive" else f"{value} min game"

    def type_text(self, text: str) -> None:
        if self.input_focused and self.draft.mode in TIME_OPTIONS:
            digits = "".join(ch for ch in text if ch.isdigit())
            self.text[self.draft.mode] = (self.text[self.draft.mode] + digits)[:3]

    def backspace(self) -> None:
        if self.input_focused and self.draft.mode in TIME_OPTIONS:
            self.text[self.draft.mode] = self.text[self.draft.mode][:-1]

    def scroll_by(self, pixels: int, view_height: int) -> None:
        self.scroll = max(0, min(self.scroll + pixels, max(0, self.content_height - view_height)))

    def draw(self, ui: Ui, now: float, on_start: Action, on_toggle_theme: Action) -> None:
        surface = ui.surface
        p = ui.p
        width, height = surface.get_size()
        self.scroll_by(0, height)
        cw = min(MAX_WIDTH, width - 64)
        x = (width - cw) // 2
        y = 40 - self.scroll

        toggle = ui.toggle("Dark theme", (x + cw, y + 12), self.draft.theme == "dark", on_toggle_theme)
        y = self._title(ui, x, y, toggle.x - x - 24) + 14
        y = ui.text(INTRO, (x, y), Face.REGULAR, 18, p.muted, wrap=min(cw, 640)).bottom + 32

        if cw >= TWO_COLUMN_MIN:
            main_w = cw - SIDE_WIDTH - GAP
            main_bottom = ui.card_section(x, y, main_w, lambda cy, w: self._settings(ui, x + 28, cy, w, now), (28, 28))
            side_bottom = self._side(ui, x + main_w + GAP, y, SIDE_WIDTH, on_start)
            y = max(main_bottom, side_bottom) + 32
        else:
            y = ui.card_section(x, y, cw, lambda cy, w: self._settings(ui, x + 24, cy, w, now), (24, 24)) + CARD_GAP
            y = self._side(ui, x, y, cw, on_start) + 32

        y = self._rules(ui, x, y, cw)
        self.content_height = y + self.scroll + 48

        if self.content_height > height:
            track = height - 16
            thumb_h = max(32, track * height // self.content_height)
            thumb_y = 8 + (track - thumb_h) * self.scroll // max(1, self.content_height - height)
            ui.rounded(pygame.Rect(width - 7, thumb_y, 4, thumb_h), 2, p.rule)

    def _title(self, ui: Ui, x: int, y: int, room: int) -> int:
        size = 60
        while size > 32 and 2 * logo_mark(size) + 18 + measure("Super Tic-Tac-Toe", Face.DISPLAY, size)[0] > room:
            size -= 4
        mark = logo_mark(size)
        title = render("Super Tic-Tac-Toe", Face.DISPLAY, size, ui.p.ink)
        row_h = max(mark, title.get_height())
        right = ui.logo((x, y + (row_h - mark) // 2), mark)
        ui.blit(title, (right + 18, y + (row_h - title.get_height()) // 2))
        return y + row_h

    def _settings(self, ui: Ui, x: int, y: int, width: int, now: float) -> int:
        y = self._cards(ui, x, y, width, "Mode", MODES, self.draft.mode, self._set_mode, icons=True) + 28
        mode = self.draft.mode
        if mode in TIME_OPTIONS:
            y = self._time_picker(ui, x, y, mode, now) + 28
        return self._cards(ui, x, y, width, "Difficulty", DIFFICULTIES, self.draft.difficulty, self._set_difficulty)

    def _cards(self, ui: Ui, x: int, y: int, width: int, legend: str, options, selected: str, choose, icons: bool = False) -> int:
        y = ui.text(legend, (x, y), Face.SEMIBOLD, 16).bottom + 12
        card_w = (width - 2 * CARD_GAP) // 3
        card_h = max(option_height(title, body, card_w, icon=icons, meter=not icons) for _, title, body, _ in options)
        for i, (value, title, body, extra) in enumerate(options):
            rect = pygame.Rect(x + i * (card_w + CARD_GAP), y, card_w, card_h)
            ui.option(
                rect,
                title,
                body,
                selected == value,
                lambda v=value: choose(v),
                icon=extra if icons else None,
                meter=None if icons else extra,
            )
        return y + card_h

    def _time_picker(self, ui: Ui, x: int, y: int, mode: str, now: float) -> int:
        p = ui.p
        legend, unit, presets, (low, high), key = TIME_OPTIONS[mode]
        legend_rect = ui.text(legend, (x, y), Face.SEMIBOLD, 16)
        ui.text(f"Between {low} and {high} {unit}", (legend_rect.right + 12, y + 2), Face.REGULAR, 14, p.muted)
        y = legend_rect.bottom + 12
        custom = self.custom[mode]
        cx = x
        for preset in presets:
            rect = ui.chip(f"{preset} {unit}", (cx, y), not custom and getattr(self.draft, key) == preset,
                           lambda v=preset: self._set_preset(mode, v))
            cx = rect.right + 8
        rect = ui.chip("Custom", (cx, y), custom, lambda: self._set_custom(mode))
        y = rect.bottom
        if not custom:
            self.input_rect = pygame.Rect(0, 0, 0, 0)
            return y

        y += 12
        self.input_rect = pygame.Rect(x, y, 96, 44)
        if self.input_focused:
            ui.rounded(self.input_rect, 10, p.card, p.ink, 2)
        else:
            ui.rounded(self.input_rect, 10, p.card, p.rule)
        text_rect = ui.text(self.text[mode], (x + 14, y + 11), Face.REGULAR, 16)
        if self.input_focused and int(now * 2) % 2 == 0:
            caret_x = x + 14 + measure(self.text[mode], Face.REGULAR, 16)[0] + 1
            ui.fill(pygame.Rect(caret_x, y + 11, 2, text_rect.height), p.ink)
        ui.region(self.input_rect, self._focus_input, "Custom value")
        ui.text(unit, (self.input_rect.right + 10, y + 11), Face.REGULAR, 16)
        y = self.input_rect.bottom
        if self.custom_value(mode) is None:
            y = ui.text(f"Enter a whole number from {low} to {high}.", (x, y + 6), Face.SEMIBOLD, 14, p.danger).bottom
        return y

    def _side(self, ui: Ui, x: int, y: int, width: int, on_start: Action) -> int:
        y = ui.card_section(x, y, width, lambda cy, w: self._players(ui, x + 20, cy, w, on_start), (20, 20)) + CARD_GAP
        return ui.card_section(x, y, width, lambda cy, w: self._credits(ui, x + 20, cy), (20, 20))

    def _players(self, ui: Ui, x: int, y: int, width: int, on_start: Action) -> int:
        p = ui.p
        ai_line = f"Plays O. {DIFFICULTY_LABELS[self.draft.difficulty]}, {self.clock_summary()}."
        for player, name, line in ((X, "You", "Play X and move first, anywhere."), (O, "AI", ai_line)):
            ui.blit(marks.mark(player, 32, p.player(player), 0.13), (x, y + 2))
            ui.text(name, (x + 44, y), Face.BOLD, 15)
            y = ui.text(line, (x + 44, y + 20), Face.REGULAR, 14, p.muted, wrap=width - 44).bottom + 14
        return ui.button(
            "Start game", (x, y + 4), on_start, enabled=self.valid, size=18, pad=(0, 17), width=width, icon="arrow"
        ).bottom

    def _credits(self, ui: Ui, x: int, y: int) -> int:
        p = ui.p
        y = ui.heading("Made by", (x, y)).bottom + 12
        for i, name in enumerate(CREDITS):
            rect = ui.text(name, (x + 18, y), Face.SEMIBOLD, 15)
            dot = pygame.Rect(x, rect.centery - 4, 8, 8)
            ui.rounded(dot, 4, p.x_ink if i % 2 == 0 else p.o_ink)
            y = rect.bottom + 8
        return y - 8

    def _rules(self, ui: Ui, x: int, y: int, cw: int) -> int:
        p = ui.p
        y = ui.text("How to play", (x, y), Face.SEMIBOLD, 16).bottom + 12
        columns = 5 if cw >= 1000 else 3 if cw >= 640 else 2
        tile_w = (cw - CARD_GAP * (columns - 1)) // columns
        pad = 16
        for row_start in range(0, len(RULES), columns):
            row = RULES[row_start : row_start + columns]
            images = [render(rule, Face.REGULAR, 14, p.muted, tile_w - 2 * pad) for rule in row]
            number_h = measure("01", Face.DISPLAY, 22)[1]
            tile_h = pad * 2 + number_h + 8 + max(image.get_height() for image in images)
            for i, image in enumerate(images):
                n = row_start + i
                rect = pygame.Rect(x + i * (tile_w + CARD_GAP), y, tile_w, tile_h)
                ui.card(rect, 12)
                ui.text(f"{n + 1:02d}", (rect.x + pad, rect.y + pad), Face.DISPLAY, 22, p.x_ink if n % 2 == 0 else p.o_ink)
                ui.blit(image, (rect.x + pad, rect.y + pad + number_h + 8))
            y += tile_h + CARD_GAP
        return y - CARD_GAP

    def _set_mode(self, mode: str) -> None:
        self.draft = replace(self.draft, mode=mode)
        self.input_focused = False

    def _set_difficulty(self, difficulty: str) -> None:
        self.draft = replace(self.draft, difficulty=difficulty)

    def _set_preset(self, mode: str, value: int) -> None:
        self.custom[mode] = False
        self.input_focused = False
        self.draft = replace(self.draft, **{TIME_OPTIONS[mode][4]: value})

    def _set_custom(self, mode: str) -> None:
        self.custom[mode] = True
        self.input_focused = True

    def _focus_input(self) -> None:
        self.input_focused = True
