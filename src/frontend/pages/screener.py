import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html

from registry import CATEGORY_COLORS, SCREENER_COLUMNS
from services.analytics import format_marketcap
from services.data_service import (
    fetch_filter_options, fetch_marketcap_range, fetch_screener_data,
)

dash.register_page(__name__, path="/screener", name="Screener", order=1)

# ── Module-level DB reads (run once at startup) ───────────────────────────────
_filter_opts        = fetch_filter_options()
_min_cap, _max_cap  = fetch_marketcap_range()


def _dt_columns() -> list[dict]:
    """Build DataTable column definitions from the registry."""
    cols = []
    for c in SCREENER_COLUMNS:
        dot  = "● " if c["category"] else ""
        col  = {"name": f"{dot}{c['label']}", "id": c["id"]}
        if c["id"] == "ticker":
            col["presentation"] = "markdown"
        cols.append(col)
    return cols


def layout(**kwargs):
    return dbc.Container([
        html.H4("Security Screener", className="mt-3 mb-2"),

        # ── Category legend ───────────────────────────────────────────────────
        html.Div([
            html.Span("Metric categories: ",
                      style={"fontSize": "12px", "color": "#6b7280", "marginRight": "4px"}),
            *[html.Span([
                html.Span("●", style={"color": color}),
                html.Span(f" {cat.title()}",
                          style={"fontSize": "12px", "color": "#374151", "marginRight": "12px"}),
              ]) for cat, color in CATEGORY_COLORS.items() if cat != "macro"],
        ], className="mb-3"),

        # ── Filters ───────────────────────────────────────────────────────────
        dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Sector", className="form-label fw-semibold small"),
                    dcc.Dropdown(id="sc-sector", clearable=True, placeholder="All Sectors",
                                 options=[{"label": s, "value": s} for s in _filter_opts["sectors"]]),
                ], md=3),
                dbc.Col([
                    html.Label("Industry", className="form-label fw-semibold small"),
                    dcc.Dropdown(id="sc-industry", clearable=True, placeholder="All Industries",
                                 options=[{"label": i, "value": i} for i in _filter_opts["industries"]]),
                ], md=3),
                dbc.Col([
                    html.Label("Country", className="form-label fw-semibold small"),
                    dcc.Dropdown(id="sc-country", clearable=True, placeholder="All Countries",
                                 options=[{"label": c, "value": c} for c in _filter_opts["countries"]]),
                ], md=3),
                dbc.Col([
                    dbc.Button("Reset", id="sc-reset", color="secondary",
                               size="sm", className="mt-4 w-100"),
                ], md=1),
            ], className="g-2"),
            dbc.Row([
                dbc.Col([
                    html.Label("Market Cap Range", className="form-label fw-semibold small mt-3"),
                    dcc.RangeSlider(
                        id="sc-marketcap", min=_min_cap, max=_max_cap,
                        step=max(1, _max_cap // 20), value=[_min_cap, _max_cap],
                        tooltip={"placement": "bottom", "always_visible": True},
                        marks={_min_cap: "$0", _max_cap: format_marketcap(_max_cap)},
                    ),
                ]),
            ]),
        ]), className="mb-3 shadow-sm"),

        # ── Result count ──────────────────────────────────────────────────────
        html.Div(id="sc-count", className="text-muted small mb-2"),

        # ── DataTable ─────────────────────────────────────────────────────────
        dcc.Loading(dash_table.DataTable(
            id="screener-table",
            columns=_dt_columns(),
            data=[],
            page_size=30,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "#f8fafc", "fontWeight": "600",
                "fontSize": "11px", "textTransform": "uppercase",
                "color": "#374151", "border": "1px solid #e2e8f0",
            },
            style_cell={
                "fontSize": "13px", "padding": "9px 13px",
                "border": "1px solid #f1f5f9", "fontFamily": "Arial, sans-serif",
                "maxWidth": "180px", "overflow": "hidden", "textOverflow": "ellipsis",
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                {"if": {"state": "active"},  "backgroundColor": "#eff6ff",
                 "border": "1px solid #3b82f6"},
                {"if": {"filter_query": "{growth_pct} > 0", "column_id": "growth_pct"},
                 "color": "#16a34a", "fontWeight": "600"},
                {"if": {"filter_query": "{growth_pct} < 0", "column_id": "growth_pct"},
                 "color": "#dc2626", "fontWeight": "600"},
                {"if": {"filter_query": "{sharpe_60d} > 1", "column_id": "sharpe_60d"},
                 "color": "#16a34a"},
                {"if": {"filter_query": "{sharpe_60d} < 0", "column_id": "sharpe_60d"},
                 "color": "#dc2626"},
            ],
            markdown_options={"link_target": "_self"},
        )),

        html.P("Click a ticker to open the asset detail view.",
               className="text-muted small mt-2"),

        dcc.Store(id="sc-store"),
    ], fluid=True)


# ── Callbacks ─────────────────────────────────────────────────────────────────

@callback(
    Output("sc-store", "data"),
    Input("sc-sector",    "value"),
    Input("sc-industry",  "value"),
    Input("sc-country",   "value"),
    Input("sc-marketcap", "value"),
    Input("sc-reset",     "n_clicks"),
)
def load_screener(sector, industry, country, cap_range, _reset):
    filters = {
        "sector":       sector,
        "industry":     industry,
        "country":      country,
        "marketcap_min": cap_range[0] if cap_range else None,
        "marketcap_max": cap_range[1] if cap_range else None,
    }
    df = fetch_screener_data(filters)
    return df.to_json(date_format="iso", orient="split") if not df.empty else None


@callback(
    Output("screener-table", "data"),
    Output("sc-count", "children"),
    Input("sc-store", "data"),
)
def render_table(data):
    if not data:
        return [], "No securities found"
    df = pd.read_json(data, orient="split")
    # Format marketcap for display and build markdown ticker links
    df["marketcap_display"] = df["marketcap"].apply(format_marketcap)
    df["ticker"] = df["ticker"].apply(lambda t: f"[{t}](/asset/{t})")
    cols = [c["id"] for c in SCREENER_COLUMNS]
    return df[cols].to_dict("records"), f"{len(df)} securities"


@callback(
    Output("sc-sector",    "value"),
    Output("sc-industry",  "value"),
    Output("sc-country",   "value"),
    Output("sc-marketcap", "value"),
    Input("sc-reset", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    return None, None, None, [_min_cap, _max_cap]
