"""Search benchmarks for the report.

Run from the repo root: uv run python -m super_tic_tac_toe.analysis.benchmark [--positions N] [--depth D]
Writes docs/analysis/benchmark.md.
"""

import argparse
import random
import statistics
from pathlib import Path
from time import perf_counter

from super_tic_tac_toe.ai.search import SearchConfig, Searcher
from super_tic_tac_toe.engine.rules import ONGOING
from super_tic_tac_toe.engine.state import GameState

OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "analysis" / "benchmark.md"

CONFIGS = [
    ("Plain minimax", SearchConfig(alphabeta=False, ordering=False, tt=False)),
    ("Alpha-beta", SearchConfig(alphabeta=True, ordering=False, tt=False)),
    ("+ move ordering", SearchConfig(alphabeta=True, ordering=True, tt=False)),
    ("+ transposition table", SearchConfig(alphabeta=True, ordering=True, tt=True)),
]
BUDGETS_MS = [100, 250, 500, 1000, 2000, 4000]


def sample_positions(count: int, seed: int) -> list[GameState]:
    rng = random.Random(seed)
    positions: list[GameState] = []
    while len(positions) < count:
        state = GameState()
        for _ in range(rng.randrange(4, 40)):
            if state.result != ONGOING:
                break
            state.make(*rng.choice(state.legal_moves()))
        if state.result == ONGOING:
            positions.append(state)
    return positions


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def pruning(positions: list[GameState], depth: int, configs: list[tuple[str, SearchConfig]]) -> str:
    baseline = None
    rows = []
    for name, config in configs:
        nodes, times = [], []
        for state in positions:
            searcher = Searcher(config)
            start = perf_counter()
            searcher.search_depth(state, depth)
            times.append((perf_counter() - start) * 1000)
            nodes.append(searcher.nodes)
        mean_nodes = statistics.mean(nodes)
        baseline = baseline or mean_nodes
        rows.append([
            name,
            f"{mean_nodes:,.0f}",
            f"{statistics.mean(times):,.1f}",
            f"{100 * mean_nodes / baseline:.1f}%",
        ])
        print(f"  depth {depth} {name}: {mean_nodes:,.0f} nodes")
    return table(["Search", "Nodes per move", "Time per move (ms)", f"Nodes vs {configs[0][0].lower()}"], rows)


def depth_vs_budget(positions: list[GameState]) -> str:
    rows = []
    for budget in BUDGETS_MS:
        depths, nodes = [], []
        for state in positions:
            result = Searcher().search(state, 64, budget)
            depths.append(result.depth)
            nodes.append(result.nodes)
        rows.append([
            f"{budget:,}",
            f"{statistics.mean(depths):.1f}",
            f"{min(depths)} to {max(depths)}",
            f"{statistics.mean(nodes):,.0f}",
        ])
        print(f"  budget {budget} ms: depth {statistics.mean(depths):.1f}")
    return table(["Budget (ms)", "Mean depth", "Depth range", "Nodes per move"], rows)


def branching(games: int, seed: int) -> str:
    rows = []
    for name, bonus_rule in (("With bonus rule (this game)", True), ("Standard Ultimate Tic-Tac-Toe", False)):
        rng = random.Random(seed)
        factors: list[int] = []
        free_moves = lengths = 0
        for _ in range(games):
            state = GameState(bonus_rule)
            while state.result == ONGOING:
                moves = state.legal_moves()
                factors.append(len(moves))
                free_moves += state.active_grid is None
                state.make(*rng.choice(moves))
            lengths += len(state.history)
        rows.append([
            name,
            f"{statistics.mean(factors):.1f}",
            f"{100 * free_moves / len(factors):.1f}%",
            f"{lengths / games:.1f}",
        ])
    return table(["Rules", "Mean legal moves", "Positions with a free move", "Placements per game"], rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positions", type=int, default=20)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--deep", type=int, default=6, help="depth for the alpha-beta-only comparison")
    parser.add_argument("--games", type=int, default=1000, help="random games for the branching factor")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    positions = sample_positions(args.positions, args.seed)
    print("Pruning at equal depth")
    equal_depth = pruning(positions, args.depth, CONFIGS)
    deeper = pruning(positions, args.deep, CONFIGS[1:])
    print("Depth vs budget")
    budgets = depth_vs_budget(positions)
    print("Branching factor")
    factor = branching(args.games, args.seed)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        f"""# Search benchmarks

Generated by `uv run python -m super_tic_tac_toe.analysis.benchmark`. Positions are {args.positions} random mid-game
positions (4 to 40 random placements from the start, seed {args.seed}). One ply is one placement.

## Pruning at equal depth (depth {args.depth})

Every variant returns the same score as plain minimax; only the work differs.

{equal_depth}

## Alpha-beta variants at depth {args.deep}

Plain minimax is too slow to include at this depth.

{deeper}

## Depth reached vs time budget

Iterative deepening with every enhancement enabled. Hard difficulty uses a 2,000 ms budget.

{budgets}

## Effect of the bonus rule on branching factor

{args.games:,} uniformly random games per rule set. A bonus placement can go in any open small grid,
so it raises the number of legal moves at that ply.

{factor}
""",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
