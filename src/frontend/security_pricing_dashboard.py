import dash
import os
from dash import dcc, html, callback, Input, Output
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# ============================================
# DATABASE CONNECTION
# ============================================
# Configure your database connection
DB_PASSWORD = os.environ['DB_PASSWORD']
DATABASE = os.environ['DATABASE']
DB_URL = f"postgresql://postgres:{DB_PASSWORD}@localhost:5432/{DATABASE}"
engine = create_engine(DB_URL)

# ============================================
# DATA FETCHING FUNCTIONS
# ============================================

def fetch_prediction_data(filters=None):
    """
    Fetch predicted pricing data with optional filters.
    
    Table structure:
    - predictpricing: securid, forecast_date, predicted_open, predicted_high, predicted_low, predicted_close, confidence_interval
    - securities: securid, ticker, companyid, isin, cusip
    - company: companyid, sector, industry, country, companyname
    - marketcap: companyid, marketcap, marketcapdate
    """
    query = """
    SELECT 
        s.ticker,
        pp.forecast_date,
        pp.predicted_close,
        pp.predicted_open,
        pp.predicted_high,
        pp.predicted_low,
        pp.confidence_interval,
        c.companyid,
        c.companyname,
        c.sector,
        c.industry,
        c.country,
        m.marketcap,
        s.isin,
        s.cusip
    FROM predictpricing pp
    JOIN securities s ON pp.securid = s.securid
    JOIN company c ON s.companyid = c.companyid
    LEFT JOIN marketcap m ON c.companyid = m.companyid
    WHERE 1=1
    """
    
    params = {}
    
    if filters:
        if filters.get('sector'):
            query += " AND c.sector = :sector"
            params['sector'] = filters['sector']
        if filters.get('industry'):
            query += " AND c.industry = :industry"
            params['industry'] = filters['industry']
        if filters.get('country'):
            query += " AND c.country = :country"
            params['country'] = filters['country']
        if filters.get('marketcap_min'):
            query += " AND m.marketcap >= :marketcap_min"
            params['marketcap_min'] = filters['marketcap_min']
        if filters.get('marketcap_max'):
            query += " AND m.marketcap <= :marketcap_max"
            params['marketcap_max'] = filters['marketcap_max']
    
    query += " ORDER BY s.ticker, pp.forecast_date"
    
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params)
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        # Convert date to datetime if it exists
        if not df.empty and 'forecast_date' in df.columns:
            df['forecast_date'] = pd.to_datetime(df['forecast_date'])
        
        print(f"✅ Fetched {len(df)} rows with columns: {df.columns.tolist()}")
        return df
    except Exception as e:
        print(f"❌ Error fetching prediction data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def fetch_filter_options():
    """Fetch unique values for filter dropdowns from company table."""
    try:
        with engine.begin() as conn:
            sectors = pd.read_sql(
                text("SELECT DISTINCT sector FROM company WHERE sector IS NOT NULL ORDER BY sector;"),
                conn
            )['sector'].tolist()
            
            industries = pd.read_sql(
                text("SELECT DISTINCT industry FROM company WHERE industry IS NOT NULL ORDER BY industry;"),
                conn
            )['industry'].tolist()
            
            countries = pd.read_sql(
                text("SELECT DISTINCT country FROM company WHERE country IS NOT NULL ORDER BY country;"),
                conn
            )['country'].tolist()
        
        return {
            'sectors': sectors,
            'industries': industries,
            'countries': countries
        }
    except Exception as e:
        print(f"Error fetching filter options: {e}")
        return {
            'sectors': [],
            'industries': [],
            'countries': []
        }

def fetch_marketcap_range():
    """Fetch min and max market cap values for slider bounds."""
    try:
        with engine.begin() as conn:
            result = pd.read_sql(
                text("""
                SELECT 
                    COALESCE(MIN(marketcap), 0) as min_cap,
                    COALESCE(MAX(marketcap), 10000000000000) as max_cap
                FROM marketcap
                WHERE marketcap IS NOT NULL;
                """),
                conn
            )
        
        min_cap = int(result.iloc[0]['min_cap']) if not result.empty else 0
        max_cap = int(result.iloc[0]['max_cap']) if not result.empty else 10000000000000
        
        return min_cap, max_cap
    except Exception as e:
        print(f"Error fetching market cap range: {e}")
        return 0, 10000000000000

def calculate_metrics(df):
    """
    Calculate metrics for output factors.
    Uses predicted_close from predictpricing table.
    Returns dict with growth_trajectory, volatility, etc.
    """
    metrics = {}
    
    if df.empty or 'ticker' not in df.columns:
        return metrics
    
    for ticker in df['ticker'].unique():
        ticker_data = df[df['ticker'] == ticker].sort_values('forecast_date')
        
        if len(ticker_data) < 2:
            continue
        
        prices = ticker_data['predicted_close'].values
        
        # Growth trajectory (% change from first to last prediction)
        growth = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] != 0 else 0
        
        # Volatility (standard deviation of returns)
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * 100 if len(returns) > 0 else 0
        
        # Get company info from first row
        company_info = ticker_data.iloc[0]
        
        metrics[ticker] = {
            'growth': growth,
            'volatility': volatility,
            'current_price': float(prices[-1]),
            'start_price': float(prices[0]),
            'companyname': company_info.get('companyname', ticker),
            'sector': company_info.get('sector', 'Unknown'),
            'num_predictions': len(ticker_data)
        }
    
    return metrics

