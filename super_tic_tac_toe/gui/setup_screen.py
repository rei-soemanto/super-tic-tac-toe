from dataclasses import replace

import pygame

from super_tic_tac_toe.game.settings import (
    COMPETITIVE_PRESETS,
    COMPETITIVE_RANGE,
    TIME_BASED_PRESETS,
    TIME_BASED_RANGE,
    Settings,
)
from super_tic_tac_toe.gui.fonts import Face, measure
from super_tic_tac_toe.gui.widgets import Action, Ui, option_height

MODES = (
    ("competitive", "Competitive", "Each placement has its own clock. Run out and you lose."),
    ("time_based", "Time-based", "One clock for the whole game. When it runs out, most small grids won wins."),
    ("free", "Free", "No clock. Undo your turn whenever you like."),
)

DIFFICULTIES = (
    ("easy", "Easy", "Looks 2 placements ahead"),
    ("medium", "Medium", "Looks 4 placements ahead"),
    ("hard", "Hard", "Searches as deep as it can in 2 seconds"),
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

MAX_WIDTH = 768
CARD_GAP = 8


class SetupScreen:
    def __init__(self, settings: Settings) -> None:
        self.draft = settings
        self.custom = {
            mode: getattr(settings, key) not in presets for mode, (_, _, presets, _, key) in TIME_OPTIONS.items()
        }
        self.text = {mode: str(getattr(settings, key)) for mode, (*_, key) in TIME_OPTIONS.items()}
        self.input_focused = False
        self.input_rect = pygame.Rect(0, 0, 0, 0)
        self.rules_open = False
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
        y = 64 - self.scroll

        ui.toggle("Dark theme", (width - 32, 24 - self.scroll), self.draft.theme == "dark", on_toggle_theme)
        title_size = 72 if cw >= 700 else 56
        y = ui.text("Super Tic-Tac-Toe", (x, y), Face.DISPLAY, title_size, wrap=cw).bottom + 16
        y = ui.text(INTRO, (x, y), Face.REGULAR, 18, p.muted, wrap=min(cw, 576)).bottom + 40

        y = self._cards(ui, x, y, cw, "Mode", MODES, self.draft.mode, self._set_mode) + 40
        mode = self.draft.mode
        if mode in TIME_OPTIONS:
            y = self._time_picker(ui, x, y, cw, mode, now) + 40
        y = self._cards(ui, x, y, cw, "Difficulty", DIFFICULTIES, self.draft.difficulty, self._set_difficulty) + 40

        start = ui.button("Start game", (x, y), on_start, enabled=self.valid, size=18, pad=(32, 14))
        y = start.bottom + 40
        ui.rule(x, y, cw)
        y = self._how_to_play(ui, x, y + 16, cw)
        self.content_height = y + self.scroll + 64

        if self.content_height > height:
            track = height - 16
            thumb_h = max(32, track * height // self.content_height)
            thumb_y = 8 + (track - thumb_h) * self.scroll // max(1, self.content_height - height)
            ui.fill(pygame.Rect(width - 6, thumb_y, 3, thumb_h), p.rule)

    def _cards(self, ui: Ui, x: int, y: int, cw: int, legend: str, options, selected: str, choose) -> int:
        y = ui.text(legend, (x, y), Face.SEMIBOLD, 16).bottom + 12
        card_w = (cw - 2 * CARD_GAP) // 3
        card_h = max(option_height(title, body, card_w) for _, title, body in options)
        for i, (value, title, body) in enumerate(options):
            rect = pygame.Rect(x + i * (card_w + CARD_GAP), y, card_w, card_h)
            ui.option(rect, title, body, selected == value, lambda v=value: choose(v))
        return y + card_h

    def _time_picker(self, ui: Ui, x: int, y: int, cw: int, mode: str, now: float) -> int:
        p = ui.p
        legend, unit, presets, (low, high), key = TIME_OPTIONS[mode]
        y = ui.text(legend, (x, y), Face.SEMIBOLD, 16).bottom + 12
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

        y = ui.text(f"Between {low} and {high} {unit}", (x, y + 12), Face.REGULAR, 14, p.muted).bottom + 4
        self.input_rect = pygame.Rect(x, y, 96, 44)
        ui.fill(self.input_rect, p.paper)
        ui.border(self.input_rect, p.ink, 3 if self.input_focused else 2)
        text_rect = ui.text(self.text[mode], (x + 12, y + 11), Face.REGULAR, 16)
        if self.input_focused and int(now * 2) % 2 == 0:
            caret_x = x + 12 + measure(self.text[mode], Face.REGULAR, 16)[0] + 1
            ui.fill(pygame.Rect(caret_x, y + 11, 2, text_rect.height), p.ink)
        ui.region(self.input_rect, self._focus_input, "Custom value")
        ui.text(unit, (self.input_rect.right + 8, y + 11), Face.REGULAR, 16)
        y = self.input_rect.bottom
        if self.custom_value(mode) is None:
            y = ui.text(f"Enter a whole number from {low} to {high}.", (x, y + 6), Face.SEMIBOLD, 14).bottom
        return y

    def _how_to_play(self, ui: Ui, x: int, y: int, cw: int) -> int:
        p = ui.p
        label_w, label_h = measure("How to play", Face.SEMIBOLD, 16)
        row = pygame.Rect(x, y, label_w + 20, label_h)
        cy = row.centery
        if self.rules_open:
            points = [(x, cy - 3), (x + 10, cy - 3), (x + 5, cy + 4)]
        else:
            points = [(x + 2, cy - 5), (x + 9, cy), (x + 2, cy + 5)]
        pygame.draw.polygon(ui.surface, p.ink, points)
        ui.text("How to play", (x + 20, y), Face.SEMIBOLD, 16)
        ui.region(row, self._toggle_rules, "How to play")
        y = row.bottom
        if self.rules_open:
            y += 12
            wrap = min(cw, 576) - 20
            for rule in RULES:
                pygame.draw.circle(ui.surface, p.muted, (x + 6, y + 10), 2)
                y = ui.text(rule, (x + 20, y), Face.REGULAR, 16, p.muted, wrap=wrap).bottom + 6
        return y

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

    def _toggle_rules(self) -> None:
        self.rules_open = not self.rules_open
