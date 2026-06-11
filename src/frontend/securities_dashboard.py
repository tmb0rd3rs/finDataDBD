import dash
from dash import dcc, html, callback, Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv()

# ============================================
# DATABASE CONNECTION
# ============================================
# Configure your database connection
host = os.environ.get("DB_HOST", "localhost")
port = int(os.environ.get("DB_PORT", 5432))
database = os.environ.get("DB_NAME", "dev_findata")
user = os.environ.get("DB_USER", "postgres")
password = os.environ["DB_PASSWORD"]  # intentionally required

url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
print("Database engine created (%s:%s/%s)", host, port, database)



# ============================================
# DATA FETCHING FUNCTIONS
# ============================================

def fetch_prediction_data(filters=None):
    """
    Fetch predicted pricing data with optional filters.

    SQL joins:
    - predictpricing: predicted prices
    - securities: ticker, companyid
    - company: sector, industry, country
    - marketcap: market capitalization
    """
    query = """
    SELECT 
        p.ticker,
        p.predictiondate,
        p.predictedprice,
        c.companyname,
        sec.sector,
        sec.industry,
        sec.country,
        m.marketcap,
        sec.isin
    FROM predictpricing p
    JOIN securities s ON p.ticker = s.ticker
    JOIN company sec ON s.companyid = sec.companyid
    LEFT JOIN marketcap m ON sec.companyid = m.companyid
    WHERE 1=1
    """

    params = {}

    if filters:
        if filters.get('sector'):
            query += " AND sec.sector = :sector"
            params['sector'] = filters['sector']
        if filters.get('industry'):
            query += " AND sec.industry = :industry"
            params['industry'] = filters['industry']
        if filters.get('country'):
            query += " AND sec.country = :country"
            params['country'] = filters['country']
        if filters.get('marketcap_min'):
            query += " AND m.marketcap >= :marketcap_min"
            params['marketcap_min'] = filters['marketcap_min']
        if filters.get('marketcap_max'):
            query += " AND m.marketcap <= :marketcap_max"
            params['marketcap_max'] = filters['marketcap_max']

    query += " ORDER BY p.ticker, p.predictiondate"

    with engine.begin() as conn:
        result = conn.execute(text(query), params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    return df


def fetch_filter_options():
    """Fetch unique values for filter dropdowns."""
    query = """
    SELECT DISTINCT sector FROM company WHERE sector IS NOT NULL ORDER BY sector;
    """
    with engine.begin() as conn:
        sectors = pd.read_sql(query, conn)['sector'].tolist()

    query = "SELECT DISTINCT industry FROM company WHERE industry IS NOT NULL ORDER BY industry;"
    with engine.begin() as conn:
        industries = pd.read_sql(query, conn)['industry'].tolist()

    query = "SELECT DISTINCT country FROM company WHERE country IS NOT NULL ORDER BY country;"
    with engine.begin() as conn:
        countries = pd.read_sql(query, conn)['country'].tolist()

    return {
        'sectors': sectors,
        'industries': industries,
        'countries': countries
    }


def calculate_metrics(df):
    """
    Calculate metrics for output factors.
    Returns dict with growth_trajectory, volatility, etc.
    """
    metrics = {}

    for ticker in df['ticker'].unique():
        ticker_data = df[df['ticker'] == ticker].sort_values('predictiondate')

        if len(ticker_data) < 2:
            continue

        prices = ticker_data['predictedprice'].values

        # Growth trajectory (% change)
        growth = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] != 0 else 0

        # Volatility (standard deviation of returns)
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * 100 if len(returns) > 0 else 0

        metrics[ticker] = {
            'growth': growth,
            'volatility': volatility,
            'current_price': prices[-1],
            'start_price': prices[0]
        }

    return metrics


# ============================================
# DASH APP INITIALIZATION
# ============================================

app = dash.Dash(__name__)
app.title = "Security Price Predictions"

# Load initial filter options
filter_options = fetch_filter_options()

# ============================================
# APP LAYOUT
# ============================================

