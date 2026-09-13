"""Read/write the Indian training table without requiring a working PyArrow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PARQUET_SUFFIX = ".parquet"
CSV_SUFFIX = ".csv"


def table_paths(path: Path) -> tuple[Path, Path]:
    base = path.with_suffix("")
    return base.with_suffix(PARQUET_SUFFIX), base.with_suffix(CSV_SUFFIX)


def write_table(frame: pd.DataFrame, path: Path) -> Path:
    parquet_path, csv_path = table_paths(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame.to_parquet(parquet_path, index=False)
        return parquet_path
    except Exception as exc:  # noqa: BLE001 — pyarrow ABI breaks are common on mixed conda/pip
        print(f"Parquet write failed ({type(exc).__name__}: {exc}). Falling back to CSV.")
        frame.to_csv(csv_path, index=False)
        return csv_path


def read_table(path: Path) -> pd.DataFrame:
    parquet_path, csv_path = table_paths(path)
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception as exc:  # noqa: BLE001
            print(f"Parquet read failed ({type(exc).__name__}: {exc}). Trying CSV.")
    if csv_path.exists():
        return pd.read_csv(csv_path)
    raise FileNotFoundError(f"No parquet or CSV dataset at {parquet_path} or {csv_path}")
