-- 04_window_functions.sql
-- Window function showcase on the Olist warehouse.
-- Run after 03_business_questions.sql so the dim/fact tables exist.
--
-- These five queries demonstrate the SQL idioms that recurring DA interviews
-- screen for: ranking, running totals, lead/lag, percentile bucketing,
-- and per-partition aggregates.

------------------------------------------------------------------------
-- 1. Top 10 customers by lifetime revenue with cumulative share
------------------------------------------------------------------------
WITH customer_revenue AS (
    SELECT
        customer_key,
        SUM(gross_revenue) AS lifetime_revenue
    FROM fact_orders
    WHERE status = 'delivered'
    GROUP BY customer_key
),
ranked AS (
    SELECT
        customer_key,
        lifetime_revenue,
        RANK() OVER (ORDER BY lifetime_revenue DESC) AS revenue_rank,
        SUM(lifetime_revenue) OVER (ORDER BY lifetime_revenue DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_revenue,
        SUM(lifetime_revenue) OVER ()                              AS total_revenue
    FROM customer_revenue
)
SELECT
    revenue_rank,
    customer_key,
    ROUND(lifetime_revenue, 2)                              AS lifetime_revenue,
    ROUND(cum_revenue / total_revenue * 100, 2)             AS cum_share_pct
FROM ranked
WHERE revenue_rank <= 10
ORDER BY revenue_rank;

------------------------------------------------------------------------
-- 2. Days between consecutive orders per customer (repeat-purchase cadence)
------------------------------------------------------------------------
WITH order_history AS (
    SELECT
        customer_key,
        order_key,
        order_purchase_timestamp,
        LAG(order_purchase_timestamp) OVER (
            PARTITION BY customer_key
            ORDER BY order_purchase_timestamp
        ) AS prev_order_at,
        ROW_NUMBER() OVER (
            PARTITION BY customer_key
            ORDER BY order_purchase_timestamp
        ) AS order_seq
    FROM fact_orders
    WHERE status = 'delivered'
)
SELECT
    order_seq,
    AVG(EXTRACT(EPOCH FROM (order_purchase_timestamp - prev_order_at)) / 86400)
        AS avg_days_since_prev,
    COUNT(*) AS customers_at_seq
FROM order_history
WHERE prev_order_at IS NOT NULL
GROUP BY order_seq
ORDER BY order_seq
LIMIT 10;

------------------------------------------------------------------------
-- 3. Revenue percentile (NTILE deciles) by product category
------------------------------------------------------------------------
WITH category_revenue AS (
    SELECT
        p.category,
        SUM(o.gross_revenue) AS category_revenue
    FROM fact_orders o
    JOIN dim_product p USING (product_key)
    WHERE o.status = 'delivered'
    GROUP BY p.category
)
SELECT
    category,
    ROUND(category_revenue, 2)                          AS revenue,
    NTILE(10) OVER (ORDER BY category_revenue)          AS revenue_decile
FROM category_revenue
ORDER BY category_revenue DESC;

------------------------------------------------------------------------
-- 4. Month-over-month revenue growth, with 3-month moving average
------------------------------------------------------------------------
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', order_purchase_timestamp)::DATE AS order_month,
        SUM(gross_revenue)                                  AS revenue
    FROM fact_orders
    WHERE status = 'delivered'
    GROUP BY 1
)
SELECT
    order_month,
    ROUND(revenue, 2)                                                  AS revenue,
    ROUND(LAG(revenue) OVER (ORDER BY order_month), 2)                 AS prev_month_revenue,
    ROUND((revenue - LAG(revenue) OVER (ORDER BY order_month))
        / NULLIF(LAG(revenue) OVER (ORDER BY order_month), 0) * 100, 2) AS mom_growth_pct,
    ROUND(AVG(revenue) OVER (
        ORDER BY order_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS ma_3mo
FROM monthly_revenue
ORDER BY order_month;

------------------------------------------------------------------------
-- 5. Rank sellers by review-to-volume ratio within each state
------------------------------------------------------------------------
WITH seller_stats AS (
    SELECT
        s.seller_key,
        s.seller_state,
        COUNT(*)                          AS order_count,
        AVG(o.review_score::FLOAT)        AS avg_review,
        SUM(o.gross_revenue)              AS revenue
    FROM fact_orders o
    JOIN dim_seller s USING (seller_key)
    WHERE o.status = 'delivered' AND o.review_score IS NOT NULL
    GROUP BY s.seller_key, s.seller_state
    HAVING COUNT(*) >= 20  -- minimum sample for a fair comparison
)
SELECT
    seller_state,
    seller_key,
    order_count,
    ROUND(avg_review, 2) AS avg_review,
    ROUND(revenue, 2)    AS revenue,
    RANK() OVER (PARTITION BY seller_state ORDER BY avg_review ASC) AS worst_review_rank_in_state,
    PERCENT_RANK() OVER (PARTITION BY seller_state ORDER BY avg_review) AS percent_rank_in_state
FROM seller_stats
QUALIFY worst_review_rank_in_state <= 3   -- DuckDB QUALIFY: top-3 worst per state
ORDER BY seller_state, worst_review_rank_in_state;
