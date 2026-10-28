import pygame

from super_tic_tac_toe.engine.state import GameState, replay
from super_tic_tac_toe.gui.board_view import BoardView, highlighted_grids
from tests.helpers import BONUS_SEQ


class TestHighlightedGrids:
    def test_only_the_active_grid(self) -> None:
        assert highlighted_grids(replay([(4, 2)]), interactive=True) == {2}

    def test_every_open_grid_on_a_free_move(self) -> None:
        assert highlighted_grids(GameState(), interactive=True) == set(range(9))

    def test_every_open_grid_on_a_bonus_placement(self) -> None:
        assert highlighted_grids(replay(BONUS_SEQ), interactive=True) == set(range(1, 9))

    def test_nothing_when_not_the_humans_turn(self) -> None:
        assert highlighted_grids(replay([(4, 2)]), interactive=False) == set()


class TestBoardView:
    def view(self) -> BoardView:
        view = BoardView()
        view.layout(pygame.Rect(10, 20, 600, 600))
        return view

    def test_hit_testing_maps_every_cell(self) -> None:
        view = self.view()
        for grid in range(9):
            for cell in range(9):
                assert view.cell_at(view.cell_rects[grid][cell].center) == (grid, cell)

    def test_gaps_and_outside_are_not_cells(self) -> None:
        view = self.view()
        between = (view.grid_rects[0].right + 2, view.grid_rects[0].centery)
        assert view.cell_at(between) is None
        assert view.cell_at((0, 0)) is None

    def test_tracks_new_placements_and_grid_wins_for_animation(self) -> None:
        view = self.view()
        state = replay(BONUS_SEQ[:-1])
        view.track(state, now=1.0)
        assert view.placed_at == {}
        state.make(0, 0)
        view.track(state, now=2.0)
        assert view.placed_at == {(0, 0): 2.0}
        assert view.won_at == {0: 2.0}

    def test_undo_forgets_removed_placements(self) -> None:
        view = self.view()
        state = GameState()
        view.track(state, now=0.0)
        state.make(4, 2)
        view.track(state, now=1.0)
        state.unmake()
        view.track(state, now=2.0)
        assert view.placed_at == {}
