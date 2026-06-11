import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from components.asset_chart import (
    cumulative_returns_chart, prediction_chart, rolling_sharpe_chart,
)
from components.metric_card import metric_group
from registry import DETAIL_METRIC_PANELS
from services.analytics import format_marketcap
from services.data_service import (
    fetch_asset_predictions, fetch_asset_sharpe, fetch_screener_data,
)

dash.register_page(__name__, path_template="/asset/<ticker>", name="Asset Detail")

_SHARPE_WINDOW = 60


def layout(ticker: str = "", **kwargs):
    if not ticker:
        return dbc.Container(
            dbc.Alert("No ticker specified. Return to the Screener.", color="warning",
                      className="mt-4"),
            fluid=True,
        )

    return dbc.Container([
        # ── Breadcrumb + header ───────────────────────────────────────────────
        dbc.Breadcrumb(
            items=[{"label": "Screener", "href": "/screener"}, {"label": ticker, "active": True}],
            className="mt-3 mb-0",
        ),
        html.H4(id="ad-header", className="mb-3"),

        # ── Prediction chart ─────────────────────────────────────────────────
        dbc.Card(dbc.CardBody(
            dcc.Loading(dcc.Graph(id="ad-pred-chart", config={"displayModeBar": False}))
        ), className="mb-3 shadow-sm"),

        # ── Metric panels (left) + Risk charts (right) ───────────────────────
        dbc.Row([
            dbc.Col(html.Div(id="ad-metric-panels"), md=4),
            dbc.Col([
                dbc.Card(dbc.CardBody(
                    dcc.Loading(dcc.Graph(id="ad-sharpe-chart", config={"displayModeBar": False}))
                ), className="mb-3 shadow-sm"),
                dbc.Card(dbc.CardBody(
                    dcc.Loading(dcc.Graph(id="ad-returns-chart", config={"displayModeBar": False}))
                ), className="shadow-sm"),
            ], md=8),
        ], className="mb-4"),

        dcc.Store(id="ad-ticker", data=ticker),
    ], fluid=True)


# ── Callbacks ─────────────────────────────────────────────────────────────────

@callback(
    Output("ad-header",    "children"),
    Output("ad-pred-chart","figure"),
    Input("ad-ticker", "data"),
)
def update_prediction(ticker):
    if not ticker:
        return "", go.Figure()
    pred_df = fetch_asset_predictions(ticker)
    return ticker, prediction_chart(pred_df, ticker)


@callback(
    Output("ad-sharpe-chart",  "figure"),
    Output("ad-returns-chart", "figure"),
    Input("ad-ticker", "data"),
)
def update_risk_charts(ticker):
    if not ticker:
        return go.Figure(), go.Figure()
    sharpe_df = fetch_asset_sharpe(ticker, window=_SHARPE_WINDOW)
    return (
        rolling_sharpe_chart(sharpe_df, ticker, window=_SHARPE_WINDOW),
        cumulative_returns_chart(sharpe_df),
    )


@callback(
    Output("ad-metric-panels", "children"),
    Input("ad-ticker", "data"),
)
def update_metric_panels(ticker):
    if not ticker:
        return []
    df = fetch_screener_data({"ticker": ticker})
    if df.empty:
        return [dbc.Alert("No metric data available.", color="secondary")]

    row = df.iloc[0].to_dict()
    row["marketcap_display"] = format_marketcap(row.get("marketcap"))

    return [
        metric_group(cat.title(), metrics, row, cat)
        for cat, metrics in DETAIL_METRIC_PANELS.items()
    ]
