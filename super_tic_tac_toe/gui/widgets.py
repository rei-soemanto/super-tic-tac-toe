"""Immediate-mode widgets.

Screens redraw every frame; each interactive widget registers a clickable region. Clicks are
matched against the regions of the frame on screen. A modal layer blocks everything below it.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from super_tic_tac_toe.gui.fonts import Face, measure, render
from super_tic_tac_toe.gui.theme import LIGHT, Color, Palette, mix

Action = Callable[[], None]


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

    def text(
        self,
        text: str,
        pos: tuple[int, int],
        face: Face = Face.REGULAR,
        size: int = 16,
        color: Color | None = None,
        wrap: int = 0,
    ) -> pygame.Rect:
        image = render(text, face, size, color or self.p.ink, wrap)
        return self.surface.blit(image, pos)

    def fill(self, rect: pygame.Rect, color: Color) -> None:
        self.surface.fill(color, rect)

    def border(self, rect: pygame.Rect, color: Color, width: int = 2) -> None:
        pygame.draw.rect(self.surface, color, rect, width)

    def rule(self, x: int, y: int, width: int) -> None:
        self.surface.fill(self.p.rule, pygame.Rect(x, y, width, 1))

    def button(
        self,
        label: str,
        pos: tuple[int, int],
        action: Action,
        primary: bool = True,
        enabled: bool = True,
        size: int = 16,
        pad: tuple[int, int] = (16, 10),
    ) -> pygame.Rect:
        tw, th = measure(label, Face.SEMIBOLD, size)
        rect = pygame.Rect(pos, (tw + pad[0] * 2, th + pad[1] * 2))
        p = self.p
        hover = enabled and self.hovered(rect)
        if primary:
            background = mix(p.ink, p.paper, 0.15) if hover else p.ink
            if not enabled:
                background = mix(p.ink, p.paper, 0.6)
            self.fill(rect, background)
            color = p.paper
        else:
            if hover:
                self.fill(rect, p.wash)
            edge = p.ink if enabled else mix(p.ink, p.paper, 0.6)
            self.border(rect, edge)
            color = edge
        self.text(label, (rect.x + pad[0], rect.y + pad[1]), Face.SEMIBOLD, size, color)
        if enabled:
            self.region(rect, action, label)
        return rect

    def link(self, label: str, pos: tuple[int, int], action: Action, size: int = 14) -> pygame.Rect:
        tw, th = measure(label, Face.REGULAR, size)
        rect = pygame.Rect(pos, (tw, th + 4))
        color = self.p.ink if self.hovered(rect) else self.p.muted
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
    ) -> None:
        p = self.p
        pad = 16
        title_h = measure(title, Face.BOLD, 18)[1]
        body_image = render(body, Face.REGULAR, 14, p.paper if selected else p.muted, rect.width - 2 * pad) if body else None
        if selected:
            self.fill(rect, p.ink)
        else:
            self.border(rect, p.ink if self.hovered(rect) else p.rule)
        self.text(title, (rect.x + pad, rect.y + pad), Face.BOLD, 18, p.paper if selected else p.ink)
        if body_image:
            if selected:
                body_image.set_alpha(200)
            self.surface.blit(body_image, (rect.x + pad, rect.y + pad + title_h + 4))
        self.region(rect, action, title)

    def chip(self, label: str, pos: tuple[int, int], selected: bool, action: Action) -> pygame.Rect:
        tw, th = measure(label, Face.REGULAR, 16)
        rect = pygame.Rect(pos, (tw + 32, th + 26))
        p = self.p
        if selected:
            self.fill(rect, p.ink)
        else:
            self.border(rect, p.ink if self.hovered(rect) else p.rule)
        self.text(label, (rect.x + 16, rect.y + 13), Face.REGULAR, 16, p.paper if selected else p.ink)
        self.region(rect, action, label)
        return rect

    def toggle(self, label: str, pos: tuple[int, int], on: bool, action: Action) -> pygame.Rect:
        """A switch with its label on the left; `pos` is the top-right corner."""
        p = self.p
        tw, th = measure(label, Face.REGULAR, 14)
        track = pygame.Rect(0, 0, 40, 22)
        track.topright = pos
        text_pos = (track.x - 10 - tw, track.centery - th // 2)
        rect = pygame.Rect(text_pos[0], track.y, track.right - text_pos[0], track.height)
        hover = self.hovered(rect)
        if on:
            pygame.draw.rect(self.surface, p.ink, track, border_radius=11)
        pygame.draw.rect(self.surface, p.ink, track, 2, border_radius=11)
        knob_x = track.right - 11 if on else track.x + 11
        pygame.draw.circle(self.surface, p.paper if on else p.ink, (knob_x, track.centery), 6)
        self.text(label, text_pos, Face.REGULAR, 14, p.ink if hover else p.muted)
        self.region(rect, action, label)
        return rect

    def banner(self, message: str, rect_x: int, y: int, width: int, action_label: str | None, action: Action | None) -> int:
        p = self.p
        image = render(message, Face.SEMIBOLD, 16, p.ink, width - 160)
        height = max(image.get_height() + 24, 56)
        rect = pygame.Rect(rect_x, y, width, height)
        self.border(rect, p.ink)
        self.surface.blit(image, (rect.x + 16, rect.centery - image.get_height() // 2))
        if action_label and action:
            bw, bh = measure(action_label, Face.SEMIBOLD, 16)
            self.button(action_label, (rect.right - bw - 32 - 12, rect.centery - (bh + 20) // 2), action)
        return height


def option_height(title: str, body: str, width: int) -> int:
    pad = 16
    height = pad * 2 + measure(title, Face.BOLD, 18)[1]
    if body:
        height += 4 + render(body, Face.REGULAR, 14, LIGHT.ink, width - 2 * pad).get_height()
    return height
