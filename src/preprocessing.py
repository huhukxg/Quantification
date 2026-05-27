"""Cleaning and period splitting for day-session HSI futures data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import (
    AFTERNOON_END,
    AFTERNOON_START,
    COL_DATE,
    COL_TIME,
    MORNING_END,
    MORNING_START,
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    VAL_END,
    VAL_START,
)
from src.utils import save_dict_as_csv


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate date/time bars while retaining the last source row."""
    return df.drop_duplicates(subset=[COL_DATE, COL_TIME], keep="last").copy()


def filter_day_session(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only morning and regular afternoon day-session bars."""
    morning_mask = df[COL_TIME].between(MORNING_START, MORNING_END)
    afternoon_mask = df[COL_TIME].between(AFTERNOON_START, AFTERNOON_END)
    return df.loc[morning_mask | afternoon_mask].copy()


def flag_zero_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Mark bars with no reported traded volume."""
    flagged = df.copy()
    flagged["is_illiquid"] = flagged["volume"].fillna(0).le(0)
    return flagged


def validate_sessions(df: pd.DataFrame, min_bars: int = 300) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove day sessions shorter than the minimum bar threshold."""
    session_counts = (
        df.groupby(COL_DATE, sort=True)
        .size()
        .rename("bar_count")
        .reset_index()
    )
    session_counts["is_valid"] = session_counts["bar_count"].ge(min_bars)
    valid_dates = session_counts.loc[session_counts["is_valid"], COL_DATE]
    validated = df.loc[df[COL_DATE].isin(valid_dates)].copy()
    return validated, session_counts


def split_by_period(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split cleaned data into train, validation, and test date windows."""
    return {
        "train": df.loc[df[COL_DATE].between(TRAIN_START, TRAIN_END)].copy(),
        "val": df.loc[df[COL_DATE].between(VAL_START, VAL_END)].copy(),
        "test": df.loc[df[COL_DATE].between(TEST_START, TEST_END)].copy(),
    }


def get_sessions(df: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """Return cleaned rows grouped by trading date."""
    return {int(date): session.copy() for date, session in df.groupby(COL_DATE, sort=True)}


def preprocess_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply Stage 1 cleaning and save a compact cleaning summary."""
    rows_before_cleaning = len(df)
    deduplicated = remove_duplicates(df)
    duplicate_count_removed = rows_before_cleaning - len(deduplicated)

    day_session = filter_day_session(deduplicated)
    flagged = flag_zero_volume(day_session)
    cleaned, session_counts = validate_sessions(flagged)
    cleaned = cleaned.sort_values("datetime", kind="mergesort").reset_index(drop=True)

    summary = {
        "rows_before_cleaning": rows_before_cleaning,
        "rows_after_duplicate_removal": len(deduplicated),
        "duplicate_count_removed": duplicate_count_removed,
        "rows_after_day_session_filter": len(day_session),
        "rows_after_cleaning": len(cleaned),
        "sessions_before_validation": int(len(session_counts)),
        "sessions_after_validation": int(session_counts["is_valid"].sum()),
        "dropped_short_sessions": int((~session_counts["is_valid"]).sum()),
        "zero_volume_count": int(cleaned["is_illiquid"].sum()),
    }
    save_dict_as_csv(summary, Path("outputs") / "tables" / "data_cleaning_summary.csv")
    return cleaned, summary
