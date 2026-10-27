from super_tic_tac_toe.engine.state import Placement

EXACT, LOWER, UPPER = 0, 1, 2

MATE = 100_000
MATE_BOUND = MATE - 1000


def _to_table(score: int, ply: int) -> int:
    if score > MATE_BOUND:
        return score + ply
    if score < -MATE_BOUND:
        return score - ply
    return score


def _from_table(score: int, ply: int) -> int:
    if score > MATE_BOUND:
        return score - ply
    if score < -MATE_BOUND:
        return score + ply
    return score


class TranspositionTable:
    """Zobrist-keyed cache of (depth, score, bound, best move).

    Mate scores are stored relative to the node so they stay correct at any ply.
    """

    def __init__(self, max_entries: int = 1_000_000) -> None:
        self.max_entries = max_entries
        self._entries: dict[int, tuple[int, int, int, Placement | None]] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def probe(self, key: int, ply: int) -> tuple[int, int, int, Placement | None] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        depth, score, flag, move = entry
        return depth, _from_table(score, ply), flag, move

    def store(self, key: int, depth: int, score: int, flag: int, move: Placement | None, ply: int) -> None:
        if len(self._entries) >= self.max_entries:
            self._entries.clear()
        self._entries[key] = (depth, _to_table(score, ply), flag, move)
