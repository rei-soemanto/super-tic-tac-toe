import pytest

from super_tic_tac_toe.engine.rules import BONUS, DRAW, FULL, IS_LINE, NORMAL, O, ONGOING, X, won_by
from super_tic_tac_toe.engine.state import GameState, IllegalMoveError, replay
from tests.helpers import BONUS_SEQ, NO_CHAIN_SEQ, find_game, play


def test_first_move_is_free_and_x_starts() -> None:
    state = GameState()
    assert state.to_move == X
    assert state.active_grid is None
    assert len(state.legal_moves()) == 81


def test_send_rule() -> None:
    state = play([(4, 2)])
    assert state.to_move == O
    assert state.active_grid == 2
    assert {g for g, _ in state.legal_moves()} == {2}


def test_winning_a_small_grid_grants_a_bonus_anywhere_open() -> None:
    state = play(BONUS_SEQ)
    assert state.grid_status[0] == won_by(X)
    assert state.phase == BONUS
    assert state.to_move == X
    assert state.active_grid is None
    assert {g for g, _ in state.legal_moves()} == set(range(1, 9))


def test_bonus_placement_applies_send_rule_and_closed_grid_frees_opponent() -> None:
    state = play(BONUS_SEQ + [(5, 0)])
    assert state.phase == NORMAL
    assert state.to_move == O
    assert state.active_grid is None
    assert all(g != 0 for g, _ in state.legal_moves())


def test_bonus_placement_after_send_rule_targets_cell() -> None:
    state = play(BONUS_SEQ + [(5, 3)])
    assert state.to_move == O
    assert state.active_grid == 3


def test_bonus_never_chains() -> None:
    state = play(NO_CHAIN_SEQ)
    assert state.grid_status[4] == won_by(X)
    assert state.phase == NORMAL
    assert state.to_move == O
    assert state.active_grid == 5


def test_without_bonus_rule_turn_passes() -> None:
    state = play(BONUS_SEQ, GameState(bonus_rule=False))
    assert state.phase == NORMAL
    assert state.to_move == O


def test_bonus_placement_can_win_the_game() -> None:
    def bonus_win(state: GameState) -> bool:
        return state.result in (won_by(X), won_by(O)) and state.history[-1][4] == BONUS

    state = find_game(bonus_win)
    winner = state.result - 1
    assert IS_LINE[state.big[winner]]
    assert state.legal_moves() == []


def test_drawn_small_grid_is_owned_by_nobody() -> None:
    state = find_game(lambda s: DRAW in s.grid_status)
    grid = state.grid_status.index(DRAW)
    assert state.bits[X][grid] | state.bits[O][grid] == FULL
    assert not state.big[X] >> grid & 1
    assert not state.big[O] >> grid & 1
    assert state.closed >> grid & 1


def test_board_draw_when_every_grid_closed_without_a_big_line() -> None:
    state = find_game(lambda s: s.result == DRAW, tries=20000)
    assert state.closed == FULL
    assert not IS_LINE[state.big[X]]
    assert not IS_LINE[state.big[O]]


def test_win_ends_game_immediately() -> None:
    state = find_game(lambda s: s.result != ONGOING and s.result != DRAW)
    assert state.legal_moves() == []
    assert state.illegal_reason(0, 0) == "the game is already over"


@pytest.mark.parametrize(
    ("history", "reason"),
    [
        ([(4, 2), (3, 0)], "must play in grid 2"),
        ([(4, 2), (2, 4), (4, 2)], "cell 2 of grid 4 is occupied"),
        (BONUS_SEQ + [(0, 5)], "grid 0 is closed"),
    ],
)
def test_replay_rejects_illegal_moves(history: list[tuple[int, int]], reason: str) -> None:
    with pytest.raises(IllegalMoveError) as error:
        replay(history)
    assert error.value.index == len(history) - 1
    assert error.value.reason == reason


def test_replay_matches_incremental_play() -> None:
    state = play(NO_CHAIN_SEQ)
    assert replay(state.placements()).to_dict() == state.to_dict()
