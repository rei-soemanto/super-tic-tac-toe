from dataclasses import dataclass

from super_tic_tac_toe.engine.rules import X
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
    paper: Color  # window ground
    card: Color  # cards, board grids, dialog
    border: Color  # card edges
    wash: Color  # hover fill
    rule: Color  # control edges, clock track
    line: Color  # cell lines inside a small grid
    frame: Color  # board behind the small grids
    muted: Color
    ink: Color
    on_ink: Color  # text on an ink fill
    danger: Color
    x_ink: Color
    o_ink: Color
    x_wash: Color  # grids open to the human
    x_tint: Color  # last-move tint, X
    o_tint: Color  # last-move tint, O
    knob: Color
    scrim: Color  # behind a dialog

    def player(self, player: int) -> Color:
        return self.x_ink if player == X else self.o_ink

    def tint(self, player: int) -> Color:
        return self.x_tint if player == X else self.o_tint


LIGHT = Palette(
    paper=hex_color("#f3f4f6"),
    card=hex_color("#ffffff"),
    border=hex_color("#e3e5e9"),
    wash=hex_color("#f3f4f6"),
    rule=hex_color("#d1d5db"),
    line=hex_color("#e5e7eb"),
    frame=hex_color("#e3e5e9"),
    muted=hex_color("#4b5563"),
    ink=hex_color("#111827"),
    on_ink=hex_color("#ffffff"),
    danger=hex_color("#b91c1c"),
    x_ink=hex_color("#c2410c"),
    o_ink=hex_color("#1d4ed8"),
    x_wash=hex_color("#fff1e8"),
    x_tint=hex_color("#ffedd5"),
    o_tint=hex_color("#e0e7ff"),
    knob=hex_color("#ffffff"),
    scrim=hex_color("#111827"),
)

DARK = Palette(
    paper=hex_color("#111318"),
    card=hex_color("#1a1d24"),
    border=hex_color("#2a2e37"),
    wash=hex_color("#232730"),
    rule=hex_color("#3a3f4a"),
    line=hex_color("#333844"),
    frame=hex_color("#0b0d11"),
    muted=hex_color("#a1a7b3"),
    ink=hex_color("#f3f4f6"),
    on_ink=hex_color("#111318"),
    danger=hex_color("#f87171"),
    x_ink=hex_color("#fb8b4e"),
    o_ink=hex_color("#7aa7ff"),
    x_wash=hex_color("#3a2a22"),
    x_tint=hex_color("#4a3326"),
    o_tint=hex_color("#1e2a44"),
    knob=hex_color("#ffffff"),
    scrim=hex_color("#000000"),
)


def palette(theme: Theme) -> Palette:
    return DARK if theme == "dark" else LIGHT
