# Main Plot Update: Historical vs Predicted Prices

## Overview

The main plot now displays **both historical and predicted pricing data** on the same graph, allowing you to see how predictions compare to actual historical performance.

---

## What's New

### New Function: `fetch_historical_pricing_data(ticker)`

Fetches historical pricing data from the `pricing` table.

**Query Details:**
```sql
SELECT 
    s.ticker,
    p.date,
    p.price as historical_price,
    p.volume,
    p.avgvolume
FROM pricing p
JOIN securities s ON p.instid = s.securid
WHERE s.ticker = :ticker
ORDER BY p.date
```

**Key Points:**
- Links `pricing` table (instid-based) to `securities` table (ticker-based)
- Uses `p.instid = s.securid` foreign key join
- Returns historical prices with dates and trading volume

### Updated Main Graph: `update_main_graph()`

The main plot now shows three layers for each ticker:

1. **Historical Price Line** (Dashed Gray)
   - Color: `#9ca3af` (gray)
   - Style: Dashed line
   - Label: "{TICKER} - Historical"
   - Data from: `pricing` table

2. **Confidence Interval** (Light Blue Shaded Area)
   - Fill color: `rgba(59, 130, 246, 0.15)` (light blue, 15% opacity)
   - Between: `lower_bound` and `upper_bound`
   - Label: "{TICKER} - Confidence Interval"
   - Data from: `predictpricing` table

3. **Predicted Price Line** (Solid Blue)
   - Color: `#3b82f6` (bright blue)
   - Style: Solid line, width 3
   - Label: "{TICKER} - Predicted"
   - Data from: `predictpricing` table

---

## Visual Design

```
Legend shows:
├── AAPL - Historical          (gray dashed line)
├── AAPL - Confidence Interval (light blue shaded area)
├── AAPL - Predicted           (bright blue solid line)
├── GOOGL - Historical         (gray dashed line)
├── GOOGL - Confidence Interval
└── GOOGL - Predicted          (bright blue solid line)
```

### Color Scheme

| Element | Color | Hex Code | Purpose |
|---------|-------|----------|---------|
| Historical Price | Gray | #9ca3af | Past performance |
| Predicted Price | Bright Blue | #3b82f6 | Model prediction |
| Confidence Interval | Light Blue | rgba(59, 130, 246, 0.15) | Uncertainty range |

---

## Database Tables Used

### pricing table
- `instid` - Instrument ID (primary key)
- `price` - Historical price
- `date` - Trading date
- `volume` - Trading volume
- `avgvolume` - Average volume

### securities table
- `securid` - Security ID (links to pricing.instid)
- `ticker` - Ticker symbol

### predictpricing table
- `ticker` - Ticker symbol
- `date` - Prediction date
- `price` - Predicted price
- `lower_bound` - Lower confidence bound
- `upper_bound` - Upper confidence bound

---

## Interaction Features

### Hover Information
When hovering over the graph:
- **Historical price**: Shows date and price in gray
- **Predicted price**: Shows date and price in blue
- **Confidence bounds**: Shows upper/lower bound values

### Legend Controls
- Click legend item to toggle visibility
- Double-click to isolate one ticker
- Multiple tickers can be shown simultaneously

### Zoom & Pan
- Drag to zoom
- Shift+drag to pan
- Double-click to reset view

---

## Example Scenarios

### Scenario 1: Validating Model Accuracy
Compare historical prices with predictions made for historical dates:
```
If prediction_date is in the past:
  - Historical line shows what actually happened
  - Predicted line shows what model predicted
  - Gap = model error
```

### Scenario 2: Future Predictions
When viewing future dates:
```
Historical line ends at last available data
Predicted line continues into future
Confidence interval shows uncertainty
```

### Scenario 3: Multiple Securities
View several tickers at once:
```
Each ticker has its own 3-layer visualization
Easy to compare growth and volatility patterns
Can isolate individual tickers via legend
```

---

## Technical Implementation

### Join Process

1. **Get prediction data** (already filtered)
   ```
   From filtered-data-store → df
   ```

2. **For each ticker in predictions:**
   ```
   ticker = 'AAPL'
   
   Get historical data:
   pricing → join on instid = securid → where ticker = 'AAPL'
   
   Combine with predicted data:
   predictpricing where ticker = 'AAPL'
   ```

