"""
All database reads for the dashboard.
No computation here — raw data in, DataFrames out.
Callbacks call these functions; the functions call nothing but the DB.
"""
import pandas as pd
from sqlalchemy import text

from .db import get_engine


# ── Screener ──────────────────────────────────────────────────────────────────

def fetch_screener_data(filters: dict | None = None) -> pd.DataFrame:
    """
    One row per security with latest predicted price, growth, Sharpe,
    realised volatility, and most-recent EV/EBITDA from fundamentals.
    """
    query = """
    WITH pred_latest AS (
        SELECT DISTINCT ON (securid)
            securid, predicted_close, confidence_interval, forecast_date
        FROM predictpricing
        ORDER BY securid, forecast_date DESC
    ),
    pred_first AS (
        SELECT DISTINCT ON (securid)
            securid, predicted_close AS first_close
        FROM predictpricing
        ORDER BY securid, forecast_date ASC
    ),
    sharpe_60 AS (
        SELECT DISTINCT ON (securid)
            securid, sharpe
        FROM rolling_sharpe
        WHERE window_days = 60
        ORDER BY securid, date DESC
    ),
    vol_30 AS (
        SELECT
            securid,
            STDDEV_SAMP(log_return) * SQRT(252) * 100 AS realized_vol_30d
        FROM (
            SELECT securid, log_return,
                   ROW_NUMBER() OVER (PARTITION BY securid ORDER BY date DESC) AS rn
            FROM daily_log_returns
        ) t
        WHERE rn <= 30
        GROUP BY securid
        HAVING COUNT(*) >= 2
    ),
    ev_ebitda AS (
        SELECT DISTINCT ON (sn.securid)
            sn.securid,
            sn.value_numeric AS ev_ebitda
        FROM fundamentals.snapshots sn
        JOIN fundamentals.lineitemcatalog lic ON sn.itemid = lic.itemid
        WHERE lic.item = 'EV to EBITDA'
          AND sn.value_numeric IS NOT NULL
        ORDER BY sn.securid, sn.period_date DESC
    )
    SELECT
        s.ticker,
        c.companyname,
        c.sector,
        c.industry,
        c.country,
        m.marketcap,
        pl.predicted_close                                          AS predicted_price,
        pl.confidence_interval,
        CASE WHEN pf.first_close > 0
             THEN ROUND(((pl.predicted_close - pf.first_close)
                  / pf.first_close * 100)::numeric, 2)
             ELSE NULL END                                          AS growth_pct,
        ROUND(sh.sharpe::numeric, 2)                               AS sharpe_60d,
        ROUND(v.realized_vol_30d::numeric, 2)                      AS realized_vol_30d,
        ROUND(ev.ev_ebitda::numeric, 2)                            AS ev_ebitda
    FROM securities s
    JOIN   company c   ON s.companyid = c.companyid
    LEFT JOIN marketcap m  ON c.companyid = m.companyid
    LEFT JOIN pred_latest pl ON s.securid = pl.securid
    LEFT JOIN pred_first  pf ON s.securid = pf.securid
    LEFT JOIN sharpe_60   sh ON s.securid = sh.securid
    LEFT JOIN vol_30      v  ON s.securid = v.securid
    LEFT JOIN ev_ebitda   ev ON s.securid = ev.securid
    WHERE 1=1
    """

    params: dict = {}

    if filters:
        if filters.get("sector"):
            query += " AND c.sector = :sector"
            params["sector"] = filters["sector"]
        if filters.get("industry"):
            query += " AND c.industry = :industry"
            params["industry"] = filters["industry"]
        if filters.get("country"):
            query += " AND c.country = :country"
            params["country"] = filters["country"]
        if filters.get("ticker"):
            query += " AND s.ticker = :ticker"
            params["ticker"] = filters["ticker"]
        if filters.get("marketcap_min") is not None:
            query += " AND m.marketcap >= :marketcap_min"
            params["marketcap_min"] = filters["marketcap_min"]
        if filters.get("marketcap_max") is not None:
            query += " AND m.marketcap <= :marketcap_max"
            params["marketcap_max"] = filters["marketcap_max"]

    query += " ORDER BY s.ticker"

    with get_engine().begin() as conn:
        return pd.read_sql(text(query), conn, params=params)


# ── Overview ──────────────────────────────────────────────────────────────────

def fetch_overview_stats() -> dict:
    query = """
    SELECT
        (SELECT COUNT(DISTINCT securid) FROM securities)                   AS total_securities,
        (SELECT COUNT(DISTINCT sector)  FROM company WHERE sector IS NOT NULL) AS total_sectors,
        (SELECT COUNT(DISTINCT securid) FROM predictpricing)               AS with_predictions,
        (
            SELECT ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latest_sharpe)::numeric, 2
            )
            FROM (
                SELECT DISTINCT ON (securid)
                    sharpe AS latest_sharpe
                FROM rolling_sharpe
                WHERE window_days = 60
                  AND sharpe BETWEEN -10 AND 10
                ORDER BY securid, date DESC
            ) t
        )                                                                  AS median_sharpe
    """
    with get_engine().begin() as conn:
        row = pd.read_sql(query, conn).iloc[0]
    return row.to_dict()


