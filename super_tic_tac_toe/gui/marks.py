"""Anti-aliased ink strokes: X and O marks and the clock ring.

pygame draws thick shapes without anti-aliasing, so strokes are drawn at 4x on an alpha
surface and smooth-scaled down. Finished surfaces are cached.
"""

import math
from functools import lru_cache

import pygame

from super_tic_tac_toe.engine.rules import X

SUPERSAMPLE = 4
STROKE_S = 0.22
SECOND_STROKE_DELAY_S = 0.11
PROGRESS_STEPS = 24

Color = tuple[int, int, int]


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 2


def stroke_progress(player: int, elapsed: float | None) -> tuple[float, float]:
    """Draw-in progress of the mark's (first, second) stroke `elapsed` seconds after placement."""
    if elapsed is None:
        return 1.0, 1.0
    first = _ease_out(min(1.0, max(0.0, elapsed / STROKE_S)))
    if player != X:
        return first, 1.0
    second = _ease_out(min(1.0, max(0.0, (elapsed - SECOND_STROKE_DELAY_S) / STROKE_S)))
    return first, second


def _segment(surface: pygame.Surface, color: Color, a: tuple[float, float], b: tuple[float, float], width: float) -> None:
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay)
    if length < 0.5:
        pygame.draw.circle(surface, color, a, width / 2)
        return
    nx, ny = -(by - ay) / length * width / 2, (bx - ax) / length * width / 2
    pygame.draw.polygon(surface, color, [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)])
    pygame.draw.circle(surface, color, a, width / 2)
    pygame.draw.circle(surface, color, b, width / 2)


def _arc(
    surface: pygame.Surface,
    color: Color,
    center: tuple[float, float],
    radius: float,
    width: float,
    fraction: float,
    caps: bool,
) -> None:
    if fraction <= 0:
        return
    steps = max(2, int(120 * fraction))
    outer, inner = radius + width / 2, radius - width / 2
    angles = [-math.pi / 2 + 2 * math.pi * fraction * i / steps for i in range(steps + 1)]
    cx, cy = center
    points = [(cx + outer * math.cos(t), cy + outer * math.sin(t)) for t in angles]
    points += [(cx + inner * math.cos(t), cy + inner * math.sin(t)) for t in reversed(angles)]
    pygame.draw.polygon(surface, color, points)
    if caps:
        for t in (angles[0], angles[-1]):
            pygame.draw.circle(surface, color, (cx + radius * math.cos(t), cy + radius * math.sin(t)), width / 2)


def _quantize(value: float) -> float:
    return round(value * PROGRESS_STEPS) / PROGRESS_STEPS


@lru_cache(maxsize=1024)
def _mark(player: int, size: int, color: Color, width: float, first: float, second: float) -> pygame.Surface:
    big = size * SUPERSAMPLE
    canvas = pygame.Surface((big, big), pygame.SRCALPHA)
    w = width * big
    if player == X:
        lo, hi = 0.24 * big, 0.76 * big
        if first > 0:
            _segment(canvas, color, (lo, lo), (lo + (hi - lo) * first, lo + (hi - lo) * first), w)
        if second > 0:
            _segment(canvas, color, (hi, lo), (hi - (hi - lo) * second, lo + (hi - lo) * second), w)
    else:
        _arc(canvas, color, (big / 2, big / 2), 0.28 * big, w, first, caps=True)
    return pygame.transform.smoothscale(canvas, (size, size))


def mark(player: int, size: int, color: Color, width: float = 0.09, elapsed: float | None = None) -> pygame.Surface:
    """A mark `size` pixels square; `width` is the stroke width as a fraction of `size`."""
    first, second = stroke_progress(player, elapsed)
    return _mark(player, max(1, size), color, width, _quantize(first), _quantize(second))


@lru_cache(maxsize=512)
def _ring(size: int, track: Color, color: Color, fraction: float) -> pygame.Surface:
    big = size * SUPERSAMPLE
    canvas = pygame.Surface((big, big), pygame.SRCALPHA)
    center, radius, width = (big / 2, big / 2), big * 0.46, big * 0.04
    _arc(canvas, track, center, radius, width, 1.0, caps=False)
    _arc(canvas, color, center, radius, width, fraction, caps=False)
    return pygame.transform.smoothscale(canvas, (size, size))


def ring(size: int, track: Color, color: Color, fraction: float) -> pygame.Surface:
    """Countdown ring starting at 12 o'clock; `fraction` of the circle remains."""
    return _ring(size, track, color, round(max(0.0, min(1.0, fraction)) * 240) / 240)