3. **Plot layers** (in order):
   - Upper confidence bound (invisible, for fill reference)
   - Lower confidence bound (fills to upper)
   - Historical line (over the fill)
   - Predicted line (on top)

### Performance Considerations

**For Large Datasets:**
- Historical data fetched per ticker (not all at once)
- Only fetches tickers shown in filtered results
- Runs only when filters change

**Optimization Tips:**
```sql
-- Add indexes to improve performance
CREATE INDEX idx_pricing_instid ON pricing(instid);
CREATE INDEX idx_securities_securid ON securities(securid);
CREATE INDEX idx_securities_ticker ON securities(ticker);
```

---

## Error Handling

### If Historical Data Missing
- Historical line won't be displayed
- Confidence interval and predicted line still shown
- No error message (graceful degradation)

### If Prediction Data Missing
- Shows error annotation
- "No data matches selected filters"

### If Database Connection Fails
- Shows error annotation
- "No data available - check your filters or database connection"

---

## Customization Options

### Change Historical Line Color
In `fetch_historical_pricing_data()` section:
```python
line=dict(width=2, color='#YOUR_COLOR', dash='dash')
```

### Change Prediction Line Color
In confidence interval section:
```python
line=dict(width=3, color='#YOUR_COLOR')
```

### Change Confidence Interval Transparency
Adjust opacity (0 = transparent, 1 = opaque):
```python
fillcolor='rgba(59, 130, 246, 0.25)'  # 25% instead of 15%
```

### Change Line Styles
```python
# Dashed options:
dash='dash'      # Long dashes
dash='dot'       # Dots
dash='dashdot'   # Dash-dot pattern
dash='solid'     # Solid line (default)
```

---

## Testing Queries

Verify your data is accessible:

```sql
-- Test historical pricing
SELECT COUNT(*), MIN(date), MAX(date) FROM pricing;

-- Test securities join
SELECT COUNT(DISTINCT s.ticker)
FROM pricing p
JOIN securities s ON p.instid = s.securid;

-- Test prediction data
SELECT COUNT(*), MIN(date), MAX(date) FROM predictpricing;

-- Test combined
SELECT COUNT(*)
FROM predictpricing pp
WHERE pp.ticker IN (
    SELECT DISTINCT s.ticker
    FROM pricing p
    JOIN securities s ON p.instid = s.securid
);
```

---

## Troubleshooting

### Historical line not showing
**Problem:** `fetch_historical_pricing_data()` returns empty dataframe

**Debug:**
```python
# Add to update_main_graph for debugging
historical_df = fetch_historical_pricing_data(ticker)
print(f"{ticker}: {len(historical_df)} historical records")
```

**Solutions:**
1. Check `pricing` table has data
2. Check `securities` table has correct `securid` values
3. Verify `ticker` exists in both tables

### Confidence interval not showing
**Problem:** `lower_bound` or `upper_bound` is NULL

**Solutions:**
```sql
-- Check for nulls
SELECT COUNT(*) FROM predictpricing WHERE lower_bound IS NULL;
SELECT COUNT(*) FROM predictpricing WHERE upper_bound IS NULL;

-- Update null bounds
UPDATE predictpricing
SET lower_bound = price * 0.95,
    upper_bound = price * 1.05
WHERE lower_bound IS NULL OR upper_bound IS NULL;
```

### Graph shows only predictions (no historical)
**Problem:** Pricing table doesn't have data for filtered tickers

**Solutions:**
1. Check which tickers have pricing data: 
   ```sql
   SELECT DISTINCT s.ticker FROM pricing p 
   JOIN securities s ON p.instid = s.securid;
   ```
2. Populate pricing table with historical data
3. Select different filters with available data

---

## Version Changes

**v1.1 → v1.2 Changes:**

| Component | Before | After |
|-----------|--------|-------|
| Main Graph | Predictions only | Historical + Predicted |
| Historical Data | None | From `pricing` table |
| Line Count | 3 per ticker | 5 per ticker (3 layers) |
| Title | "Predicted Security Prices" | "Historical vs Predicted Security Prices" |
| Legend Items | 2 per ticker | 3 per ticker |

---

## Summary

The updated dashboard now provides:
✅ Historical context for predictions
✅ Validation against past performance
✅ Confidence intervals visualized
✅ Professional multi-layer visualization
✅ Better insights into model accuracy

---

**Questions?** Check your database tables or verify the joins are working correctly.
