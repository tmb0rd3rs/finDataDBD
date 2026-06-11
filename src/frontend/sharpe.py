import sys
sys.path.insert(0, '/Users/toniborders/PycharmProjects/MonteCarloSimStockPrices')
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from app.client.postgres_client_refactored import PricingRepository

# ── Config ────────────────────────────────────────────────────────────────────
RF_ANNUAL     = 0.05
WINDOW        = 60
START_DATE    = datetime.datetime(2020, 2, 6)
END_DATE      = datetime.datetime.now()
TICKERS       = ['SCCO', 'IBM', 'TRI', 'XOM', 'AZN', 'JNJ']
MARKET_TICKER = 'SPY'        # benchmark for Treynor beta
DATA_SOURCE   = 'Yahoo'


# ── Data fetching ─────────────────────────────────────────────────────────────

def get_data(tickers: list[str]) -> pd.DataFrame:
    pricing_repo = PricingRepository()
    frames = [
        pricing_repo.get_stock_data(t, DATA_SOURCE, START_DATE, END_DATE)
        for t in tickers
    ]
    valid = [df for df in frames if df is not None]
    return pd.concat(valid) if valid else pd.DataFrame()


def make_price_matrix(df: pd.DataFrame):
    """Pivot OHLCV dataframe → (closes array, tickers, dates)."""
    if df.index.name == "date":
        pivot = df.pivot(columns="ticker", values="Close")
    else:
        pivot = df.pivot(index="date", columns="ticker", values="Close")
    pivot = pivot.sort_index().dropna()
    return pivot.to_numpy(), pivot.columns.tolist(), pivot.index.tolist()


# ── Returns ───────────────────────────────────────────────────────────────────

def compute_log_returns(closes: np.ndarray) -> np.ndarray:
    """Log returns from a closes array. Shape (T-1, N) or (T-1,) for 1-D input."""
    return np.log(closes[1:] / closes[:-1])


# ── Full-period ratios ────────────────────────────────────────────────────────

def sharpe_ratio(log_returns: np.ndarray, rf_annual: float = RF_ANNUAL) -> np.ndarray:
    """
    Annualised Sharpe ratio per column.
    Sharpe = (mean_excess / σ_excess) × √252
    """
    rf_daily = np.log(1 + rf_annual) / 252
    excess   = log_returns - rf_daily
    return (excess.mean(axis=0) / excess.std(axis=0, ddof=1)) * np.sqrt(252)


def sortino_ratio(log_returns: np.ndarray, rf_annual: float = RF_ANNUAL) -> np.ndarray:
    """
    Annualised Sortino ratio per column.
    Uses the downside semi-deviation (RMS of negative excess returns only),
    which gives a higher ratio than Sharpe for positively-skewed return streams.

    Sortino = (mean_excess / σ_downside) × √252
    """
    rf_daily = np.log(1 + rf_annual) / 252
    excess   = log_returns - rf_daily
    mean     = excess.mean(axis=0)

    # Zero out positive days; RMS of what remains = downside semi-deviation
    downside_sq  = np.where(excess < 0, excess ** 2, 0.0)
    downside_std = np.sqrt(downside_sq.mean(axis=0))

    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(downside_std > 0,
                        (mean / downside_std) * np.sqrt(252),
                        np.nan)


def treynor_ratio(
    log_returns: np.ndarray,
    market_returns: np.ndarray,
    rf_annual: float = RF_ANNUAL,
) -> np.ndarray:
    """
    Annualised Treynor ratio per column.
    Replaces σ (total risk) with β (systematic risk vs. the market benchmark).
    Useful for comparing well-diversified portfolios where idiosyncratic risk
    has been reduced; less informative for individual stocks in isolation.

    Treynor = (mean_excess / β) × 252
    where β = Cov(asset_excess, market_excess) / Var(market_excess)

    Parameters
    ----------
    log_returns     : (T, N) – asset log-returns
    market_returns  : (T,)   – benchmark log-returns aligned to the same dates
    """
    rf_daily      = np.log(1 + rf_annual) / 252
    excess        = log_returns - rf_daily          # (T, N)
    market_excess = market_returns - rf_daily       # (T,)

    market_var = np.var(market_excess, ddof=1)
    betas = np.array([
        np.cov(excess[:, i], market_excess, ddof=1)[0, 1] / market_var
        for i in range(excess.shape[1])
    ])
    mean = excess.mean(axis=0)

    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.abs(betas) > 1e-4, (mean / betas) * 252, np.nan)


