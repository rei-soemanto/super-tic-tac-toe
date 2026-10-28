import pygame

from super_tic_tac_toe.engine.rules import CELLS_OF, DRAW, FULL, LINES, OPEN, O, X
from super_tic_tac_toe.engine.state import GameState, Placement
from super_tic_tac_toe.gui import marks
from super_tic_tac_toe.gui.theme import Palette, mix

FLASH_S = 0.48
FLASH_STEP_S = 0.12
DIM_ALPHA = 110


def highlighted_grids(state: GameState, interactive: bool) -> set[int]:
    """Grids the human may play in: the active grid, or every open grid on a free or bonus move."""
    if not interactive:
        return set()
    if state.active_grid is not None:
        return {state.active_grid}
    return set(CELLS_OF[FULL & ~state.closed])


def winning_grids(state: GameState) -> set[int]:
    """The three small grids that won the game, if it was won by a line."""
    for player in (X, O):
        for line in LINES:
            if state.big[player] & line == line:
                return set(CELLS_OF[line])
    return set()


def owner(state: GameState, grid: int, cell: int) -> int | None:
    if state.bits[X][grid] >> cell & 1:
        return X
    if state.bits[O][grid] >> cell & 1:
        return O
    return None


class BoardView:
    def __init__(self) -> None:
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.grid_rects: list[pygame.Rect] = []
        self.cell_rects: list[list[pygame.Rect]] = []
        self.placed_at: dict[Placement, float] = {}
        self.won_at: dict[int, float] = {}
        self._known: tuple[tuple[Placement, ...], tuple[int, ...]] | None = None

    def layout(self, rect: pygame.Rect) -> None:
        size = rect.width
        gap = 8 if size >= 480 else 6
        grid_size = (size - 4 * gap) / 3
        pad = grid_size * 0.07
        cell = (grid_size - 2 * pad) / 3
        self.rect = pygame.Rect(rect.x, rect.y, size, size)
        self.grid_rects, self.cell_rects = [], []
        for grid in range(9):
            gx = rect.x + gap + (grid % 3) * (grid_size + gap)
            gy = rect.y + gap + (grid // 3) * (grid_size + gap)
            self.grid_rects.append(pygame.Rect(round(gx), round(gy), round(gx + grid_size) - round(gx), round(gy + grid_size) - round(gy)))
            cells = []
            for c in range(9):
                cx = gx + pad + (c % 3) * cell
                cy = gy + pad + (c // 3) * cell
                cells.append(pygame.Rect(round(cx), round(cy), round(cx + cell) - round(cx), round(cy + cell) - round(cy)))
            self.cell_rects.append(cells)

    def cell_at(self, pos: tuple[int, int]) -> Placement | None:
        if not self.rect.collidepoint(pos):
            return None
        for grid, grid_rect in enumerate(self.grid_rects):
            if grid_rect.collidepoint(pos):
                for cell, cell_rect in enumerate(self.cell_rects[grid]):
                    if cell_rect.collidepoint(pos):
                        return grid, cell
        return None

    def track(self, state: GameState, now: float) -> None:
        """Records when placements and grid wins first appear, to animate them."""
        placements = tuple(state.placements())
        statuses = tuple(state.grid_status)
        if self._known is None:
            self._known = (placements, statuses)
            return
        old_placements, old_statuses = self._known
        common = 0
        while common < min(len(placements), len(old_placements)) and placements[common] == old_placements[common]:
            common += 1
        if common < len(old_placements):
            self.placed_at = {p: t for p, t in self.placed_at.items() if p in placements[:common]}
            self.won_at = {g: t for g, t in self.won_at.items() if statuses[g] == old_statuses[g]}
        for placement in placements[common:]:
            self.placed_at[placement] = now
        for grid, status in enumerate(statuses):
            if status not in (OPEN, DRAW) and old_statuses[grid] != status:
                self.won_at[grid] = now
        self._known = (placements, statuses)

    def reset_animation(self) -> None:
        self.placed_at.clear()
        self.won_at.clear()
        self._known = None

    def draw(
        self,
        surface: pygame.Surface,
        p: Palette,
        state: GameState,
        interactive: bool,
        now: float,
        hover: Placement | None,
        flash_at: float | None,
    ) -> None:
        highlighted = highlighted_grids(state, interactive)
        legal = set(state.legal_moves()) if interactive else set()
        history = state.history
        last = (history[-1][0], history[-1][1]) if history else None
        last_owner = owner(state, *last) if last else None
        winners = winning_grids(state)
        flashing = flash_at is not None and 0 <= now - flash_at < FLASH_S
        flash_on = flashing and int((now - flash_at) / FLASH_STEP_S) % 2 == 0
        radius = max(4, round(self.grid_rects[0].width * 0.05))

        surface.blit(marks.rounded(self.rect.size, round(radius * 1.6), p.frame), self.rect.topleft)
        for grid, grid_rect in enumerate(self.grid_rects):
            status = state.grid_status[grid]
            background = p.x_wash if grid in highlighted else p.card
            surface.blit(marks.rounded(grid_rect.size, radius, background), grid_rect.topleft)
            cells = self.cell_rects[grid]
            inner = cells[0].union(cells[8])
            for i in (1, 2):
                surface.fill(p.line, (cells[i].x, inner.y, 1, inner.height))
                surface.fill(p.line, (inner.x, cells[i * 3].y, inner.width, 1))

            fade = 0.16 if status not in (OPEN, DRAW) else 0.38 if status == DRAW else 1.0
            for cell, cell_rect in enumerate(cells):
                player = owner(state, grid, cell)
                if (grid, cell) == last and last_owner is not None:
                    tint = pygame.Rect(cell_rect.x + 1, cell_rect.y + 1, cell_rect.width - 1, cell_rect.height - 1)
                    surface.fill(p.tint(last_owner), tint)
                if player is not None:
                    color = mix(background, p.player(player), fade)
                    self._blit_mark(surface, player, cell_rect, color, now, self.placed_at.get((grid, cell)))
                elif (grid, cell) in legal and hover == (grid, cell):
                    self._blit_mark(surface, X, cell_rect, mix(background, p.x_ink, 0.3), now, None)

            if status not in (OPEN, DRAW):
                size = round(grid_rect.width * 0.88)
                started = self.won_at.get(grid)
                image = marks.mark(status - 1, size, p.player(status - 1), 0.07, None if started is None else now - started)
                surface.blit(image, image.get_rect(center=grid_rect.center))
            if winners and grid not in winners:
                surface.blit(marks.rounded(grid_rect.size, radius, p.paper + (DIM_ALPHA,)), grid_rect.topleft)
            edge = None
            if grid in winners:
                edge = (p.player(status - 1), 4)
            elif grid in highlighted and (flash_on or state.active_grid == grid):
                edge = (p.x_ink, 5 if flash_on else 3)
            if edge:
                surface.blit(marks.rounded(grid_rect.size, radius, None, edge[0], edge[1]), grid_rect.topleft)

    @staticmethod
    def _blit_mark(
        surface: pygame.Surface,
        player: int,
        cell_rect: pygame.Rect,
        color: tuple[int, int, int],
        now: float,
        placed_at: float | None,
    ) -> None:
        size = round(min(cell_rect.width, cell_rect.height) * 0.78)
        elapsed = None if placed_at is None else now - placed_at
        image = marks.mark(player, size, color, 0.1, elapsed)
        surface.blit(image, image.get_rect(center=cell_rect.center))
