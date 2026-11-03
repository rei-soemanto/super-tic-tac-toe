"""AI-vs-AI matches for the report and for evaluation-weight tuning.

Run from the repo root: uv run python -m super_tic_tac_toe.analysis.selfplay [--games N] [--hard-ms MS]
Writes docs/analysis/selfplay.md.
"""

import argparse
import random
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from super_tic_tac_toe.ai.agent import Difficulty, choose_turn
from super_tic_tac_toe.ai.evaluate import Evaluator, Weights
from super_tic_tac_toe.engine.rules import DRAW, O, ONGOING, X
from super_tic_tac_toe.engine.state import GameState

OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "analysis" / "selfplay.md"
OPENING_PLIES = 2


@dataclass
class Player:
    name: str
    difficulty: Difficulty
    budget_ms: float | None = None
    evaluator: Evaluator = field(default_factory=Evaluator)
    time_aware: bool = False


@dataclass
class Tally:
    wins: int = 0
    draws: int = 0
    losses: int = 0

    def add(self, outcome: int) -> None:
        if outcome > 0:
            self.wins += 1
        elif outcome < 0:
            self.losses += 1
        else:
            self.draws += 1

    @property
    def score(self) -> float:
        games = self.wins + self.draws + self.losses
        return (self.wins + 0.5 * self.draws) / games if games else 0.0


def random_opening(rng: random.Random) -> GameState:
    state = GameState()
    for _ in range(OPENING_PLIES):
        state.make(*rng.choice(state.legal_moves()))
    return state


def play(players: dict[int, Player], state: GameState, game_ms: float | None = None) -> int:
    """Plays to the end; returns the winning side, or -1 for a draw.

    With `game_ms`, both sides share one simulated game clock charged with real search time,
    and the side with more small grids won wins when it runs out (Time-based mode).
    """
    left = game_ms
    while state.result == ONGOING:
        player = players[state.to_move]
        budget = player.budget_ms
        if left is not None:
            empty = sum(state.empty_cells(g).bit_count() for g in state.open_grids())
            share = left / max(10, empty / 2)
            budget = min(budget, share) if budget else share
        turn = choose_turn(
            state,
            player.difficulty,
            budget,
            left if player.time_aware else None,
            player.evaluator,
        )
        if left is not None:
            left -= turn.time_ms
            if left <= 0:
                x, o = state.big[X].bit_count(), state.big[O].bit_count()
                return X if x > o else O if o > x else -1
    return -1 if state.result == DRAW else state.result - 1


def match(a: Player, b: Player, games: int, seed: int, game_ms: float | None = None) -> Tally:
    rng = random.Random(seed)
    tally = Tally()
    for game in range(games):
        a_side = X if game % 2 == 0 else O
        players = {a_side: a, 1 - a_side: b}
        winner = play(players, random_opening(rng), game_ms)
        tally.add(0 if winner == -1 else 1 if winner == a_side else -1)
    return tally


def row(name: str, tally: Tally) -> str:
    return f"| {name} | {tally.wins} | {tally.draws} | {tally.losses} | {100 * tally.score:.0f}% |"


HEADER = "| Match | Wins | Draws | Losses | Score |\n|---|---|---|---|---|"


def run_section(title: str, pairs: list[tuple[str, Callable[[], Tally]]]) -> str:
    print(title)
    lines = [HEADER]
    for name, run in pairs:
        tally = run()
        print(f"  {name}: {tally}")
        lines.append(row(name, tally))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--hard-ms", type=float, default=300)
    parser.add_argument("--clock-ms", type=float, default=6000, help="shared clock for the time-aware match")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    easy = Player("Easy", "easy")
    medium = Player("Medium", "medium")
    hard = Player("Hard", "hard", args.hard_ms)

    difficulty = run_section(
        "Difficulty levels",
        [
            (f"{a.name} vs {b.name}", lambda a=a, b=b: match(a, b, args.games, args.seed))
            for a, b in ((medium, easy), (hard, medium), (hard, easy))
        ],
    )

    default = Weights()
    variants = {
        "Big-grid two-in-a-row 300": replace(default, big_two=300),
        "Bonus threat 120": replace(default, bonus_threat=120),
        "Small two-in-a-row 20": replace(default, small_two=20),
        "Grid won 150": replace(default, grid_won=150),
    }
    tuning = run_section(
        "Weight tuning",
        [
            (
                f"{name} vs default",
                lambda w=w: match(Player("variant", "medium", evaluator=Evaluator(w)), medium, args.games, args.seed),
            )
            for name, w in variants.items()
        ],
    )

    aware = Player("Time-aware", "hard", args.hard_ms, time_aware=True)
    plain = Player("Normal", "hard", args.hard_ms)
    time_aware = run_section(
        "Time-aware evaluation",
        [("Time-aware vs normal", lambda: match(aware, plain, args.games, args.seed, args.clock_ms))],
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        f"""# Self-play results

Generated by `uv run python -m super_tic_tac_toe.analysis.selfplay`. Each match is {args.games} games with colours
alternated and the first {OPENING_PLIES} placements random (seed {args.seed}) so games differ.
Hard uses a {args.hard_ms:.0f} ms budget per placement here (2,000 ms in the real game) to keep the
run short. Results are from the first player's point of view; score counts a draw as half a win.

## Difficulty levels

{difficulty}

## Evaluation weight tuning

Medium (depth 4) with one weight changed, against Medium with the default weights. A variant is
only worth adopting if it also wins a larger confirmation match with a different seed.

{tuning}

## Time-aware evaluation (Time-based mode)

Both sides are Hard on a shared {args.clock_ms / 1000:.0f} s simulated game clock charged with real
search time; when it runs out, more small grids won wins. The time-aware side weights the small-grid
difference more heavily as its remaining time drops below 60 s.

{time_aware}
""",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
