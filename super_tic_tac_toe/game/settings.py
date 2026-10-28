import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Literal

Mode = Literal["competitive", "time_based", "free"]
Difficulty = Literal["easy", "medium", "hard"]
Theme = Literal["light", "dark"]

MODES: tuple[Mode, ...] = ("competitive", "time_based", "free")
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
THEMES: tuple[Theme, ...] = ("light", "dark")

COMPETITIVE_PRESETS = (5, 10, 15, 30)
COMPETITIVE_RANGE = (3, 120)
TIME_BASED_PRESETS = (3, 5, 10, 15)
TIME_BASED_RANGE = (1, 60)


@dataclass(frozen=True)
class Settings:
    mode: Mode = "competitive"
    competitive_seconds: int = 10
    time_based_minutes: int = 10
    difficulty: Difficulty = "medium"
    theme: Theme = "light"


DEFAULTS = Settings()

_VALID = {
    "mode": lambda v: v in MODES,
    "competitive_seconds": lambda v: type(v) is int and COMPETITIVE_RANGE[0] <= v <= COMPETITIVE_RANGE[1],
    "time_based_minutes": lambda v: type(v) is int and TIME_BASED_RANGE[0] <= v <= TIME_BASED_RANGE[1],
    "difficulty": lambda v: v in DIFFICULTIES,
    "theme": lambda v: v in THEMES,
}


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "SuperTicTacToe" / "settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SuperTicTacToe" / "settings.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "super-tic-tac-toe" / "settings.json"


def load(path: Path | None = None) -> Settings:
    """Saved settings; any missing or invalid field falls back to its default."""
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULTS
    if not isinstance(data, dict):
        return DEFAULTS
    values = {
        f.name: data[f.name] if f.name in data and _VALID[f.name](data[f.name]) else getattr(DEFAULTS, f.name)
        for f in fields(Settings)
    }
    return Settings(**values)


def save(settings: Settings, path: Path | None = None) -> None:
    target = path or settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    except OSError:
        pass
