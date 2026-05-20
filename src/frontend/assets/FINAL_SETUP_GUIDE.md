# Security Price Predictions Dashboard - Final Setup Guide

## Database Structure Overview

Your actual database structure includes these tables:

### Key Tables for Dashboard:
1. **predictpricing** - Predicted price data
   - `ticker` - Security ticker symbol
   - `price` - Predicted price value
   - `lower_bound` - Lower confidence bound
   - `upper_bound` - Upper confidence bound
   - `date` - Prediction date
   - Foreign key: `ticker → securities(ticker)`

2. **securities** - Security information
   - `ticker` - Primary identifier
   - `companyid` - Links to company
   - `isin`, `cusip` - Security identifiers
   - Foreign key: `companyid → company(companyid)`

3. **company** - Company information
   - `companyid` - Primary key
   - `companyname` - Company name
   - `sector` - Industry sector
   - `industry` - Specific industry
   - `country` - Country of origin
   - Other fields: address, city, region, website, etc.

4. **marketcap** - Market capitalization
   - `companyid` - Links to company
   - `marketcap` - Market cap value
   - `marketcapdate` - Date of market cap data

### Other Tables (Reference):
- **pricing** - Actual historical pricing (instid, price, date, volume)
- **exchange** - Exchange information
- **corpact** - Corporate actions (dividends, splits)
- **audit_log** - Event logging

---

## What's Different in This Version

### Main Graph: Confidence Intervals

The main graph now displays:
- **Blue prediction line** - Predicted price from `predictpricing.price`
- **Shaded area** - Confidence interval between `lower_bound` and `upper_bound`

This shows the range of uncertainty in your predictions.

### SQL Joins

```
predictpricing (ticker, price, date, lower_bound, upper_bound)
        ↓ (ticker)
securities (ticker, companyid)
        ↓ (companyid)
company (companyid, sector, industry, country, companyname)
        ↓ (companyid)
marketcap (companyid, marketcap)
```

### Column Mapping

| Original Code | Your Database | Data Type |
|---|---|---|
| `predictedprice` | `price` | REAL |
| `predictiondate` | `date` | DATE |
| (new) `lower_bound` | `lower_bound` | REAL |
| (new) `upper_bound` | `upper_bound` | REAL |

---

## Installation & Setup

### 1. Install Dependencies

```bash
pip install dash plotly pandas sqlalchemy psycopg2-binary numpy
```

### 2. Configure Database Connection

Edit line 11 in `security_pricing_dashboard_final.py`:

```python
DB_URL = "postgresql://username:password@localhost:5432/your_database"
```

Replace:
- `username` - Your PostgreSQL user (default: `postgres`)
- `password` - Your PostgreSQL password
- `localhost` - Database server (use your host if remote)
- `5432` - Database port
- `your_database` - Your database name (e.g., `dev_findata`)

**Example:**
```python
DB_URL = "postgresql://postgres:mypassword@localhost:5432/dev-marketdata"
```

### 3. Create Assets Folder for Styling

```bash
mkdir assets
cp dashboard_styles.css assets/
```

If you skip this, the dashboard will still work but without custom styling.

### 4. Run the Application

```bash
python security_pricing_dashboard_final.py
```

The app will start at `http://localhost:8050`

---

## Verify Database Connectivity

Run these queries in PostgreSQL to verify data:

```sql
-- Check predictpricing table
SELECT COUNT(*), MIN(date), MAX(date) FROM predictpricing;
-- Expected: Should return row count and date range

-- Check join works
SELECT COUNT(*)
FROM predictpricing pp
JOIN securities s ON pp.ticker = s.ticker
JOIN company c ON s.companyid = c.companyid;
-- Expected: Should return same count as predictpricing

-- Check filter options exist
SELECT DISTINCT sector FROM company WHERE sector IS NOT NULL LIMIT 5;
SELECT DISTINCT industry FROM company WHERE industry IS NOT NULL LIMIT 5;
SELECT DISTINCT country FROM company WHERE country IS NOT NULL LIMIT 5;
-- Expected: Should return values for dropdowns

-- Check market cap data
SELECT COUNT(*), MIN(marketcap), MAX(marketcap) FROM marketcap WHERE marketcap IS NOT NULL;
-- Expected: Should return count and range for slider
```

---

## Dashboard Features

### 1. Main Predictions Graph
- Shows predicted prices for selected securities
- Includes confidence intervals (shaded areas)
- Interactive: hover for details, click legend to toggle tickers
- Zoom and pan enabled

### 2. Growth Trajectory Chart
- Top 10 securities by percentage growth
- Green bars = positive growth, Red bars = losses
- Calculated as: `(final_price - start_price) / start_price * 100`

### 3. Volatility Chart
- Top 10 most volatile securities
- Orange bars
- Calculated as standard deviation of daily returns

### 4. Price Distribution
- Histogram of all predicted prices
- Shows typical price ranges across portfolio
- 30 bins (adjustable)

### 5. Market Cap vs Price
- Scatter plot: x-axis = market cap (log scale), y-axis = price
- Color-coded by sector
- Only shows latest price per ticker (no duplicates)

### 6. Sector Distribution
- Pie chart showing number of securities per sector
- Interactive: click slice to isolate

---

## Filter Options

### Sector Filter
- Dropdown populated from `company.sector`
- Affects all graphs
- "All Sectors" shows everything

### Industry Filter
- Dropdown populated from `company.industry`
- Works independently of sector (can combine filters)

### Country Filter
- Dropdown populated from `company.country`
- Filters by company headquarters

### Market Cap Range
- Dual-handle slider
- Min: 0, Max: highest market cap in database
- Filters by `marketcap.marketcap` value
- Shows values in billions

