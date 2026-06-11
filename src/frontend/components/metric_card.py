from dash import html
import dash_bootstrap_components as dbc
from registry import CATEGORY_COLORS


def _fmt(value, fmt: str | None) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
        import math
        if math.isnan(v):
            return "—"
        if fmt == "currency_2dp":   return f"${v:,.2f}"
        if fmt == "pct_2dp":        return f"{v:.2f}%"
        if fmt == "pct_1dp":        return f"{v:.1f}%"
        if fmt == "float_2dp":      return f"{v:.2f}"
        if fmt == "text":           return str(value)
        return str(value)
    except (TypeError, ValueError):
        return str(value) if value else "—"


def metric_group(title: str, metrics: list[dict], data_row: dict, category: str) -> dbc.Card:
    """Titled panel card grouping related metrics for the asset detail view."""
    color = CATEGORY_COLORS.get(category, "#6b7280")
    rows = [
        html.Div([
            html.Span(m["label"],
                      style={"fontSize": "11px", "color": "#6b7280",
                             "textTransform": "uppercase", "flex": "1"}),
            html.Span(_fmt(data_row.get(m["id"]), m.get("format")),
                      style={"fontWeight": "600", "fontSize": "14px"}),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "padding": "7px 0", "borderBottom": "1px solid #f1f5f9"})
        for m in metrics
    ]
    return dbc.Card([
        dbc.CardHeader(
            html.Div([
                html.Span("●", style={"color": color, "marginRight": "8px"}),
                html.Span(title, style={"fontWeight": "600", "fontSize": "12px",
                                        "textTransform": "uppercase", "color": color}),
            ]),
            style={"backgroundColor": f"{color}12", "padding": "8px 14px"},
        ),
        dbc.CardBody(rows, style={"padding": "4px 14px 8px"}),
    ], style={"marginBottom": "10px", "borderTop": f"3px solid {color}",
              "boxShadow": "0 1px 3px rgba(0,0,0,0.07)"})


def kpi_card(label: str, value: str, color: str = "#3b82f6") -> dbc.Card:
    """Single large KPI number card for the overview page."""
    return dbc.Card(
        dbc.CardBody([
            html.P(label, style={"fontSize": "11px", "textTransform": "uppercase",
                                 "color": "#6b7280", "marginBottom": "6px", "fontWeight": "600"}),
            html.H3(value, style={"fontWeight": "700", "color": color, "marginBottom": "0"}),
        ], style={"padding": "16px 20px"}),
        style={"borderTop": f"3px solid {color}", "boxShadow": "0 1px 3px rgba(0,0,0,0.07)"},
    )
