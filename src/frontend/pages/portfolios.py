import dash
import dash_bootstrap_components as dbc
from dash import html

dash.register_page(__name__, path="/portfolios", name="Portfolios", order=3)


def layout(**kwargs):
    return dbc.Container([
        html.H4("Portfolios", className="mt-3 mb-3"),
        dbc.Card(dbc.CardBody([
            html.H5("Coming soon", className="text-muted"),
            html.P(
                "The portfolio builder will support position management, "
                "live P&L recomputation, and portfolio-level Sharpe using "
                "the full covariance matrix of constituent return series.",
                className="text-muted",
            ),
        ]), className="shadow-sm"),
    ], fluid=True)