# ── Rolling ratios ────────────────────────────────────────────────────────────

def rolling_sharpe(
    log_returns: np.ndarray,
    window: int = WINDOW,
    rf_annual: float = RF_ANNUAL,
) -> np.ndarray:
    """
    Rolling Sharpe ratio. Returns (T, N) array; NaN during the burn-in period.

    Bug-fix vs. original: the np.where block that overwrote all loop values
    with the last window's mean/std has been removed.
    """
    if log_returns.ndim == 1:
        log_returns = log_returns[:, np.newaxis]
    rf_daily = np.log(1 + rf_annual) / 252
    excess   = log_returns - rf_daily
    T, N     = excess.shape
    out      = np.full((T, N), np.nan)

    for i in range(window, T + 1):
        w = excess[i - window: i]          # (window, N)
        s = w.std(axis=0, ddof=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i - 1] = np.where(s > 0, (w.mean(axis=0) / s) * np.sqrt(252), np.nan)

    return out


def rolling_sortino(
    log_returns: np.ndarray,
    window: int = WINDOW,
    rf_annual: float = RF_ANNUAL,
) -> np.ndarray:
    """
    Rolling Sortino ratio. Returns (T, N) array; NaN during burn-in.
    Shares the same loop structure as rolling_sharpe, differing only
    in the denominator (downside semi-deviation instead of total σ).
    """
    if log_returns.ndim == 1:
        log_returns = log_returns[:, np.newaxis]
    rf_daily = np.log(1 + rf_annual) / 252
    excess   = log_returns - rf_daily
    T, N     = excess.shape
    out      = np.full((T, N), np.nan)

    for i in range(window, T + 1):
        w            = excess[i - window: i]
        mean         = w.mean(axis=0)
        downside_sq  = np.where(w < 0, w ** 2, 0.0)
        ds           = np.sqrt(downside_sq.mean(axis=0))
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i - 1] = np.where(ds > 0, (mean / ds) * np.sqrt(252), np.nan)

    return out


def rolling_treynor(
    log_returns: np.ndarray,
    market_returns: np.ndarray,
    window: int = WINDOW,
    rf_annual: float = RF_ANNUAL,
) -> np.ndarray:
    """
    Rolling Treynor ratio. Returns (T, N) array; NaN during burn-in.
    Beta is re-estimated in each rolling window so it reflects the
    prevailing market sensitivity rather than the full-period beta.
    """
    if log_returns.ndim == 1:
        log_returns = log_returns[:, np.newaxis]
    rf_daily     = np.log(1 + rf_annual) / 252
    excess       = log_returns - rf_daily
    mkt_excess   = market_returns - rf_daily
    T, N         = excess.shape
    out          = np.full((T, N), np.nan)

    for i in range(window, T + 1):
        w_asset = excess[i - window: i]    # (window, N)
        w_mkt   = mkt_excess[i - window: i]
        mkt_var = np.var(w_mkt, ddof=1)
        if mkt_var < 1e-10:
            continue
        mean  = w_asset.mean(axis=0)
        betas = np.array([
            np.cov(w_asset[:, j], w_mkt, ddof=1)[0, 1] / mkt_var
            for j in range(N)
        ])
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i - 1] = np.where(np.abs(betas) > 1e-4,
                                   (mean / betas) * 252, np.nan)

    return out


# ── Portfolio ─────────────────────────────────────────────────────────────────

