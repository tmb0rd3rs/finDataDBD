"""
Pure figure-builder functions — accept DataFrames, return Plotly figures.
No Dash imports, no DB calls.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

_LAYOUT_BASE = dict(
    plot_bgcolor="rgba(240,242,245,0.5)",
    paper_bgcolor="white",
    font=dict(family="Arial, sans-serif", size=11),
    margin=dict(l=60, r=20, t=55, b=40),
)


def prediction_chart(pred_df: pd.DataFrame, ticker: str) -> go.Figure:
    fig = go.Figure()
    if pred_df.empty:
        fig.add_annotation(text="No prediction data available", showarrow=False, font=dict(size=13))
        fig.update_layout(height=420, **_LAYOUT_BASE)
        return fig

    ci     = pred_df["confidence_interval"] / 100
    upper  = pred_df["predicted_close"] * (1 + ci)
    lower  = pred_df["predicted_close"] * (1 - ci)

    fig.add_trace(go.Scatter(
        x=pred_df["forecast_date"], y=upper,
        fill=None, mode="lines", line_color="rgba(0,0,0,0)",
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=pred_df["forecast_date"], y=lower,
        fill="tonexty", mode="lines", line_color="rgba(0,0,0,0)",
        name="Confidence band", fillcolor="rgba(59,130,246,0.12)",
        hovertemplate="Lower: $%{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=pred_df["forecast_date"], y=pred_df["predicted_close"],
        mode="lines", name=ticker,
        line=dict(color="#3b82f6", width=2.5),
        hovertemplate="<b>%{fullData.name}</b><br>%{x|%Y-%m-%d}<br>$%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=f"{ticker} — Predicted Close with Confidence Interval",
        xaxis_title="Date", yaxis_title="Price (USD)",
        hovermode="x unified", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **_LAYOUT_BASE,
    )
    return fig


def rolling_sharpe_chart(sharpe_df: pd.DataFrame, ticker: str, window: int) -> go.Figure:
    """
    Rolling Sharpe for one asset with an optional SPY benchmark overlay.
    sharpe_df must have columns: date, sharpe, and optionally spy_sharpe.
    """
    fig = go.Figure()
    if sharpe_df.empty or "sharpe" not in sharpe_df.columns:
        fig.add_annotation(text="No Sharpe data available", showarrow=False, font=dict(size=13))
        fig.update_layout(height=310, **_LAYOUT_BASE)
        return fig

    fig.add_trace(go.Scatter(
        x=sharpe_df["date"], y=sharpe_df["sharpe"],
        mode="lines", name=ticker,
        line=dict(color="#f97316", width=2),
        hovertemplate="%{x|%Y-%m-%d}  Sharpe: %{y:.2f}<extra></extra>",
    ))

    if "spy_sharpe" in sharpe_df.columns and sharpe_df["spy_sharpe"].notna().any():
        fig.add_trace(go.Scatter(
            x=sharpe_df["date"], y=sharpe_df["spy_sharpe"],
            mode="lines", name="SPY (benchmark)",
            line=dict(color="#94a3b8", width=1.5, dash="dash"),
            hovertemplate="%{x|%Y-%m-%d}  SPY: %{y:.2f}<extra></extra>",
        ))

    fig.add_hline(y=0, line_dash="dash",  line_color="#374151", line_width=0.8)
    fig.add_hline(y=1, line_dash="dot",   line_color="#22c55e", line_width=0.8,
                  annotation_text="Sharpe = 1", annotation_position="bottom right")
    fig.update_layout(
        title=f"Rolling Sharpe ({window}-day)",
        xaxis_title="Date", yaxis_title="Sharpe",
        hovermode="x unified", height=310,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **_LAYOUT_BASE,
    )
    return fig


def cumulative_returns_chart(sharpe_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if sharpe_df.empty or "log_return" not in sharpe_df.columns:
        fig.add_annotation(text="No return data available", showarrow=False, font=dict(size=13))
        fig.update_layout(height=310, **_LAYOUT_BASE)
        return fig

    series     = sharpe_df.dropna(subset=["log_return"]).sort_values("date")
    cumulative = np.exp(np.cumsum(series["log_return"].values))

    fig.add_trace(go.Scatter(
        x=series["date"], y=cumulative,
        mode="lines", name="Growth of $1",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.07)",
        hovertemplate="%{x|%Y-%m-%d}  $%{y:.3f}<extra></extra>",
    ))
    fig.add_hline(y=1, line_dash="dash", line_color="#374151", line_width=0.8)
    fig.update_layout(
        title="Cumulative Returns (Growth of $1)",
        xaxis_title="Date", yaxis_title="Growth of $1",
        height=310, **_LAYOUT_BASE,
    )
    return fig


def treynor_histogram(treynor_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if treynor_df.empty or "treynor" not in treynor_df.columns:
        fig.add_annotation(text="No Treynor data available", showarrow=False, font=dict(size=13))
        fig.update_layout(height=350, **_LAYOUT_BASE)
        return fig

    clean = pd.to_numeric(treynor_df["treynor"], errors="coerce").dropna()
    # Clip extreme outliers for display (keep 1st–99th percentile)
    lo, hi = clean.quantile(0.01), clean.quantile(0.99)
    clipped = clean.clip(lo, hi)

    fig.add_trace(go.Histogram(
        x=clipped, nbinsx=30,
        marker_color="#f97316", opacity=0.8,
        hovertemplate="Treynor: %{x:.3f}<br>Count: %{y}<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#374151", line_width=1)
    fig.update_layout(
        title="Treynor Ratio Distribution",
        xaxis_title="Treynor Ratio", yaxis_title="Count",
        height=350, showlegend=False, **_LAYOUT_BASE,
    )
    return fig


def sector_country_heatmap(pivot: pd.DataFrame) -> go.Figure:
    if pivot.empty:
        fig = go.Figure()
        fig.add_annotation(text="No sector/country data", showarrow=False, font=dict(size=13))
        fig.update_layout(height=400, **_LAYOUT_BASE)
        return fig

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="Blues",
        hovertemplate="Sector: %{x}<br>Country: %{y}<br>Securities: %{z}<extra></extra>",
        showscale=True,
    ))
    fig.update_layout(
        title="Securities by Sector × Country",
        xaxis_title="Sector", yaxis_title="Country",
        xaxis=dict(tickangle=-35),
        height=max(350, 30 * len(pivot) + 120),
        **_LAYOUT_BASE,
    )
    return fig


def growth_bar(screener_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if screener_df.empty or "growth_pct" not in screener_df.columns:
        fig.add_annotation(text="No growth data", showarrow=False)
        fig.update_layout(height=350, **_LAYOUT_BASE)
        return fig

    df = screener_df.copy()
    df["growth_pct"] = pd.to_numeric(df["growth_pct"], errors="coerce")
    top = df.dropna(subset=["growth_pct"]).nlargest(10, "growth_pct")
    n = len(top)
    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in top["growth_pct"]]
    fig.add_trace(go.Bar(
        x=top["ticker"], y=top["growth_pct"],
        marker_color=colors,
        text=[f"{v:.1f}%" for v in top["growth_pct"]], textposition="auto",
        hovertemplate="<b>%{x}</b><br>Growth: %{y:.2f}%<extra></extra>",
    ))
    fig.update_layout(title=f"Top {n} — Predicted Growth", xaxis_title="Ticker",
                      yaxis_title="Growth (%)", height=350, showlegend=False,
                      **_LAYOUT_BASE)
    return fig


def volatility_bar(screener_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if screener_df.empty or "realized_vol_30d" not in screener_df.columns:
        fig.add_annotation(text="No volatility data", showarrow=False)
        fig.update_layout(height=350, **_LAYOUT_BASE)
        return fig

    df = screener_df.copy()
    df["realized_vol_30d"] = pd.to_numeric(df["realized_vol_30d"], errors="coerce")
    top = df.dropna(subset=["realized_vol_30d"]).nlargest(10, "realized_vol_30d")
    n = len(top)
    fig.add_trace(go.Bar(
        x=top["ticker"], y=top["realized_vol_30d"],
        marker_color="#8b5cf6",
        text=[f"{v:.1f}%" for v in top["realized_vol_30d"]], textposition="auto",
        hovertemplate="<b>%{x}</b><br>Vol (30d): %{y:.2f}%<extra></extra>",
    ))
    fig.update_layout(title=f"Top {n} — Realised Volatility (30d)", xaxis_title="Ticker",
                      yaxis_title="Annualised Vol (%)", height=350, showlegend=False,
                      **_LAYOUT_BASE)
    return fig


def marketcap_scatter(screener_df: pd.DataFrame) -> go.Figure:
    if screener_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data", showarrow=False)
        fig.update_layout(height=350, **_LAYOUT_BASE)
        return fig

    df = screener_df.copy()
    df["marketcap"]      = pd.to_numeric(df["marketcap"],      errors="coerce")
    df["predicted_price"] = pd.to_numeric(df["predicted_price"], errors="coerce")
    df = df.dropna(subset=["marketcap", "predicted_price"])
    fig = px.scatter(
        df, x="marketcap", y="predicted_price", color="sector",
        hover_name="ticker",
        hover_data={"companyname": True, "marketcap": ":,.0f", "predicted_price": ":.2f"},
        title="Market Cap vs Predicted Price (log log)",
        labels={"marketcap": "Market Cap (USD)", "predicted_price": "Predicted Price (USD)"},
        height=350,
    )
    fig.update_xaxes(type="log", title_text="Market Cap (USD)")
    fig.update_yaxes(type="log", title_text="Predicted Price (USD)")
    fig.update_layout(showlegend=False, **_LAYOUT_BASE)
    return fig
