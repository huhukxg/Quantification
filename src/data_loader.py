"""Dataset loading and datetime preparation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_TIME, COL_VOLUME

REQUIRED_COLUMNS = [COL_DATE, COL_TIME, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME]
COLUMN_RENAMES = {
    COL_OPEN: "open",
    COL_HIGH: "high",
    COL_LOW: "low",
    COL_CLOSE: "close",
    COL_VOLUME: "volume",
}


def load_raw_data(filepath: str | Path) -> pd.DataFrame:
    """Read the raw HSI futures CSV and validate its required columns."""
    data_path = Path(filepath)
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    df = pd.read_csv(data_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    return df


def parse_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """Add a parsed datetime column from integer date and time columns."""
    parsed = df.copy()
    date_text = parsed[COL_DATE].astype("int64").astype(str).str.zfill(8)
    time_text = parsed[COL_TIME].astype("int64").astype(str).str.zfill(6)
    parsed["datetime"] = pd.to_datetime(date_text + time_text, format="%Y%m%d%H%M%S", errors="raise")
    return parsed


def load_and_prepare_data(filepath: str | Path) -> pd.DataFrame:
    """Load raw data, normalize OHLCV names, add datetime, and sort rows."""
    df = load_raw_data(filepath)
    prepared = parse_datetime(df).rename(columns=COLUMN_RENAMES)
    return prepared.sort_values("datetime", kind="mergesort").reset_index(drop=True)
