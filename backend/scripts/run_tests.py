#!/usr/bin/env python3
"""Run FastAPI tests. Coverage flags are used only when pytest-cov is installed."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "backend" / "tests"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(TESTS),
        "-q",
        f"--ignore={TESTS / 'load'}",
    ]
    try:
        import pytest_cov  # noqa: F401
    except ImportError:
        print(
            "pytest-cov is not installed; running without coverage.\n"
            "Install it with: pip install pytest-cov",
            file=sys.stderr,
        )
    else:
        cmd += ["--cov=app", "--cov-report=term-missing"]

    env = os.environ.copy()
    backend = str(ROOT / "backend")
    existing = env.get("PYTHONPATH", "")
    parts = [part for part in existing.split(os.pathsep) if part]
    if backend not in parts:
        env["PYTHONPATH"] = os.pathsep.join([backend, *parts]) if parts else backend

    return subprocess.call(cmd, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