def portfolio_log_returns(
    log_returns: np.ndarray,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """
    Compute portfolio log-returns from individual asset log-returns.

    Converts log → simple returns, takes the weighted sum, then converts back.
    This is exact (no small-return approximation).

    Parameters
    ----------
    log_returns : (T, N)
    weights     : (N,) – will be normalised to sum to 1.
                  Defaults to equal-weight.

    Returns
    -------
    (T,) portfolio log-return series
    """
    if weights is None:
        weights = np.ones(log_returns.shape[1]) / log_returns.shape[1]
    weights = np.asarray(weights, dtype=float)
    weights /= weights.sum()
    simple_portfolio = np.expm1(log_returns) @ weights   # weighted simple returns
    return np.log1p(simple_portfolio)                     # back to log-returns


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_results(
    dates: list,
    log_returns: np.ndarray,
    roll_sharpe: np.ndarray,
    roll_sortino: np.ndarray,
    roll_treynor: np.ndarray | None,
    ticker_names: list[str],
    port_log_rets: np.ndarray | None = None,
    market_log_rets: np.ndarray | None = None,
):
    """
    2 × 2 dashboard:
      [0,0]  Cumulative Returns        [0,1]  Rolling Sharpe
      [1,0]  Rolling Sortino           [1,1]  Rolling Treynor

    The portfolio is overlaid as a thick dashed black line on every panel.
    Final metric values are annotated in the bottom-right of each ratio chart.
    """
    dates_str  = [ts.strftime('%Y-%m-%d') for ts in dates]
    cumulative = np.exp(np.cumsum(log_returns, axis=0))
    colors     = plt.cm.tab10.colors

    # Pre-compute portfolio rolling series
    port_cum, port_roll_sh, port_roll_so, port_roll_tr = (None,) * 4
    if port_log_rets is not None:
        port_cum     = np.exp(np.cumsum(port_log_rets))
        port_roll_sh = rolling_sharpe(port_log_rets[:, np.newaxis])[:, 0]
        port_roll_so = rolling_sortino(port_log_rets[:, np.newaxis])[:, 0]
        if market_log_rets is not None:
            port_roll_tr = rolling_treynor(
                port_log_rets[:, np.newaxis], market_log_rets
            )[:, 0]

    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle("Risk-Adjusted Return Dashboard", fontsize=14, fontweight="bold")

    def _plot(ax, matrix, port_series, title, ylabel, zero_line=True):
        for i, name in enumerate(ticker_names):
            ax.plot(dates_str, matrix[:, i],
                    label=name, color=colors[i % len(colors)],
                    linewidth=1.2, alpha=0.85)
        if port_series is not None:
            ax.plot(dates_str, port_series,
                    label="Portfolio", color="black",
                    linewidth=2.2, linestyle="--")
        if zero_line:
            ax.axhline(0, color="grey", linewidth=0.7, linestyle=":")
        ax.set_title(title, fontsize=11, fontweight="semibold")
        ax.set_ylabel(ylabel, fontsize=9)
        ax.legend(fontsize=7, ncol=2)
        ax.tick_params(axis="x", labelsize=7)
        ax.tick_params(axis="y", labelsize=8)

    def _annotate_final(ax, matrix, port_series, ticker_names, fmt=".3f"):
        """Print the last non-NaN value for each series in the chart margin."""
        lines, labels = ax.get_legend_handles_labels()
        finals = []
        for i, name in enumerate(ticker_names):
            col   = matrix[:, i]
            valid = col[~np.isnan(col)]
            finals.append(f"{name}: {valid[-1]:{fmt}}" if len(valid) else f"{name}: n/a")
        if port_series is not None:
            valid = port_series[~np.isnan(port_series)]
            finals.append(f"Portfolio: {valid[-1]:{fmt}}" if len(valid) else "Portfolio: n/a")
        ax.text(0.99, 0.02, "  |  ".join(finals),
                transform=ax.transAxes, fontsize=7,
                ha="right", va="bottom", color="dimgrey",
                bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"))

    # ── [0,0] Cumulative returns ───────────────────────────────────────────
    _plot(axes[0, 0], cumulative, port_cum,
          "Cumulative Returns", "Growth of $1", zero_line=False)

    # ── [0,1] Rolling Sharpe ──────────────────────────────────────────────
    _plot(axes[0, 1], roll_sharpe, port_roll_sh,
          f"Rolling Sharpe ({WINDOW}d)", "Sharpe Ratio")
    _annotate_final(axes[0, 1], roll_sharpe, port_roll_sh, ticker_names)

    # ── [1,0] Rolling Sortino ─────────────────────────────────────────────
    _plot(axes[1, 0], roll_sortino, port_roll_so,
          f"Rolling Sortino ({WINDOW}d)", "Sortino Ratio")
    _annotate_final(axes[1, 0], roll_sortino, port_roll_so, ticker_names)

    # ── [1,1] Rolling Treynor ─────────────────────────────────────────────
    if roll_treynor is not None:
        _plot(axes[1, 1], roll_treynor, port_roll_tr,
              f"Rolling Treynor ({WINDOW}d)", "Treynor Ratio")
        _annotate_final(axes[1, 1], roll_treynor, port_roll_tr,
                        ticker_names, fmt=".4f")
    else:
        axes[1, 1].text(0.5, 0.5,
            "Market data unavailable\n(Treynor not computed)",
            ha="center", va="center", transform=axes[1, 1].transAxes,
            color="grey", fontsize=10)
        axes[1, 1].set_title("Rolling Treynor", fontsize=11)

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Fetch asset + market data
    data       = get_data(TICKERS)
    market_df  = get_data([MARKET_TICKER])

    # 2. Reshape into close arrays
    closes, tickers, dates = make_price_matrix(data)

    market_log_rets = None
    if not market_df.empty:
        mkt_closes, _, mkt_dates = make_price_matrix(market_df)
        # align market dates to asset dates (both are weekly-day series)
        mkt_date_idx = {d: i for i, d in enumerate(mkt_dates)}
        asset_indices = [mkt_date_idx[d] for d in dates if d in mkt_date_idx]
        if len(asset_indices) >= len(dates) - 5:         # allow a few missing days
            mkt_aligned     = mkt_closes[asset_indices, 0]
            market_log_rets = compute_log_returns(mkt_aligned[:, np.newaxis])[:, 0]

    # 3. Compute log-returns
    log_rets = compute_log_returns(closes)               # (T, N)

    # 4. Portfolio (equal-weight; swap weights array here for custom allocation)
    port_weights  = np.ones(len(tickers)) / len(tickers)
    port_log_rets = portfolio_log_returns(log_rets, port_weights)

    # 5. Full-period ratios ──────────────────────────────────────────────────
    sharpes  = sharpe_ratio(log_rets)
    sortinos = sortino_ratio(log_rets)

    header = f"\n{'Ticker':<8}{'Sharpe':>9}{'Sortino':>10}"
    if market_log_rets is not None:
        treynors = treynor_ratio(log_rets, market_log_rets)
        print(header + f"{'Treynor':>11}")
        for t, sh, so, tr in zip(tickers, sharpes, sortinos, treynors):
            print(f"{t:<8}{sh:>9.3f}{so:>10.3f}{tr:>11.4f}")
    else:
        treynors = None
        print(header)
        for t, sh, so in zip(tickers, sharpes, sortinos):
            print(f"{t:<8}{sh:>9.3f}{so:>10.3f}")

    # Portfolio summary
    p_sh = sharpe_ratio(port_log_rets[:, np.newaxis])[0]
    p_so = sortino_ratio(port_log_rets[:, np.newaxis])[0]
    print(f"\n{'Portfolio':<8}{p_sh:>9.3f}{p_so:>10.3f}", end="")
    if market_log_rets is not None:
        p_tr = treynor_ratio(port_log_rets[:, np.newaxis], market_log_rets)[0]
        print(f"{p_tr:>11.4f}")
    else:
        print()

    # 6. Rolling ratios ──────────────────────────────────────────────────────
    roll_sh = rolling_sharpe(log_rets)
    roll_so = rolling_sortino(log_rets)
    roll_tr = rolling_treynor(log_rets, market_log_rets) if market_log_rets is not None else None

    # 7. Plot
    plot_results(
        dates[1:],           # one fewer date due to differencing
        log_rets,
        roll_sh, roll_so, roll_tr,
        tickers,
        port_log_rets=port_log_rets,
        market_log_rets=market_log_rets,
    )


if __name__ == "__main__":
    main()