app.layout = html.Div([
    # Header
    html.Div([
        html.H1("Security Price Predictions", className="dashboard-title"),
        html.P("Analyze predicted pricing trends and performance metrics", className="dashboard-subtitle")
    ], className="header-container"),

    # Filter Panel
    html.Div([
        html.Div([
            html.Div([
                html.Label("Sector", className="filter-label"),
                dcc.Dropdown(
                    id='sector-filter',
                    options=[{'label': 'All Sectors', 'value': 'all'}] +
                            [{'label': s, 'value': s} for s in filter_options['sectors']],
                    value='all',
                    clearable=False,
                    className="filter-dropdown"
                )
            ], className="filter-item"),

            html.Div([
                html.Label("Industry", className="filter-label"),
                dcc.Dropdown(
                    id='industry-filter',
                    options=[{'label': 'All Industries', 'value': 'all'}] +
                            [{'label': i, 'value': i} for i in filter_options['industries']],
                    value='all',
                    clearable=False,
                    className="filter-dropdown"
                )
            ], className="filter-item"),

            html.Div([
                html.Label("Country", className="filter-label"),
                dcc.Dropdown(
                    id='country-filter',
                    options=[{'label': 'All Countries', 'value': 'all'}] +
                            [{'label': c, 'value': c} for c in filter_options['countries']],
                    value='all',
                    clearable=False,
                    className="filter-dropdown"
                )
            ], className="filter-item"),

            html.Div([
                html.Label("Market Cap Range (USD)", className="filter-label"),
                dcc.RangeSlider(
                    id='marketcap-filter',
                    min=0,
                    max=10000000000000,
                    step=1000000000000,
                    marks={i: f"${i / 1e12:.1f}T" for i in range(0, 11000000000000, 2000000000000)},
                    value=[0, 10000000000000],
                    className="range-slider",
                    tooltip={"placement": "bottom", "always_visible": True}
                )
            ], className="filter-item-full"),

            html.Button(
                "Reset Filters",
                id='reset-button',
                n_clicks=0,
                className="reset-button"
            )
        ], className="filter-container")
    ], className="filters-wrapper"),

    # Main visualization area
    html.Div([
        # Large main graph
        html.Div([
            dcc.Loading(
                id="loading-main-graph",
                type="default",
                children=[
                    dcc.Graph(id='main-predictions-graph')
                ]
            )
        ], className="main-graph-container"),

        # Metrics grid (5 smaller graphs)
        html.Div([
            html.Div([
                dcc.Loading(
                    id="loading-growth",
                    type="default",
                    children=[dcc.Graph(id='growth-trajectory-graph')]
                )
            ], className="metric-card"),

            html.Div([
                dcc.Loading(
                    id="loading-volatility",
                    type="default",
                    children=[dcc.Graph(id='volatility-graph')]
                )
            ], className="metric-card"),

            html.Div([
                dcc.Loading(
                    id="loading-distribution",
                    type="default",
                    children=[dcc.Graph(id='price-distribution-graph')]
                )
            ], className="metric-card"),

            html.Div([
                dcc.Loading(
                    id="loading-marketcap",
                    type="default",
                    children=[dcc.Graph(id='marketcap-graph')]
                )
            ], className="metric-card"),

            html.Div([
                dcc.Loading(
                    id="loading-sector",
                    type="default",
                    children=[dcc.Graph(id='sector-distribution-graph')]
                )
            ], className="metric-card"),
        ], className="metrics-grid"),
    ], className="main-content"),

    # Store for caching data
    dcc.Store(id='filtered-data-store')

], className="dashboard-container", style={
    'fontFamily': "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    'backgroundColor': '#f5f7fa',
    'minHeight': '100vh',
    'padding': '20px'
})


# ============================================
# CALLBACKS
# ============================================

@callback(
    Output('filtered-data-store', 'data'),
    Input('sector-filter', 'value'),
    Input('industry-filter', 'value'),
    Input('country-filter', 'value'),
    Input('marketcap-filter', 'value'),
    Input('reset-button', 'n_clicks'),
    prevent_initial_call=False
)
def update_data(sector, industry, country, marketcap_range, reset_clicks):
    """Fetch and filter data based on selected filters."""

    filters = {}
    if sector != 'all':
        filters['sector'] = sector
    if industry != 'all':
        filters['industry'] = industry
    if country != 'all':
        filters['country'] = country

    filters['marketcap_min'] = marketcap_range[0]
    filters['marketcap_max'] = marketcap_range[1]

    df = fetch_prediction_data(filters)

    return df.to_json(date_format='iso', orient='split')


