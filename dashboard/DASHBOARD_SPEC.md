# Power BI Dashboard Spec — Olist E-commerce

A 3-page Power BI report built on top of `analytics.fact_orders` + `analytics.dim_*`. Designed for a Head of Operations + Head of Marketing audience.

## Connection

- **Source:** DuckDB → export `analytics.*` to CSV/Parquet, OR connect Power BI directly via the [DuckDB ODBC driver](https://duckdb.org/docs/api/odbc/overview.html).
- **Refresh:** daily, batch.

## Pages

### Page 1 — Executive Overview

KPI cards (top row):

| KPI | DAX |
|-----|-----|
| Total Revenue | `SUM(fact_orders[gross_revenue])` |
| Orders | `COUNTROWS(fact_orders)` |
| Avg Order Value | `[Total Revenue] / [Orders]` |
| Avg Review Score | `AVERAGE(fact_orders[review_score])` |
| % Late Deliveries | `DIVIDE(CALCULATE([Orders], fact_orders[delivery_lag_days] > 0), [Orders])` |

Visuals:
- Line chart: monthly revenue with 12-mo rolling avg
- Bar chart: top 15 product categories by revenue
- Map: revenue by customer state (filled map, Brazil)

### Page 2 — Customer & Cohort

- Cohort retention heatmap (matrix visual, conditional formatting). Measure:
  ```dax
  Retention Rate =
  VAR _cohort = SELECTEDVALUE(dim_date[month_start])
  VAR _cohortSize = CALCULATE([Distinct Customers], dim_date[month_start] = _cohort, fact_orders[months_since_first] = 0)
  RETURN DIVIDE([Distinct Customers], _cohortSize)
  ```
- Bar chart: avg CLV by state
- Scatter: review score vs delivery lag, sized by orders
- Card: 90-day repeat-purchase rate

### Page 3 — Operations

- Waterfall: delivery time decomposition (purchase → carrier → customer)
- Bar chart: worst-rated sellers (review score <= 2 share), with revenue-at-risk column
- Bar chart: freight share of revenue by category
- Heatmap: orders by day-of-week × month-of-year

## Slicers (global)

- Date range (purchase date)
- Customer state
- Product category
- Payment type

## Theme

- **Palette:** `#2E86AB` (primary), `#06A77D` (positive), `#F18F01` (warn), `#C73E1D` (alert), neutral greys.
- **Font:** Segoe UI, 11pt body, 14pt headers.
- **Chart density:** at most 4 visuals per page above the fold.

## Export

Final dashboard exported to:
- `outputs/dashboard.pbix` (Power BI Desktop file — too large for git, ignored)
- `outputs/dashboard_screenshots/` (PNG exports — committed)

## Equivalent in Tableau

If you prefer Tableau Public, every measure above maps 1:1 to a Tableau calculated field. The cohort heatmap is built with `INDEX()` and `MIN(order_purchase_timestamp)` LOD calculations.
