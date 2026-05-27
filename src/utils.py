"""Small shared utilities for the project pipeline."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.config import AFTERNOON_END, AFTERNOON_START, MORNING_END, MORNING_START


def ensure_dir(path: str | Path) -> Path:
    """Create a directory and its parents if needed."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def time_to_minutes(time_int: int) -> int:
    """Convert an integer HMMSS or HHMMSS time into minutes after midnight."""
    time_text = str(int(time_int)).zfill(6)
    hour = int(time_text[:2])
    minute = int(time_text[2:4])
    second = int(time_text[4:])
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError(f"Invalid time value: {time_int}")
    return hour * 60 + minute


def is_in_day_session(time_int: int) -> bool:
    """Return whether a raw integer time belongs to the day trading session."""
    return MORNING_START <= time_int <= MORNING_END or AFTERNOON_START <= time_int <= AFTERNOON_END


def save_dict_as_csv(dictionary: Mapping[str, Any], filepath: str | Path) -> None:
    """Persist a flat dictionary as a two-column CSV table."""
    output_path = Path(filepath)
    ensure_dir(output_path.parent)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["metric", "value"])
        for key, value in dictionary.items():
            writer.writerow([key, value])


def flatten_params(params: Mapping[str, Any], parent_key: str = "", separator: str = "_") -> dict[str, Any]:
    """Flatten nested parameter dictionaries into a single dictionary."""
    flattened: dict[str, Any] = {}
    for key, value in params.items():
        compound_key = f"{parent_key}{separator}{key}" if parent_key else str(key)
        if isinstance(value, Mapping):
            flattened.update(flatten_params(value, compound_key, separator))
        else:
            flattened[compound_key] = value
    return flattened
