"""Pure signal functions for Stage 2 strategy logic."""

from __future__ import annotations

from src.regime import EXTREME, RANGE, TREND


def orb_signal(
    close_t: float,
    or_high: float | None,
    or_low: float | None,
    buffer_points: float,
    current_position: int,
) -> int:
    """Return an Opening Range Breakout target position."""
    if current_position != 0:
        return current_position
    if or_high is None or or_low is None:
        return 0
    if close_t > or_high + buffer_points:
        return 1
    if close_t < or_low - buffer_points:
        return -1
    return 0


def mr_signal(z_t: float, z_entry: float, z_exit: float, current_position: int) -> int:
    """Return a fair-value mean-reversion target position."""
    if current_position == 0:
        if z_t < -z_entry:
            return 1
        if z_t > z_entry:
            return -1
        return 0
    if current_position == 1:
        return 0 if z_t >= -z_exit else 1
    if current_position == -1:
        return 0 if z_t <= z_exit else -1
    return current_position


def hybrid_signal(
    regime: str,
    close_t: float,
    z_t: float,
    or_high: float | None,
    or_low: float | None,
    buffer_points: float,
    z_entry: float,
    z_exit: float,
    current_position: int,
    opening_window_passed: bool,
) -> int:
    """Choose ORB or MR logic from the current classified regime."""
    if regime == EXTREME:
        return 0
    if regime == TREND:
        if not opening_window_passed:
            return 0
        return orb_signal(close_t, or_high, or_low, buffer_points, current_position)
    if regime == RANGE:
        return mr_signal(z_t, z_entry, z_exit, current_position)
    raise ValueError(f"Unknown regime: {regime}")
