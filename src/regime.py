"""Regime classification from session features."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd

from src.features import compute_realized_volatility, compute_returns

EXTREME = "EXTREME"
TREND = "TREND"
RANGE = "RANGE"


def compute_extreme_vol_threshold(
    train_sessions: Mapping[int, pd.DataFrame] | Iterable[pd.DataFrame],
    rv_window: int,
    quantile: float,
) -> float:
    """Compute the training RV quantile used for the extreme-volatility filter."""
    sessions = train_sessions.values() if isinstance(train_sessions, Mapping) else train_sessions
    realized_volatility = []
    for session_df in sessions:
        rv = compute_realized_volatility(compute_returns(session_df), rv_window)
        realized_volatility.append(rv)

    if not realized_volatility:
        raise ValueError("At least one training session is required to compute the RV threshold.")

    rv_all = pd.concat(realized_volatility, ignore_index=True)
    valid_rv = rv_all.loc[rv_all.notna() & rv_all.ne(0)]
    if valid_rv.empty:
        raise ValueError("Training sessions contain no nonzero realized-volatility values.")
    return float(valid_rv.quantile(quantile))


def classify_regime(er_t: float, rv_t: float, er_threshold: float, extreme_vol_threshold: float) -> str:
    """Classify one observation as extreme, trend, or range."""
    if rv_t > extreme_vol_threshold:
        return EXTREME
    if er_t > er_threshold:
        return TREND
    return RANGE


def classify_regime_series(
    er: pd.Series,
    rv: pd.Series,
    er_threshold: float,
    extreme_vol_threshold: float,
) -> pd.Series:
    """Vectorize regime classification for aligned ER and RV series."""
    regimes = np.select(
        [rv.gt(extreme_vol_threshold), er.gt(er_threshold)],
        [EXTREME, TREND],
        default=RANGE,
    )
    return pd.Series(regimes, index=er.index, name="regime")
