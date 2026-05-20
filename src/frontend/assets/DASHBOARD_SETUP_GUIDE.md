# Security Price Predictions Dashboard - Setup Guide

## Overview

This Dash application provides a comprehensive interactive dashboard for analyzing predicted security prices with filtering capabilities and multiple analytical views.

**Features:**
- Real-time filtering by sector, industry, country, and market cap
- Main time-series visualization of predicted prices
- 5 analytical metric cards showing:
  - Fastest growth trajectory
  - Most volatile securities
  - Price distribution histogram
  - Market cap vs predicted price scatter
  - Sector distribution pie chart

---

## Prerequisites

```bash
pip install dash plotly pandas sqlalchemy psycopg2-binary numpy
```

Or from requirements.txt:
```
dash>=2.14.0
plotly>=5.14.0
pandas>=1.5.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
numpy>=1.24.0
```

---

## Database Requirements

The dashboard expects the following tables and structure:

### Required Tables:
1. **predictpricing** - Predicted price data
   - ticker (VARCHAR) - Security ticker symbol
   - predictiondate (DATE) - Prediction date
   - predictedprice (NUMERIC) - Predicted price value

2. **securities** - Security information
   - ticker (VARCHAR, PRIMARY KEY) - Ticker symbol
   - companyid (INTEGER) - Foreign key to company table

3. **company** - Company information
   - companyid (INTEGER, PRIMARY KEY)
   - companyname (VARCHAR)
   - sector (VARCHAR) - Industry sector
   - industry (VARCHAR) - Specific industry
   - country (VARCHAR) - Country of origin

4. **marketcap** - Market capitalization data
   - companyid (INTEGER) - Foreign key
   - marketcap (BIGINT/NUMERIC) - Market cap value
   - marketcapdate (DATE) - Date of market cap data

---

## Configuration

### 1. Update Database Connection

In `security_pricing_dashboard.py`, line ~25:

```python
DB_URL = "postgresql://username:password@localhost:5432/your_database"
```

Replace with your actual PostgreSQL credentials and database name.

Example:
```python
DB_URL = "postgresql://postgres:mypassword@localhost:5432/stock_prices"
```

### 2. Add CSS Styling (Optional but Recommended)

To apply the professional styling, add the CSS file to your Dash assets folder:

```bash
# Create assets folder in your project directory
mkdir assets

# Copy the CSS file there
cp dashboard_styles.css assets/
```

Dash automatically loads CSS files from the `assets/` folder.

---

## Running the Application

```bash
python security_pricing_dashboard.py
```

The dashboard will be available at `http://localhost:8050`

---

## Features Explained

### Filter Panel

**Sector Filter**
- Dropdown with all unique sectors from your database
- Filters main graph and all metric cards
- Select "All Sectors" to remove filter

**Industry Filter**
- Dropdown with all unique industries
- Works independently of sector filter
- Combine with other filters for precise analysis

**Country Filter**
- Dropdown with all unique countries
- Filter by company headquarters location

**Market Cap Range**
- Dual-handle range slider
- Set minimum and maximum market cap values
- Uses logarithmic scale for better distribution

**Reset Button**
- Clears all filters to default values
- Returns dashboard to initial state

### Main Predictions Graph

- **Type**: Line chart with multiple series (one per ticker)
- **X-axis**: Prediction date
- **Y-axis**: Predicted price (USD)
- **Interactive Features**:
  - Hover to see company name, sector, and country
  - Click legend items to toggle visibility
  - Zoom by dragging
  - Pan by shift-dragging
  - Download as PNG

### Metric Card 1: Fastest Growth Trajectory

- **Type**: Horizontal bar chart
- **Shows**: Top 10 securities by growth percentage
- **Color coding**: 
  - Green = positive growth
  - Red = negative growth (losses)
- **Calculation**: ((Final Price - Start Price) / Start Price) × 100

### Metric Card 2: Most Volatile Securities

- **Type**: Bar chart
- **Shows**: Top 10 most volatile securities
- **Color**: Orange
- **Calculation**: Standard deviation of returns over prediction period

### Metric Card 3: Price Distribution

- **Type**: Histogram
- **Shows**: Distribution of predicted prices across all securities
- **Bins**: 30 (adjustable in code)
- **Use case**: Identify typical price ranges

### Metric Card 4: Market Cap vs Predicted Price

- **Type**: Scatter plot
- **X-axis**: Market cap (logarithmic scale)
- **Y-axis**: Predicted price
- **Color**: Sector (color-coded)
- **Insight**: Relationship between company size and price predictions

### Metric Card 5: Sector Distribution

- **Type**: Pie chart
- **Shows**: Breakdown of securities by sector
- **Interactive**: Click slice to isolate, double-click to reset

---

## Callback Architecture

The dashboard uses Dash callbacks to manage data flow:

```
Filter Inputs → update_data() → filtered_data_store
                                      ↓
              ┌─────────────────────────┼─────────────────────────┐
              ↓                         ↓                         ↓
        update_main_graph()    update_growth_graph()    update_volatility_graph()
              ↓                         ↓                         ↓
         Main Graph              Growth Chart            Volatility Chart
              
        (Similar for Distribution, Market Cap, and Sector graphs)
```

