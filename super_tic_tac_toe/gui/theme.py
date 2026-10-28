from dataclasses import dataclass

from super_tic_tac_toe.game.settings import Theme

Color = tuple[int, int, int]


def hex_color(value: str) -> Color:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def mix(a: Color, b: Color, amount: float) -> Color:
    """`amount` of b over a."""
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))  # type: ignore[return-value]


@dataclass(frozen=True)
class Palette:
    paper: Color
    wash: Color
    rule: Color
    muted: Color
    ink: Color
    danger: Color


LIGHT = Palette(
    paper=hex_color("#ffffff"),
    wash=hex_color("#ededed"),
    rule=hex_color("#d4d4d4"),
    muted=hex_color("#666666"),
    ink=hex_color("#000000"),
    danger=hex_color("#d40000"),
)

DARK = Palette(
    paper=hex_color("#171717"),
    wash=hex_color("#2b2b2b"),
    rule=hex_color("#404040"),
    muted=hex_color("#a3a3a3"),
    ink=hex_color("#ffffff"),
    danger=hex_color("#ff5252"),
)


def palette(theme: Theme) -> Palette:
    return DARK if theme == "dark" else LIGHT