def fetch_treynor_data() -> pd.DataFrame:
    """
    Per-security Treynor ratio using stored beta and 252-day mean log return.
    rf_daily = LN(1.05)/252 matches sharpe.py RF_ANNUAL = 0.05.
    """
    query = """
    WITH returns AS (
        SELECT securid, AVG(log_return) * 252 AS annualised_return
        FROM (
            SELECT securid, log_return,
                   ROW_NUMBER() OVER (PARTITION BY securid ORDER BY date DESC) AS rn
            FROM daily_log_returns
        ) t
        WHERE rn <= 252
        GROUP BY securid
        HAVING COUNT(*) >= 60
    )
    SELECT
        s.ticker,
        c.sector,
        s.beta,
        r.annualised_return,
        ROUND(
            ((r.annualised_return - LN(1.0 + 0.05)) / s.beta)::numeric, 4
        ) AS treynor
    FROM securities s
    JOIN company c ON s.companyid = c.companyid
    JOIN returns r ON s.securid = r.securid
    WHERE s.beta IS NOT NULL
      AND ABS(s.beta) >= 0.05
    ORDER BY s.ticker
    """
    with get_engine().begin() as conn:
        return pd.read_sql(query, conn)


def fetch_sector_country_counts() -> pd.DataFrame:
    query = """
    SELECT
        c.sector,
        c.country,
        COUNT(DISTINCT s.securid) AS count
    FROM securities s
    JOIN company c ON s.companyid = c.companyid
    WHERE c.sector IS NOT NULL AND c.country IS NOT NULL
    GROUP BY c.sector, c.country
    """
    with get_engine().begin() as conn:
        return pd.read_sql(query, conn)


# ── Asset detail ──────────────────────────────────────────────────────────────

def fetch_asset_predictions(ticker: str) -> pd.DataFrame:
    query = """
    SELECT
        pp.forecast_date,
        pp.predicted_open,
        pp.predicted_high,
        pp.predicted_low,
        pp.predicted_close,
        pp.confidence_interval
    FROM predictpricing pp
    JOIN securities s ON pp.securid = s.securid
    WHERE s.ticker = :ticker
    ORDER BY pp.forecast_date
    """
    with get_engine().begin() as conn:
        df = pd.read_sql(text(query), conn, params={"ticker": ticker})
    df["forecast_date"] = pd.to_datetime(df["forecast_date"])
    return df


def fetch_asset_sharpe(ticker: str, window: int = 60) -> pd.DataFrame:
    """Rolling Sharpe + log return series for one asset, plus SPY benchmark."""
    query = """
    SELECT
        s.ticker,
        rs.date,
        rs.sharpe,
        dlr.log_return
    FROM rolling_sharpe rs
    JOIN securities s ON rs.securid = s.securid
    LEFT JOIN daily_log_returns dlr
           ON dlr.securid = rs.securid AND dlr.date = rs.date
    WHERE s.ticker = :ticker
      AND rs.window_days = :window
    ORDER BY rs.date
    """
    spy_query = """
    SELECT rs.date, rs.sharpe AS spy_sharpe
    FROM rolling_sharpe rs
    JOIN securities s ON rs.securid = s.securid
    WHERE s.ticker = 'SPY'
      AND rs.window_days = :window
    ORDER BY rs.date
    """
    with get_engine().begin() as conn:
        df     = pd.read_sql(text(query),     conn, params={"ticker": ticker, "window": window})
        spy_df = pd.read_sql(text(spy_query), conn, params={"window": window})

    df["date"]     = pd.to_datetime(df["date"])
    spy_df["date"] = pd.to_datetime(spy_df["date"])

    if not spy_df.empty:
        df = df.merge(spy_df, on="date", how="left")
    else:
        df["spy_sharpe"] = None

    return df


# ── Filters ───────────────────────────────────────────────────────────────────

def fetch_filter_options() -> dict:
    queries = {
        "sectors":    "SELECT DISTINCT sector   FROM company WHERE sector   IS NOT NULL ORDER BY sector",
        "industries": "SELECT DISTINCT industry FROM company WHERE industry IS NOT NULL ORDER BY industry",
        "countries":  "SELECT DISTINCT country  FROM company WHERE country  IS NOT NULL ORDER BY country",
    }
    with get_engine().begin() as conn:
        return {k: pd.read_sql(q, conn).iloc[:, 0].tolist() for k, q in queries.items()}


def fetch_marketcap_range() -> tuple[int, int]:
    query = """
    SELECT
        COALESCE(MIN(marketcap), 0)               AS min_cap,
        COALESCE(MAX(marketcap), 10000000000000)  AS max_cap
    FROM marketcap
    WHERE marketcap IS NOT NULL
    """
    with get_engine().begin() as conn:
        row = pd.read_sql(query, conn).iloc[0]
    return int(row["min_cap"]), int(row["max_cap"])
