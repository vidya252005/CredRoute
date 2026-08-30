"""Resolve repo vs Docker layout for ML artifacts and env files."""

from pathlib import Path


def ml_dir() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "ml",
        here.parents[2] / "ml",
        here.parents[3] / "ml",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def env_files() -> tuple[str, ...]:
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / ".env",
        here.parents[2] / ".env",
        here.parents[3] / ".env",
    ]
    found: list[str] = []
    for path in candidates:
        resolved = str(path)
        if path.is_file() and resolved not in found:
            found.append(resolved)
    return tuple(found) or (".env",)
