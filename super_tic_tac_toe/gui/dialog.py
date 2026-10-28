import pygame

from super_tic_tac_toe.engine.rules import O, X
from super_tic_tac_toe.game.session import HUMAN, GameEnd, Timeout
from super_tic_tac_toe.gui import marks
from super_tic_tac_toe.gui.fonts import Face, measure, render
from super_tic_tac_toe.gui.widgets import Action, Ui

OVERLAY_ALPHA = 115
MARK_SIZE = 56


def end_title(end: GameEnd) -> str:
    if end.winner is None:
        return "Draw"
    return "You win" if end.winner == HUMAN else "AI wins"


def end_reason(end: GameEnd, won: tuple[int, int]) -> str:
    if end.reason == "win":
        return "Three small grids in a row."
    if end.reason == "draw":
        return "Every small grid is closed and nobody has three in a row."
    if end.timed_out == Timeout.HUMAN:
        return "You ran out of time for your placement."
    if end.timed_out == Timeout.AI:
        return "The AI ran out of time for its placement."
    return f"Time is up. Small grids won: you {won[0]}, AI {won[1]}."


def draw_game_over(
    ui: Ui,
    end: GameEnd,
    won: tuple[int, int],
    can_undo: bool,
    on_play_again: Action,
    on_change_settings: Action,
    on_undo: Action,
    on_view_board: Action,
) -> None:
    surface = ui.surface
    p = ui.p
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((*p.scrim, OVERLAY_ALPHA))
    surface.blit(overlay, (0, 0))
    ui.begin_modal()

    width = min(420, int(surface.get_width() * 0.92))
    pad = 28
    inner = width - 2 * pad
    title = render(end_title(end), Face.DISPLAY, 40, p.ink, inner)
    reason = render(end_reason(end, won), Face.REGULAR, 16, p.muted, inner)
    button_h = measure("Play again", Face.SEMIBOLD, 15)[1] + 24
    link_h = measure("View board", Face.REGULAR, 14)[1] + 4
    height = pad + MARK_SIZE + 12 + title.get_height() + 8 + reason.get_height() + 24 + button_h + 16 + link_h + pad

    box = pygame.Rect(0, 0, width, height)
    box.center = surface.get_rect().center
    ui.rounded(box, 20, p.card, p.border)

    x, y = box.x + pad, box.y + pad
    winners = (X, O) if end.winner is None else (end.winner,)
    for i, player in enumerate(winners):
        ui.blit(marks.mark(player, MARK_SIZE, p.player(player), 0.12), (x + i * MARK_SIZE, y))
    y += MARK_SIZE + 12
    y = ui.blit(title, (x, y)).bottom + 8
    y = ui.blit(reason, (x, y)).bottom + 24
    for label, action, primary in (
        ("Play again", on_play_again, True),
        ("Change settings", on_change_settings, False),
        ("Undo", on_undo, False),
    ):
        if label != "Undo" or can_undo:
            x = ui.button(label, (x, y), action, primary=primary, pad=(18, 12)).right + 8
    ui.link("View board", (box.x + pad, y + button_h + 16), on_view_board)
