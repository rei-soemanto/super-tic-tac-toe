from enum import StrEnum
from functools import cache
from pathlib import Path

import pygame

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


class Face(StrEnum):
    REGULAR = "Archivo-Regular.ttf"
    SEMIBOLD = "Archivo-SemiBold.ttf"
    BOLD = "Archivo-Bold.ttf"
    DISPLAY = "ArchivoExpanded-Black.ttf"
    HEADING = "ArchivoSemiExpanded-Bold.ttf"


@cache
def font(face: Face, size: int) -> pygame.font.Font:
    return pygame.font.Font(FONT_DIR / face.value, size)


def render(text: str, face: Face, size: int, color: tuple[int, int, int], wrap: int = 0) -> pygame.Surface:
    return font(face, size).render(text, True, color, None, wrap)


def measure(text: str, face: Face, size: int) -> tuple[int, int]:
    return font(face, size).size(text)