---

## Performance Optimization

### For Large Datasets

1. **Pagination**: Add limit/offset to SQL queries
```python
query += " LIMIT 1000 OFFSET :offset"
```

2. **Caching**: Use `cache_timeout` in callbacks
```python
@callback(..., prevent_initial_call=False)
def my_callback(...):
    # Add caching decorator if using dash-extensions
    pass
```

3. **Data Aggregation**: Pre-aggregate daily data to weekly/monthly

### Example with weekly aggregation:
```python
query = """
SELECT 
    ticker,
    DATE_TRUNC('week', predictiondate) as week,
    AVG(predictedprice) as avg_price,
    MAX(predictedprice) as max_price,
    MIN(predictedprice) as min_price
FROM predictpricing
GROUP BY ticker, DATE_TRUNC('week', predictiondate)
"""
```

---

## Customization

### Change Colors

Edit the color variables in `dashboard_styles.css`:

```css
:root {
    --primary-blue: #0066cc;
    --success-green: #22c55e;
    --danger-red: #ef4444;
    --warning-orange: #f97316;
    /* ... more colors ... */
}
```

### Modify Metrics Calculations

Edit the `calculate_metrics()` function around line ~80:

```python
def calculate_metrics(df):
    metrics = {}
    for ticker in df['ticker'].unique():
        ticker_data = df[df['ticker'] == ticker].sort_values('predictiondate')
        prices = ticker_data['predictedprice'].values
        
        # Add your custom calculations here
        custom_metric = your_function(prices)
        
        metrics[ticker] = {
            'growth': growth,
            'volatility': volatility,
            'custom_metric': custom_metric  # Add custom metric
        }
    
    return metrics
```

### Add New Metric Card

1. Add a new callback with `@callback` decorator
2. Add a new `html.Div` with `dcc.Graph` in the metrics grid
3. Create a new figure-generating function

Example:
```python
@callback(
    Output('my-new-metric-graph', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_my_metric(data):
    if not data:
        return go.Figure().add_annotation(text="No data")
    
    df = pd.read_json(data, orient='split')
    
    # Create your figure
    fig = go.Figure(...)
    
    return fig
```

---

## Troubleshooting

### "No data available" message

**Problem**: Filters return empty dataset
**Solutions**:
- Verify filters match data in database
- Check if prediction data exists for selected date range
- Use reset button to clear filters

### Database connection error

**Problem**: `psycopg2.OperationalError`
**Solutions**:
- Verify credentials in `DB_URL`
- Ensure PostgreSQL server is running
- Check firewall allows connection on port 5432
- Verify database name exists

### Slow dashboard

**Problem**: Graphs take long time to load
**Solutions**:
- Reduce date range in SQL query
- Add indexing to predictpricing table:
  ```sql
  CREATE INDEX idx_predictpricing_ticker 
  ON predictpricing(ticker);
  
  CREATE INDEX idx_predictpricing_date 
  ON predictpricing(predictiondate);
  ```
- Use data aggregation (see Performance Optimization section)

### CSS not applying

**Problem**: Styling not showing
**Solutions**:
- Create `assets/` folder in project root
- Place `dashboard_styles.css` in `assets/`
- Restart Dash application
- Clear browser cache (Ctrl+Shift+Delete)

---

## API Reference

### Main Functions

#### `fetch_prediction_data(filters=None)`
Fetches predicted pricing data with optional filters.

**Parameters:**
```python
filters = {
    'sector': 'Technology',
    'industry': 'Consumer Electronics',
    'country': 'US',
    'marketcap_min': 1000000000,
    'marketcap_max': 3000000000000
}
```

**Returns:** pandas DataFrame

#### `fetch_filter_options()`
Returns unique values for all filter dropdowns.

**Returns:** dict with keys: `sectors`, `industries`, `countries`

#### `calculate_metrics(df)`
Calculates growth and volatility metrics for all tickers.

**Parameters:** pandas DataFrame
**Returns:** dict with ticker metrics

---

## Deployment

### Deploy to Heroku

1. Create `Procfile`:
```
web: gunicorn app:server
```

2. Create `requirements.txt`:
```bash
pip freeze > requirements.txt
```

3. Deploy:
```bash
heroku login
heroku create your-app-name
git push heroku main
```

### Deploy to Cloud

**AWS**: Use Elastic Beanstalk with Gunicorn
**Azure**: Use App Service with Python runtime
**GCP**: Use Cloud Run with containerized deployment

---

## Additional Resources

- [Dash Documentation](https://dash.plotly.com/)
- [Plotly Graph Objects](https://plotly.com/python/graph-objects/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

---

## Support

For issues or questions:
1. Check this guide's troubleshooting section
2. Review Dash documentation
3. Check database connectivity
4. Enable debug mode: `app.run_server(debug=True)`

---

**Version**: 1.0  
**Last Updated**: 2024  
**License**: MIT
