"""Feature engineering for a single cleaned intraday session."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


def compute_returns(session_df: pd.DataFrame) -> pd.Series:
    """Compute close-to-close percentage returns within one session."""
    return session_df["close"].pct_change().fillna(0)


def compute_opening_range(session_df: pd.DataFrame, opening_window: int) -> tuple[float | None, float | None]:
    """Return the high and low of the first opening-window bars."""
    if len(session_df) < opening_window:
        return None, None

    opening_bars = session_df.iloc[:opening_window]
    return float(opening_bars["high"].max()), float(opening_bars["low"].min())


def compute_vwap(session_df: pd.DataFrame) -> pd.Series:
    """Compute cumulative VWAP with an expanding close mean fallback."""
    close = session_df["close"]
    volume = session_df["volume"].fillna(0)
    cumulative_volume = volume.cumsum()
    cumulative_notional = close.mul(volume).cumsum()
    expanding_mean = close.expanding(min_periods=1).mean()
    vwap = cumulative_notional.div(cumulative_volume.where(cumulative_volume.ne(0)))
    return vwap.fillna(expanding_mean)


def compute_rolling_fair_value(session_df: pd.DataFrame, window: int) -> pd.Series:
    """Compute rolling close mean, using early bars as available."""
    return session_df["close"].rolling(window, min_periods=1).mean()


def compute_zscore(
    close: pd.Series,
    fair_value: pd.Series,
    window: int,
    min_std_threshold: float = 5,
) -> pd.Series:
    """Compute fair-value deviation z-scores with low-variance bars suppressed."""
    rolling_std = close.rolling(window, min_periods=window).std()
    valid_std = rolling_std.ge(min_std_threshold)
    z_score = close.sub(fair_value).div(rolling_std)
    return z_score.where(valid_std, 0).replace([np.inf, -np.inf], 0).fillna(0)


def compute_efficiency_ratio(close: pd.Series, window: int) -> pd.Series:
    """Compute Kaufman-style efficiency ratio for a close-price series."""
    net_change = close.sub(close.shift(window)).abs()
    path_change = close.diff().abs().rolling(window, min_periods=window).sum()
    efficiency_ratio = net_change.div(path_change.where(path_change.ne(0)))
    return efficiency_ratio.replace([np.inf, -np.inf], 0).fillna(0)


def compute_realized_volatility(returns: pd.Series, window: int) -> pd.Series:
    """Compute raw rolling realized volatility from intraday returns."""
    squared_returns = returns.pow(2)
    realized_volatility = squared_returns.rolling(window, min_periods=window).sum().pow(0.5)
    realized_volatility = realized_volatility.fillna(0)
    realized_volatility.iloc[:window] = 0
    return realized_volatility


def compute_session_features(session_df: pd.DataFrame, params: Mapping[str, Any]) -> pd.DataFrame:
    """Attach Stage 2 features to one cleaned session DataFrame."""
    opening_window = int(params.get("opening_window", 30))
    fair_value_window = int(params.get("rolling_window", 60))
    er_window = int(params.get("er_window", 60))
    rv_window = int(params.get("rv_window", 60))
    use_vwap = bool(params.get("use_vwap", True))
    min_std_threshold = float(params.get("min_std_threshold", 5))

    features = session_df.copy()
    features["returns"] = compute_returns(features)
    features["vwap"] = compute_vwap(features)
    features["rolling_fair_value"] = compute_rolling_fair_value(features, fair_value_window)
    features["fair_value"] = features["vwap"] if use_vwap else features["rolling_fair_value"]
    features["z_score"] = compute_zscore(
        features["close"],
        features["fair_value"],
        fair_value_window,
        min_std_threshold,
    )
    features["ER"] = compute_efficiency_ratio(features["close"], er_window)
    features["RV"] = compute_realized_volatility(features["returns"], rv_window)

    or_high, or_low = compute_opening_range(features, opening_window)
    features.attrs["OR_high"] = or_high
    features.attrs["OR_low"] = or_low
    return features
