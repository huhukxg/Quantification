"""Exploratory strategy definitions kept outside the original project source."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyCandidate:
    """One exploratory parameter candidate."""

    strategy: str
    variant: str
    family: str
    params_id: str
    params: dict[str, Any]


ORB_FILTERED_FAMILY = "A_ORB_FILTERED_HYBRID"
ORB_ONLY_FAMILY = "B_ORB_ONLY_IMPROVED"
STRICT_MR_FAMILY = "C_STRICT_MR"
LOW_TURNOVER_FAMILY = "D_LOW_TURNOVER_HYBRID"
DIRECTIONAL_FAMILY = "E_DIRECTIONAL_LONG_FILTERS"


def variant_family(variant: str) -> str:
    """Return a high-level family label for plotting and summaries."""
    if variant.startswith("ORB_FILTERED_HYBRID"):
        return ORB_FILTERED_FAMILY
    if variant.startswith("ORB_ONLY"):
        return ORB_ONLY_FAMILY
    if variant.startswith("STRICT_MR"):
        return STRICT_MR_FAMILY
    if variant.startswith("LOW_TURNOVER"):
        return LOW_TURNOVER_FAMILY
    if variant.startswith(("LONG_OR_FLAT", "LONG_ONLY_ORB", "ORB_TO_CLOSE", "EXTREME_TREND")):
        return DIRECTIONAL_FAMILY
    return "OTHER"