@callback(
    Output('main-predictions-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_main_graph(data):
    """Update main predictions graph."""
    if not data:
        return go.Figure().add_annotation(text="No data available")

    df = pd.read_json(data, orient='split')

    if df.empty:
        return go.Figure().add_annotation(text="No data matches filters")

    fig = px.line(
        df,
        x='predictiondate',
        y='predictedprice',
        color='ticker',
        hover_name='companyname',
        hover_data={'sector': True, 'country': True},
        title='Predicted Security Prices Over Time',
        labels={'predictedprice': 'Predicted Price (USD)', 'predictiondate': 'Date'},
        height=500
    )

    fig.update_layout(
        plot_bgcolor='rgba(240, 242, 245, 0.5)',
        paper_bgcolor='white',
        hovermode='x unified',
        font=dict(family="Arial, sans-serif", size=11),
        title_font_size=16,
        margin=dict(l=60, r=20, t=60, b=40)
    )

    return fig


@callback(
    Output('growth-trajectory-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_growth_graph(data):
    """Top performers by growth trajectory."""
    if not data:
        return go.Figure().add_annotation(text="No data")

    df = pd.read_json(data, orient='split')
    metrics = calculate_metrics(df)

    if not metrics:
        return go.Figure().add_annotation(text="Insufficient data")

    # Sort by growth and get top 10
    sorted_metrics = sorted(metrics.items(), key=lambda x: x[1]['growth'], reverse=True)[:10]
    tickers = [t[0] for t in sorted_metrics]
    growth_values = [t[1]['growth'] for t in sorted_metrics]

    colors = ['#22c55e' if v >= 0 else '#ef4444' for v in growth_values]

    fig = go.Figure(data=[
        go.Bar(
            x=tickers,
            y=growth_values,
            marker_color=colors,
            text=[f'{v:.1f}%' for v in growth_values],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Growth: %{y:.2f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        title='Fastest Growth Trajectory',
        xaxis_title='Ticker',
        yaxis_title='Growth (%)',
        plot_bgcolor='rgba(240, 242, 245, 0.5)',
        paper_bgcolor='white',
        height=350,
        showlegend=False,
        font=dict(size=10),
        margin=dict(l=50, r=20, t=50, b=30)
    )

    return fig


@callback(
    Output('volatility-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_volatility_graph(data):
    """Most volatile securities."""
    if not data:
        return go.Figure().add_annotation(text="No data")

    df = pd.read_json(data, orient='split')
    metrics = calculate_metrics(df)

    if not metrics:
        return go.Figure().add_annotation(text="Insufficient data")

    sorted_metrics = sorted(metrics.items(), key=lambda x: x[1]['volatility'], reverse=True)[:10]
    tickers = [t[0] for t in sorted_metrics]
    volatility_values = [t[1]['volatility'] for t in sorted_metrics]

    fig = go.Figure(data=[
        go.Bar(
            x=tickers,
            y=volatility_values,
            marker_color='#f97316',
            text=[f'{v:.2f}%' for v in volatility_values],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Volatility: %{y:.2f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        title='Most Volatile Securities',
        xaxis_title='Ticker',
        yaxis_title='Volatility (%)',
        plot_bgcolor='rgba(240, 242, 245, 0.5)',
        paper_bgcolor='white',
        height=350,
        showlegend=False,
        font=dict(size=10),
        margin=dict(l=50, r=20, t=50, b=30)
    )

    return fig


@callback(
    Output('price-distribution-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_distribution_graph(data):
    """Price distribution histogram."""
    if not data:
        return go.Figure().add_annotation(text="No data")

    df = pd.read_json(data, orient='split')

    fig = px.histogram(
        df,
        x='predictedprice',
        nbins=30,
        title='Price Distribution',
        labels={'predictedprice': 'Predicted Price (USD)'},
        color_discrete_sequence=['#3b82f6']
    )

    fig.update_layout(
        plot_bgcolor='rgba(240, 242, 245, 0.5)',
        paper_bgcolor='white',
        height=350,
        showlegend=False,
        font=dict(size=10),
        margin=dict(l=50, r=20, t=50, b=30)
    )

    return fig


@callback(
    Output('marketcap-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_marketcap_graph(data):
    """Market cap vs predicted price scatter."""
    if not data:
        return go.Figure().add_annotation(text="No data")

    df = pd.read_json(data, orient='split')
    df_unique = df.drop_duplicates(subset=['ticker'])

    fig = px.scatter(
        df_unique,
        x='marketcap',
        y='predictedprice',
        color='sector',
        hover_name='ticker',
        title='Market Cap vs Predicted Price',
        labels={'marketcap': 'Market Cap (USD)', 'predictedprice': 'Predicted Price (USD)'},
        height=350
    )

    fig.update_xaxes(type='log')
    fig.update_layout(
        plot_bgcolor='rgba(240, 242, 245, 0.5)',
        paper_bgcolor='white',
        showlegend=False,
        font=dict(size=10),
        margin=dict(l=50, r=20, t=50, b=30)
    )

    return fig


@callback(
    Output('sector-distribution-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_sector_graph(data):
    """Sector distribution."""
    if not data:
        return go.Figure().add_annotation(text="No data")

    df = pd.read_json(data, orient='split')
    sector_counts = df['sector'].value_counts()

    fig = px.pie(
        values=sector_counts.values,
        names=sector_counts.index,
        title='Distribution by Sector',
        height=350
    )

    fig.update_layout(
        paper_bgcolor='white',
        font=dict(size=10),
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


@callback(
    [Output('sector-filter', 'value'),
     Output('industry-filter', 'value'),
     Output('country-filter', 'value'),
     Output('marketcap-filter', 'value')],
    Input('reset-button', 'n_clicks'),
    prevent_initial_call=True
)
def reset_filters(n_clicks):
    """Reset all filters to default values."""
    return 'all', 'all', 'all', [0, 10000000000000]


# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    app.run(debug=True, port=8050)



