#!/usr/bin/env python3
"""CLI: PYTHONPATH=backend python3 backend/scripts/generate_scale_data.py --mode quick|full"""

from __future__ import annotations

import argparse

from app.services.scale_data import generate_scale_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    args = parser.parse_args()
    print(generate_scale_data(args.mode))


if __name__ == "__main__":
    main()
