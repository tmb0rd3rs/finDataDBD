"""
Metric registry — single source of truth for what metrics exist,
which category they belong to, and which asset classes they apply to.

Screener columns, detail panels, and filter controls are all generated from
this registry. A commodity shows "—" for equity-only metrics because the
registry says so — nothing is special-cased.
"""

CATEGORY_COLORS: dict[str, str] = {
    "technical": "#3b82f6",    # blue
    "fundamental": "#8b5cf6",  # purple
    "risk": "#f97316",         # orange
    "sentiment": "#22c55e",    # green
    "macro": "#6b7280",        # gray
}

# Columns rendered in the screener DataTable (order matters)
SCREENER_COLUMNS: list[dict] = [
    {
        "id": "ticker",
        "label": "Ticker",
        "category": None,
        "format": None,
        "asset_classes": ["equity", "etf", "commodity"],
    },
    {
        "id": "companyname",
        "label": "Company",
        "category": None,
        "format": None,
        "asset_classes": ["equity", "etf", "commodity"],
    },
    {
        "id": "sector",
        "label": "Sector",
        "category": "fundamental",
        "format": None,
        "asset_classes": ["equity", "etf"],
    },
    {
        "id": "country",
        "label": "Country",
        "category": "fundamental",
        "format": None,
        "asset_classes": ["equity", "etf", "commodity"],
    },
    {
        "id": "marketcap_display",
        "label": "Mkt Cap",
        "category": "fundamental",
        "format": "currency_compact",
        "asset_classes": ["equity"],
    },
    {
        "id": "predicted_price",
        "label": "Pred. Price",
        "category": "technical",
        "format": "currency_2dp",
        "asset_classes": ["equity", "etf", "commodity"],
    },
    {
        "id": "growth_pct",
        "label": "Growth %",
        "category": "technical",
        "format": "pct_2dp",
        "asset_classes": ["equity", "etf", "commodity"],
    },
    {
        "id": "realized_vol_30d",
        "label": "Vol 30d %",
        "category": "technical",
        "format": "pct_2dp",
        "asset_classes": ["equity", "etf", "commodity"],
    },
    {
        "id": "sharpe_60d",
        "label": "Sharpe 60d",
        "category": "risk",
        "format": "float_2dp",
        "asset_classes": ["equity", "etf", "commodity"],
    },
    {
        "id": "ev_ebitda",
        "label": "EV/EBITDA",
        "category": "fundamental",
        "format": "float_2dp",
        "asset_classes": ["equity"],
    },
]

# Metric panels rendered on the asset detail page, grouped by category
DETAIL_METRIC_PANELS: dict[str, list[dict]] = {
    "risk": [
        {"id": "sharpe_60d",       "label": "Sharpe (60d)",      "format": "float_2dp"},
        {"id": "realized_vol_30d", "label": "Realized Vol (30d)", "format": "pct_2dp"},
    ],
    "technical": [
        {"id": "predicted_price",    "label": "Predicted Price", "format": "currency_2dp"},
        {"id": "growth_pct",         "label": "Pred. Growth",    "format": "pct_2dp"},
        {"id": "confidence_interval","label": "Confidence ±",    "format": "pct_1dp"},
    ],
    "fundamental": [
        {"id": "sector",           "label": "Sector",      "format": "text"},
        {"id": "industry",         "label": "Industry",    "format": "text"},
        {"id": "country",          "label": "Country",     "format": "text"},
        {"id": "marketcap_display","label": "Market Cap",  "format": "text"},
        {"id": "ev_ebitda",        "label": "EV/EBITDA",   "format": "float_2dp"},
    ],
}
