"""
Pure computation functions — no database calls, no Dash imports.
Callbacks call these; FastAPI endpoints will wrap these when migrating to React.
"""
import numpy as np
import pandas as pd

# Matches RF_ANNUAL in sharpe.py exactly
RF_ANNUAL: float = 0.05
RF_LOG: float = np.log(1 + RF_ANNUAL)          # annualised log risk-free rate ≈ 0.04879
RF_DAILY: float = RF_LOG / 252                  # daily log risk-free rate ≈ 0.0001936


def compute_treynor(annualised_log_return: float, beta: float) -> float | None:
    """
    Treynor = (annualised_excess_return) / beta.
    Consistent with sharpe.py: excess uses log rf, not simple rf.
    Returns None for near-zero beta to avoid division instability.
    """
    if abs(beta) < 0.05:
        return None
    return (annualised_log_return - RF_LOG) / beta


def build_sector_country_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot sector × country count matrix for the heatmap."""
    if df.empty:
        return pd.DataFrame()
    pivot = df.pivot_table(
        index="country", columns="sector", values="count", fill_value=0
    )
    # Sort by row/col totals for readability
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    pivot = pivot[pivot.sum(axis=0).sort_values(ascending=False).index]
    return pivot


def format_marketcap(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if np.isnan(v):
        return "—"
    if v >= 1e12:
        return f"${v / 1e12:.1f}T"
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.0f}"