def fetch_rolling_sharpe_data(tickers: list[str], window: int) -> pd.DataFrame:
    """Fetch rolling Sharpe and cumulative return data for selected tickers."""
    if not tickers:
        return pd.DataFrame()
    ticker_list = ", ".join(f"'{t}'" for t in tickers)
    query = f"""
        SELECT s.ticker, rs.date, rs.sharpe, dlr.log_return
        FROM rolling_sharpe rs
        JOIN securities s ON rs.securid = s.securid
        LEFT JOIN daily_log_returns dlr
            ON dlr.securid = rs.securid AND dlr.date = rs.date
        WHERE s.ticker IN ({ticker_list})
          AND rs.window_days = :window
        ORDER BY s.ticker, rs.date
    """
    try:
        with engine.begin() as conn:
            df = pd.read_sql(text(query), conn, params={"window": window})
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        print(f"Error fetching rolling Sharpe data: {e}")
        return pd.DataFrame()


def fetch_sharpe_tickers() -> list[str]:
    """Return tickers that have data in rolling_sharpe."""
    try:
        with engine.begin() as conn:
            df = pd.read_sql(
                text("""
                    SELECT DISTINCT s.ticker
                    FROM rolling_sharpe rs
                    JOIN securities s ON rs.securid = s.securid
                    ORDER BY s.ticker
                """),
                conn
            )
        return df["ticker"].tolist()
    except Exception as e:
        print(f"Error fetching Sharpe tickers: {e}")
        return []
# ============================================
# DASH APP INITIALIZATION
# ============================================

app = dash.Dash(__name__)
app.title = "Security Price Predictions"

# Load initial filter options
filter_options = fetch_filter_options()
min_cap, max_cap = fetch_marketcap_range()
sharpe_tickers = fetch_sharpe_tickers()

# ============================================
# APP LAYOUT
# ============================================

