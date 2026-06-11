import os
import sys

# Ensure src/frontend/ is on the path so pages can import services, components, registry
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
    title="Portfolio Dashboard",
)
server = app.server  # expose for production WSGI servers


def _nav_link(label: str, href: str) -> dbc.NavItem:
    return dbc.NavItem(dbc.NavLink(label, href=href, active="exact"))


navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand("Portfolio Dashboard", href="/", className="fw-bold"),
        dbc.Nav([
            _nav_link("Overview",   "/"),
            _nav_link("Screener",   "/screener"),
            _nav_link("Portfolios", "/portfolios"),
        ], navbar=True, className="ms-3"),
    ], fluid=True),
    color="primary", dark=True, className="mb-0",
)

app.layout = html.Div([
    navbar,
    dbc.Container(dash.page_container, fluid=True,
                  style={"backgroundColor": "#f8fafc", "minHeight": "calc(100vh - 56px)",
                         "paddingTop": "4px"}),
])


if __name__ == "__main__":
    app.run(debug=True, port=8050)