### Reset Button
- Clears all filters to default values
- Returns dashboard to initial state

---

## Troubleshooting

### "No data available" Message

**Cause:** Database connection failed or no data

**Fix:**
1. Check database URL is correct
2. Verify PostgreSQL is running: `psql -U postgres`
3. Check database exists: `psql -l` (list databases)
4. Check tables exist: `\dt` (in psql)

### "Insufficient data" in Metrics Cards

**Cause:** A ticker has less than 2 prediction dates

**Fix:** This is normal. The dashboard requires multiple predictions per ticker to calculate growth/volatility.

### Slider not showing correct range

**Cause:** No data in marketcap table

**Fix:**
```sql
SELECT COUNT(*) FROM marketcap WHERE marketcap IS NOT NULL;
```
If result is 0, populate marketcap table first.

### Missing filter options (blank dropdowns)

**Cause:** No data in company.sector/industry/country

**Fix:**
```sql
SELECT COUNT(DISTINCT sector) FROM company;
-- If 0, populate company table with sector data
```

### Graph shows "No market cap data available"

**Cause:** No matching records in marketcap table for filtered tickers

**Fix:** This is okay. The dashboard shows what data is available. Not all companies have market cap data.

---

## Performance Tips

### Large Datasets

If dashboard is slow with many predictions:

1. **Add database indexes:**
```sql
CREATE INDEX idx_predictpricing_ticker ON predictpricing(ticker);
CREATE INDEX idx_predictpricing_date ON predictpricing(date);
CREATE INDEX idx_securities_companyid ON securities(companyid);
```

2. **Aggregate data to daily/weekly:**
```sql
SELECT 
    ticker,
    DATE_TRUNC('day', date) as date,
    AVG(price) as price,
    MIN(lower_bound) as lower_bound,
    MAX(upper_bound) as upper_bound
FROM predictpricing
GROUP BY ticker, DATE_TRUNC('day', date)
ORDER BY ticker, date;
```

3. **Limit date range in query** (modify fetch_prediction_data):
```python
query += " AND pp.date >= CURRENT_DATE - INTERVAL '1 year'"
```

---

## Customization

### Change Main Graph Colors

Edit `update_main_graph()` in the Python file:

```python
fig.add_trace(go.Scatter(
    # ...
    line=dict(width=2, color='#0066cc'),  # Change color here
    # ...
))
```

### Change Metric Card Colors

In `update_growth_graph()`:
```python
colors = ['#22c55e' if v >= 0 else '#ef4444' for v in growth_values]
# #22c55e = green, #ef4444 = red
```

### Adjust Confidence Interval Transparency

In `update_main_graph()`:
```python
fillcolor=f'rgba(0,0,0,0.1)',  # Change 0.1 to 0-1 scale (0=transparent, 1=opaque)
```

### Add More Metric Cards

1. Create new callback function:
```python
@callback(
    Output('my-new-chart', 'figure'),
    Input('filtered-data-store', 'data')
)
def update_my_chart(data):
    # Your code here
    return fig
```

2. Add HTML div:
```python
html.Div([
    dcc.Loading(
        children=[dcc.Graph(id='my-new-chart')]
    )
], className="metric-card")
```

---

## Files Included

1. **security_pricing_dashboard_final.py** - Main application (use this file)
2. **dashboard_styles.css** - Optional styling (copy to `assets/` folder)
3. **DASHBOARD_SETUP_GUIDE.md** - This guide

---

## Running in Production

### Using Gunicorn (Recommended)

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn --workers 4 --bind 0.0.0.0:8050 security_pricing_dashboard_final:app
```

### Using Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8050", "security_pricing_dashboard_final:app"]
```

Build and run:
```bash
docker build -t security-dashboard .
docker run -p 8050:8050 security-dashboard
```

---

## Key Functions Reference

### `fetch_prediction_data(filters=None)`
Fetches predicted prices with optional filters.

**Returns:** pandas DataFrame with columns: ticker, predictiondate, predictedprice, lower_bound, upper_bound, companyname, sector, industry, country, marketcap

### `fetch_filter_options()`
Returns unique sectors, industries, countries.

**Returns:** dict with keys: sectors, industries, countries

### `fetch_marketcap_range()`
Gets min/max market cap for slider.

**Returns:** tuple (min_cap, max_cap)

### `calculate_metrics(df)`
Calculates growth and volatility for each ticker.

**Returns:** dict with metrics for each ticker

---

## Support & Resources

- **Dash Docs:** https://dash.plotly.com/
- **Plotly Docs:** https://plotly.com/python/
- **PostgreSQL Docs:** https://www.postgresql.org/docs/
- **SQLAlchemy Docs:** https://docs.sqlalchemy.org/

---

## Version Info

- **Version:** 1.1 (Final)
- **Updated:** 2024
- **Database:** PostgreSQL 12+
- **Python:** 3.8+
- **Status:** Production Ready

---

## Common Questions

**Q: Can I modify the date range?**
A: Yes, edit the SQL in `fetch_prediction_data()` to add `AND pp.date >= ...` clause.

**Q: Can I export the data?**
A: The data is cached in `filtered-data-store`. You can add a button to download as CSV.

**Q: How often does data refresh?**
A: Data is fetched when filters change. No auto-refresh currently.

**Q: Can I add real-time updates?**
A: Yes, use `dcc.Interval` callback to refresh data periodically.

**Q: Can I deploy to cloud?**
A: Yes, works with Heroku, AWS, Azure, GCP using Docker or native deployment.

---

**Questions?** Check the troubleshooting section or verify your database connectivity first.