app.layout = html.Div([
    # Header
    html.Div([
        html.H1("Security Price Predictions", className="dashboard-title"),
        html.P("Analyze predicted pricing trends with confidence intervals and performance metrics", className="dashboard-subtitle")
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
                    max=max_cap,
                    step=max(1, max_cap / 20),
                    marks={
                        0: '$0',
                        max_cap * 0.25: f'${max_cap * 0.25 / 1e9:.0f}B',
                        max_cap * 0.5: f'${max_cap * 0.5 / 1e9:.0f}B',
                        max_cap * 0.75: f'${max_cap * 0.75 / 1e9:.0f}B',
                        max_cap: f'${max_cap / 1e9:.0f}B'
                    },
                    value=[0, max_cap],
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
    dcc.Store(id='filtered-data-store'),

# Analytics Section
    html.Div([
        html.H2("Risk Analytics", style={"marginBottom": "16px", "fontSize": "18px", "fontWeight": "600"}),

        # Controls
        html.Div([
            html.Div([
                html.Label("Tickers", className="filter-label"),
                dcc.Dropdown(
                    id="sharpe-ticker-filter",
                    options=[{"label": t, "value": t} for t in sharpe_tickers],
                    value=sharpe_tickers[:6] if len(sharpe_tickers) >= 6 else sharpe_tickers,
                    multi=True,
                    className="filter-dropdown",
                    placeholder="Select tickers..."
                )
            ], style={"flex": "1", "minWidth": "300px"}),

            html.Div([
                html.Label("Rolling Window", className="filter-label"),
                dcc.Dropdown(
                    id="sharpe-window-filter",
                    options=[
                        {"label": "30-day",  "value": 30},
                        {"label": "60-day",  "value": 60},
                        {"label": "120-day", "value": 120},
                        {"label": "252-day", "value": 252},
                    ],
                    value=60,
                    clearable=False,
                    className="filter-dropdown",
                    style={"width": "160px"}
                )
            ])
        ], style={"display": "flex", "gap": "20px", "alignItems": "flex-end",
                  "marginBottom": "16px", "flexWrap": "wrap"}),

        # Charts
        html.Div([
            html.Div([
                dcc.Loading(
                    type="default",
                    children=[dcc.Graph(id="rolling-sharpe-graph")]
                )
            ], className="main-graph-container"),

            html.Div([
                dcc.Loading(
                    type="default",
                    children=[dcc.Graph(id="cumulative-returns-graph")]
                )
            ], className="main-graph-container"),
        ]),

    ], style={"marginTop": "30px", "backgroundColor": "white",
              "borderRadius": "8px", "padding": "20px",
              "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}),

    dcc.Store(id="sharpe-data-store"),
    
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
    if df.empty:
        return None
    
    return df.to_json(date_format='iso', orient='split')

@callback(
    Output('main-predictions-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_main_graph(data):
    """
    Update main predictions graph.
    Shows predicted prices with confidence intervals.
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available - check your filters or database connection",
            showarrow=False,
            font=dict(size=14)
        )
        fig.update_layout(height=500)
        return fig
    
    df = pd.read_json(data, orient='split')
    
    if df.empty or 'ticker' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No data matches selected filters",
            showarrow=False,
            font=dict(size=14)
        )
        fig.update_layout(height=500)
        return fig
    
    # Convert forecast_date back to datetime
    df['forecast_date'] = pd.to_datetime(df['forecast_date'])
    
    fig = go.Figure()
    
    # Add a line for each ticker with confidence intervals
    for ticker in df['ticker'].unique():
        ticker_df = df[df['ticker'] == ticker].sort_values('forecast_date')
        company_name = ticker_df['companyname'].iloc[0]

        # Calculate confidence interval bounds
        ticker_df = ticker_df.copy()
        ticker_df['confidence_pct'] = ticker_df['confidence_interval'] / 100
        ticker_df['upper_bound'] = ticker_df['predicted_close'] * (1 + ticker_df['confidence_pct'])
        ticker_df['lower_bound'] = ticker_df['predicted_close'] * (1 - ticker_df['confidence_pct'])
        
        # Upper bound (invisible line for fill reference)
        fig.add_trace(go.Scatter(
            x=ticker_df['forecast_date'],
            y=ticker_df['upper_bound'],
            fill=None,
            mode='lines',
            line_color='rgba(0,0,0,0)',
            showlegend=False,
            hovertemplate='Upper Bound: $%{y:.2f}<extra></extra>'
        ))
        
        # Lower bound (creates filled area between upper and lower)
        fig.add_trace(go.Scatter(
            x=ticker_df['forecast_date'],
            y=ticker_df['lower_bound'],
            fill='tonexty',
            mode='lines',
            line_color='rgba(0,0,0,0)',
            name=f"{ticker} - Confidence Interval",
            fillcolor='rgba(59, 130, 246, 0.15)',
            showlegend=True,
            hovertemplate='Lower Bound: $%{y:.2f}<extra></extra>'
        ))
        
        # Main prediction line
        fig.add_trace(go.Scatter(
            x=ticker_df['forecast_date'],
            y=ticker_df['predicted_close'],
            mode='lines',
            name=f"{ticker} ({company_name})",
            line=dict(width=2),
            hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Price: $%{y:.2f}<br>Confidence: %{customdata:.1f}%<extra></extra>',
            customdata=ticker_df['confidence_interval']
        ))
    
    fig.update_layout(
        title='Predicted Security Prices with Confidence Intervals',
        xaxis_title='Date',
        yaxis_title='Price (USD)',
        plot_bgcolor='rgba(240, 242, 245, 0.5)',
        paper_bgcolor='white',
        hovermode='x unified',
        font=dict(family="Arial, sans-serif", size=11),
        title_font_size=16,
        margin=dict(l=60, r=20, t=60, b=40),
        height=500,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99
        )
    )
    
    return fig

@callback(
    Output('growth-trajectory-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_growth_graph(data):
    """Top performers by growth trajectory."""
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data")
        fig.update_layout(height=350)
        return fig
    
    try:
        df = pd.read_json(data, orient='split')
        
        if df.empty or 'ticker' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(text="No ticker data available")
            fig.update_layout(height=350)
            return fig
        
        df['forecast_date'] = pd.to_datetime(df['forecast_date'])
        metrics = calculate_metrics(df)
        
        if not metrics:
            fig = go.Figure()
            fig.add_annotation(text="Insufficient data")
            fig.update_layout(height=350)
            return fig
        
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
    except Exception as e:
        print(f"Error in update_growth_graph: {e}")
        import traceback
        traceback.print_exc()
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}")
        fig.update_layout(height=350)
        return fig

@callback(
    Output('volatility-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_volatility_graph(data):
    """Most volatile securities."""
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data")
        fig.update_layout(height=350)
        return fig
    
    df = pd.read_json(data, orient='split')
    
    if df.empty or 'ticker' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No ticker data")
        fig.update_layout(height=350)
        return fig
    
    df['forecast_date'] = pd.to_datetime(df['forecast_date'])
    metrics = calculate_metrics(df)
    
    if not metrics:
        fig = go.Figure()
        fig.add_annotation(text="Insufficient data")
        fig.update_layout(height=350)
        return fig
    
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
        fig = go.Figure()
        fig.add_annotation(text="No data")
        fig.update_layout(height=350)
        return fig
    
    df = pd.read_json(data, orient='split')
    
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data")
        fig.update_layout(height=350)
        return fig
    
    fig = px.histogram(
        df,
        x='predicted_close',
        nbins=30,
        title='Price Distribution',
        labels={'predicted_close': 'Forecasted Price (USD)'},
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
        fig = go.Figure()
        fig.add_annotation(text="No data")
        fig.update_layout(height=350)
        return fig
    
    df = pd.read_json(data, orient='split')
    
    if df.empty or 'ticker' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No ticker data")
        fig.update_layout(height=350)
        return fig
    
    # Get the latest price for each ticker
    df_latest = df.sort_values('forecast_date').drop_duplicates(subset=['ticker'], keep='last')
    
    # Remove rows with null marketcap
    df_latest = df_latest.dropna(subset=['marketcap'])
    
    if df_latest.empty:
        fig = go.Figure()
        fig.add_annotation(text="No market cap data available")
        fig.update_layout(height=350)
        return fig
    
    fig = px.scatter(
        df_latest,
        x='marketcap',
        y='predicted_close',
        color='sector',
        hover_name='ticker',
        hover_data={
            'companyname': True,
            'sector': True,
            'marketcap': ':,.0f',
            'predicted_close': ':.2f'
        },
        title='Market Cap vs Predicted Price',
        labels={'marketcap': 'Market Cap (USD)', 'predicted_close': 'Predicted Price (USD)'},
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
        fig = go.Figure()
        fig.add_annotation(text="No data")
        fig.update_layout(height=350)
        return fig
    
    df = pd.read_json(data, orient='split')
    
    if df.empty or 'ticker' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No ticker data")
        fig.update_layout(height=350)
        return fig
    
    # Get unique sectors by ticker
    df_unique = df.drop_duplicates(subset=['ticker'])
    sector_counts = df_unique['sector'].value_counts()
    
    if sector_counts.empty:
        fig = go.Figure()
        fig.add_annotation(text="No sector data available")
        fig.update_layout(height=350)
        return fig
    
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
    return 'all', 'all', 'all', [0, max_cap]

@callback(
    Output("sharpe-data-store", "data"),
    Input("sharpe-ticker-filter", "value"),
    Input("sharpe-window-filter", "value"),
)
def update_sharpe_store(tickers, window):
    if not tickers:
        return None
    df = fetch_rolling_sharpe_data(tickers, window)
    return df.to_json(date_format="iso", orient="split") if not df.empty else None


@callback(
    Output("rolling-sharpe-graph", "figure"),
    Input("sharpe-data-store", "data"),
    Input("sharpe-window-filter", "value"),
)
def update_sharpe_graph(data, window):
    empty = go.Figure()
    empty.add_annotation(text="No data — select tickers with computed Sharpe ratios",
                         showarrow=False, font=dict(size=13))
    empty.update_layout(height=450)

    if not data:
        return empty

    df = pd.read_json(data, orient="split")
    if df.empty or "sharpe" not in df.columns:
        return empty

    df["date"] = pd.to_datetime(df["date"])
    fig = go.Figure()

    for ticker in df["ticker"].unique():
        tdf = df[df["ticker"] == ticker].sort_values("date")
        fig.add_trace(go.Scatter(
            x=tdf["date"],
            y=tdf["sharpe"],
            mode="lines",
            name=ticker,
            hovertemplate="<b>%{fullData.name}</b><br>%{x|%Y-%m-%d}<br>Sharpe: %{y:.2f}<extra></extra>"
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=0.8)
    fig.add_hline(y=1, line_dash="dot",  line_color="green", line_width=0.8,
                  annotation_text="Sharpe = 1", annotation_position="bottom right")

    fig.update_layout(
        title=f"Rolling Sharpe Ratio ({window}-day)",
        xaxis_title="Date",
        yaxis_title="Sharpe Ratio",
        plot_bgcolor="rgba(240, 242, 245, 0.5)",
        paper_bgcolor="white",
        hovermode="x unified",
        height=450,
        font=dict(size=11),
        margin=dict(l=60, r=20, t=60, b=40),
        legend=dict(orientation="v", yanchor="top", y=0.99, xanchor="right", x=0.99)
    )
    return fig


@callback(
    Output("cumulative-returns-graph", "figure"),
    Input("sharpe-data-store", "data"),
)
def update_cumulative_returns_graph(data):
    empty = go.Figure()
    empty.add_annotation(text="No return data available", showarrow=False, font=dict(size=13))
    empty.update_layout(height=450)

    if not data:
        return empty

    df = pd.read_json(data, orient="split")
    if df.empty or "log_return" not in df.columns:
        return empty

    df["date"] = pd.to_datetime(df["date"])
    fig = go.Figure()

    for ticker in df["ticker"].unique():
        tdf = df[df["ticker"] == ticker].sort_values("date").dropna(subset=["log_return"])
        cumulative = np.exp(np.cumsum(tdf["log_return"].values))
        fig.add_trace(go.Scatter(
            x=tdf["date"],
            y=cumulative,
            mode="lines",
            name=ticker,
            hovertemplate="<b>%{fullData.name}</b><br>%{x|%Y-%m-%d}<br>Growth: $%{y:.3f}<extra></extra>"
        ))

    fig.add_hline(y=1, line_dash="dash", line_color="black", line_width=0.8)
    fig.update_layout(
        title="Cumulative Returns (Growth of $1)",
        xaxis_title="Date",
        yaxis_title="Growth of $1",
        plot_bgcolor="rgba(240, 242, 245, 0.5)",
        paper_bgcolor="white",
        hovermode="x unified",
        height=450,
        font=dict(size=11),
        margin=dict(l=60, r=20, t=60, b=40),
        legend=dict(orientation="v", yanchor="top", y=0.99, xanchor="right", x=0.99)
    )
    return fig
# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    app.run(debug=True, port=8050)
