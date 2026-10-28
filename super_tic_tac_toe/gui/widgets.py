"""Immediate-mode widgets.

Screens redraw every frame; each interactive widget registers a clickable region. Clicks are
matched against the regions of the frame on screen. A modal layer blocks everything below it.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import pygame

from super_tic_tac_toe.engine.rules import O, X
from super_tic_tac_toe.gui import marks
from super_tic_tac_toe.gui.fonts import Face, measure, render
from super_tic_tac_toe.gui.theme import LIGHT, Color, Palette, mix

Action = Callable[[], None]

CARD_RADIUS = 14
CONTROL_RADIUS = 10
OPTION_PAD = 16
OPTION_ICON = 26
METER_SEGMENTS = 6


@dataclass
class Region:
    rect: pygame.Rect
    action: Action
    label: str


class Ui:
    def __init__(self) -> None:
        self.surface: pygame.Surface | None = None
        self.colors: Palette | None = None
        self.mouse = (-1, -1)
        self.regions: list[Region] = []
        self.modal_from: int | None = None
        self._modal_pending = False
        self._scratch = pygame.Surface((1, 1), pygame.SRCALPHA)

    def begin_frame(self, surface: pygame.Surface, colors: Palette, mouse: tuple[int, int], modal: bool) -> None:
        self.surface = surface
        self.colors = colors
        self.mouse = mouse
        self.regions = []
        self.modal_from = None
        self._modal_pending = modal

    def begin_modal(self) -> None:
        self.modal_from = len(self.regions)
        self._modal_pending = False

    @property
    def p(self) -> Palette:
        assert self.colors is not None
        return self.colors

    @contextmanager
    def dry_run(self) -> Iterator[None]:
        """Lays widgets out without drawing them or registering their regions."""
        surface, count = self.surface, len(self.regions)
        self.surface = self._scratch
        try:
            yield
        finally:
            self.surface = surface
            del self.regions[count:]

    def hovered(self, rect: pygame.Rect) -> bool:
        return not self._modal_pending and rect.collidepoint(self.mouse)

    def region(self, rect: pygame.Rect, action: Action, label: str = "") -> None:
        self.regions.append(Region(pygame.Rect(rect), action, label))

    def active_regions(self) -> list[Region]:
        return self.regions if self.modal_from is None else self.regions[self.modal_from :]

    def click(self, pos: tuple[int, int]) -> bool:
        for region in reversed(self.active_regions()):
            if region.rect.collidepoint(pos):
                region.action()
                return True
        return False

    def over_clickable(self, pos: tuple[int, int]) -> bool:
        return any(region.rect.collidepoint(pos) for region in self.active_regions())

    def find(self, label: str) -> pygame.Rect | None:
        return next((r.rect for r in self.active_regions() if r.label == label), None)

    def blit(self, image: pygame.Surface, pos: tuple[int, int]) -> pygame.Rect:
        self.surface.blit(image, pos)
        return pygame.Rect(pos, image.get_size())

    def text(
        self,
        text: str,
        pos: tuple[int, int],
        face: Face = Face.REGULAR,
        size: int = 16,
        color: Color | None = None,
        wrap: int = 0,
    ) -> pygame.Rect:
        return self.blit(render(text, face, size, color or self.p.ink, wrap), pos)

    def fill(self, rect: pygame.Rect, color: Color) -> None:
        self.surface.fill(color, rect)

    def border(self, rect: pygame.Rect, color: Color, width: int = 2) -> None:
        pygame.draw.rect(self.surface, color, rect, width)

    def rounded(
        self, rect: pygame.Rect, radius: int, fill: Color | None, edge: Color | None = None, edge_width: int = 1
    ) -> None:
        self.surface.blit(marks.rounded(rect.size, radius, fill, edge, edge_width), rect.topleft)

    def rule(self, x: int, y: int, width: int) -> None:
        self.surface.fill(self.p.border, pygame.Rect(x, y, width, 1))

    def card(self, rect: pygame.Rect, radius: int = CARD_RADIUS) -> None:
        self.rounded(rect, radius, self.p.card, self.p.border)

    def card_section(
        self, x: int, y: int, width: int, content: Callable[[int, int], int], pad: tuple[int, int] = (18, 16)
    ) -> int:
        """A card sized to fit `content(y, inner_width)`, which draws from `y` and returns its bottom."""
        with self.dry_run():
            bottom = content(y + pad[1], width - 2 * pad[0])
        self.card(pygame.Rect(x, y, width, bottom + pad[1] - y))
        content(y + pad[1], width - 2 * pad[0])
        return bottom + pad[1]

    def logo(self, pos: tuple[int, int], size: int) -> int:
        """The X and O pair, each `size` pixels square; returns its right edge."""
        p = self.p
        self.blit(marks.mark(X, size, p.x_ink, 0.14), pos)
        self.blit(marks.mark(O, size, p.o_ink, 0.14), (pos[0] + size, pos[1]))
        return pos[0] + 2 * size

    def heading(self, text: str, pos: tuple[int, int]) -> pygame.Rect:
        """A small uppercase section label."""
        return self.text(text.upper(), pos, Face.SEMIBOLD, 12, self.p.muted)

    def button(
        self,
        label: str,
        pos: tuple[int, int],
        action: Action,
        primary: bool = True,
        enabled: bool = True,
        size: int = 15,
        pad: tuple[int, int] = (18, 11),
        width: int | None = None,
        icon: str | None = None,
    ) -> pygame.Rect:
        tw, th = measure(label, Face.SEMIBOLD, size)
        icon_w = size + 4 if icon else 0
        content_w = tw + (icon_w + 10 if icon else 0)
        rect = pygame.Rect(pos, (width or content_w + pad[0] * 2, th + pad[1] * 2))
        p = self.p
        hover = enabled and self.hovered(rect)
        if primary:
            background = mix(p.ink, p.card, 0.18) if hover else p.ink
            if not enabled:
                background = mix(p.ink, p.card, 0.6)
            self.rounded(rect, CONTROL_RADIUS, background)
            color = p.on_ink
        else:
            edge = p.ink if hover else p.rule
            self.rounded(rect, CONTROL_RADIUS, p.wash if hover else None, edge if enabled else p.border)
            color = p.ink if enabled else mix(p.ink, p.card, 0.6)
        tx = rect.x + (rect.width - content_w) // 2
        self.text(label, (tx, rect.y + pad[1]), Face.SEMIBOLD, size, color)
        if icon:
            self.blit(marks.icon(icon, icon_w, color, 2.5), (tx + tw + 10, rect.centery - icon_w // 2))
        if enabled:
            self.region(rect, action, label)
        return rect

    def link(self, label: str, pos: tuple[int, int], action: Action, size: int = 14) -> pygame.Rect:
        tw, th = measure(label, Face.REGULAR, size)
        rect = pygame.Rect(pos, (tw, th + 4))
        color = self.p.ink if self.hovered(rect) else self.p.o_ink
        self.text(label, pos, Face.REGULAR, size, color)
        self.fill(pygame.Rect(rect.x, rect.bottom - 2, tw, 1), color)
        self.region(rect, action, label)
        return rect

    def option(
        self,
        rect: pygame.Rect,
        title: str,
        body: str,
        selected: bool,
        action: Action,
        icon: str | None = None,
        meter: int | None = None,
    ) -> None:
        """A selectable card: optional icon, title, optional 6-segment meter, then body text."""
        p = self.p
        pad = OPTION_PAD
        if selected:
            self.rounded(rect, 12, p.card, p.ink, 2)
        else:
            self.rounded(rect, 12, p.card, p.ink if self.hovered(rect) else p.rule)
        x, y = rect.x + pad, rect.y + pad
        if icon:
            self.blit(marks.icon(icon, OPTION_ICON, p.x_ink if selected else p.muted), (x, y))
            y += OPTION_ICON + 8
        y = self.text(title, (x, y), Face.BOLD, 16).bottom + 8
        if meter is not None:
            inner = rect.width - 2 * pad
            seg = (inner - 3 * (METER_SEGMENTS - 1)) / METER_SEGMENTS
            for i in range(METER_SEGMENTS):
                bar = pygame.Rect(round(x + i * (seg + 3)), y, round(seg), 6)
                self.rounded(bar, 3, p.o_ink if i < meter else p.line)
            y += 6 + 10
        if body:
            self.text(body, (x, y), Face.REGULAR, 14, p.muted, rect.width - 2 * pad)
        self.region(rect, action, title)

    def chip(self, label: str, pos: tuple[int, int], selected: bool, action: Action) -> pygame.Rect:
        face = Face.SEMIBOLD if selected else Face.REGULAR
        tw, th = measure(label, face, 15)
        rect = pygame.Rect(pos, (tw + 40, th + 20))
        p = self.p
        radius = rect.height // 2
        if selected:
            self.rounded(rect, radius, p.ink)
        else:
            self.rounded(rect, radius, p.card, p.ink if self.hovered(rect) else p.rule)
        self.text(label, (rect.x + 20, rect.y + 10), face, 15, p.on_ink if selected else p.ink)
        self.region(rect, action, label)
        return rect

    def toggle(self, label: str, pos: tuple[int, int], on: bool, action: Action) -> pygame.Rect:
        """A switch with its label on the left; `pos` is the top-right corner."""
        p = self.p
        tw, th = measure(label, Face.REGULAR, 14)
        track = pygame.Rect(0, 0, 44, 24)
        track.topright = pos
        text_pos = (track.x - 10 - tw, track.centery - th // 2)
        rect = pygame.Rect(text_pos[0], track.y, track.right - text_pos[0], track.height)
        hover = self.hovered(rect)
        self.rounded(track, 12, p.o_ink if on else p.rule)
        knob = pygame.Rect(0, 0, 18, 18)
        knob.center = (track.right - 12 if on else track.x + 12, track.centery)
        self.rounded(knob, 9, p.knob)
        self.text(label, text_pos, Face.REGULAR, 14, p.ink if hover else p.muted)
        self.region(rect, action, label)
        return rect

    def banner(self, message: str, rect_x: int, y: int, width: int, action_label: str | None, action: Action | None) -> int:
        p = self.p
        image = render(message, Face.SEMIBOLD, 15, p.ink, width - 160)
        height = max(image.get_height() + 24, 56)
        rect = pygame.Rect(rect_x, y, width, height)
        self.rounded(rect, CONTROL_RADIUS, p.card, p.danger, 2)
        self.blit(image, (rect.x + 16, rect.centery - image.get_height() // 2))
        if action_label and action:
            bw, bh = measure(action_label, Face.SEMIBOLD, 15)
            self.button(action_label, (rect.right - bw - 36 - 10, rect.centery - (bh + 22) // 2), action)
        return height


def option_height(title: str, body: str, width: int, icon: bool = False, meter: bool = False) -> int:
    pad = OPTION_PAD
    height = pad * 2 + measure(title, Face.BOLD, 16)[1] + 8
    if icon:
        height += OPTION_ICON + 8
    if meter:
        height += 16
    if body:
        height += render(body, Face.REGULAR, 14, LIGHT.ink, width - 2 * pad).get_height()
    return height
