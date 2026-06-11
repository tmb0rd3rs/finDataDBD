import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

from components.asset_chart import (
    growth_bar, volatility_bar, treynor_histogram,
    marketcap_scatter, sector_country_heatmap,
)
from components.metric_card import kpi_card
from services.analytics import build_sector_country_pivot, format_marketcap
from services.data_service import (
    fetch_overview_stats, fetch_screener_data,
    fetch_treynor_data, fetch_sector_country_counts,
)

dash.register_page(__name__, path="/", name="Overview", order=0)


def layout(**kwargs):
    # All data fetched once at render time — no callbacks needed for the overview
    stats       = fetch_overview_stats()
    screener_df = fetch_screener_data()
    treynor_df  = fetch_treynor_data()
    sc_df       = fetch_sector_country_counts()
    pivot       = build_sector_country_pivot(sc_df)

    median_sharpe = stats.get("median_sharpe")
    try:
        median_sharpe_str = f"{float(median_sharpe):.2f}" if median_sharpe is not None else "—"
    except (TypeError, ValueError):
        median_sharpe_str = "—"

    return dbc.Container([
        html.H4("Overview", className="mt-3 mb-3"),

        # ── KPI cards ────────────────────────────────────────────────────────
        dbc.Row([
            dbc.Col(kpi_card("Securities",       str(int(stats.get("total_securities", 0))),  "#3b82f6"), md=3),
            dbc.Col(kpi_card("Sectors",           str(int(stats.get("total_sectors",     0))),  "#8b5cf6"), md=3),
            dbc.Col(kpi_card("With Predictions",  str(int(stats.get("with_predictions",  0))),  "#22c55e"), md=3),
            dbc.Col(kpi_card("Median Sharpe (60d)", median_sharpe_str,                            "#f97316"), md=3),
        ], className="mb-4 g-3"),

        # ── Row 1: Growth + Volatility ───────────────────────────────────────
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(figure=growth_bar(screener_df),     config={"displayModeBar": False})), className="shadow-sm"), md=6),
            dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(figure=volatility_bar(screener_df), config={"displayModeBar": False})), className="shadow-sm"), md=6),
        ], className="mb-4 g-3"),

        # ── Row 2: Treynor histogram + Market cap scatter ────────────────────
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(figure=treynor_histogram(treynor_df),     config={"displayModeBar": False})), className="shadow-sm"), md=6),
            dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(figure=marketcap_scatter(screener_df),    config={"displayModeBar": False})), className="shadow-sm"), md=6),
        ], className="mb-4 g-3"),

        # ── Row 3: Sector × Country heatmap (full width) ─────────────────────
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(figure=sector_country_heatmap(pivot), config={"displayModeBar": False})), className="shadow-sm")),
        ], className="mb-4"),

    ], fluid=True)
