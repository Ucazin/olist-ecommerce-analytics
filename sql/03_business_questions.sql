-- =============================================================================
-- 03_business_questions.sql
-- Ten analytical queries, one per business question in the README.
-- All run against analytics.fact_orders + dim_*.
-- =============================================================================

------------------------------------------------------------------------
-- Q1. Revenue concentration by category
--     Which category drives revenue, and what share belongs to the top 10%?
------------------------------------------------------------------------
WITH cat_rev AS (
    SELECT
        p.category_en,
        SUM(f.gross_revenue) AS revenue,
        COUNT(*)             AS orders
    FROM analytics.fact_orders f
    JOIN analytics.dim_product p ON p.product_key = f.product_key
    WHERE f.order_status NOT IN ('canceled','unavailable')
    GROUP BY p.category_en
),
ranked AS (
    SELECT
        category_en,
        revenue,
        orders,
        revenue * 1.0 / SUM(revenue) OVER () AS share,
        SUM(revenue) OVER (ORDER BY revenue DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            / SUM(revenue) OVER () AS cumulative_share
    FROM cat_rev
)
SELECT * FROM ranked ORDER BY revenue DESC LIMIT 25;

------------------------------------------------------------------------
-- Q2. State-level customer lifetime value (CLV proxy = total revenue per
--     unique customer, averaged by state).
------------------------------------------------------------------------
SELECT
    c.customer_state,
    COUNT(DISTINCT f.customer_key)             AS customers,
    SUM(f.gross_revenue)                       AS total_revenue,
    SUM(f.gross_revenue) / COUNT(DISTINCT f.customer_key) AS avg_clv,
    AVG(f.review_score)                        AS avg_review
FROM analytics.fact_orders f
JOIN analytics.dim_customer c ON c.customer_key = f.customer_key
WHERE f.order_status = 'delivered'
GROUP BY c.customer_state
HAVING COUNT(DISTINCT f.customer_key) >= 100  -- exclude tiny states for stability
ORDER BY avg_clv DESC;

------------------------------------------------------------------------
-- Q3. Delivery lateness → review score impact, and repeat-purchase probability
------------------------------------------------------------------------
WITH labeled AS (
    SELECT
        f.*,
        CASE
            WHEN delivery_lag_days IS NULL                 THEN 'undelivered'
            WHEN delivery_lag_days <= 0                    THEN 'on_time'
            WHEN delivery_lag_days BETWEEN 1 AND 7         THEN 'late_1_7d'
            ELSE                                                'late_8d_plus'
        END AS lateness_bucket
    FROM analytics.fact_orders f
    WHERE order_status = 'delivered'
),
repeat_purchase AS (
    -- Did this customer place a second order within 90 days of THIS one?
    SELECT
        l.order_key,
        l.customer_key,
        l.lateness_bucket,
        l.review_score,
        MAX(CASE WHEN f2.order_purchase_timestamp > l.order_purchase_timestamp
                  AND f2.order_purchase_timestamp <= l.order_purchase_timestamp + INTERVAL 90 DAY
            THEN 1 ELSE 0 END) AS repeated_within_90d
    FROM labeled l
    LEFT JOIN analytics.fact_orders f2
        ON f2.customer_key = l.customer_key
       AND f2.order_key   <> l.order_key
    GROUP BY l.order_key, l.customer_key, l.lateness_bucket, l.review_score
)
SELECT
    lateness_bucket,
    COUNT(*)                  AS orders,
    AVG(review_score)         AS avg_review,
    AVG(repeated_within_90d)  AS repeat_rate_90d
FROM repeat_purchase
GROUP BY lateness_bucket
ORDER BY ARRAY_POSITION(['on_time','late_1_7d','late_8d_plus','undelivered'], lateness_bucket);

------------------------------------------------------------------------
-- Q4. Bottleneck decomposition for late orders (seller dispatch / carrier
--     transit / last mile)
------------------------------------------------------------------------
SELECT
    CASE
        WHEN delivery_lag_days <= 0 THEN 'on_time'
        ELSE 'late'
    END AS lateness,
    AVG(DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_carrier_date))   AS days_seller_to_carrier,
    AVG(DATE_DIFF('day', o.order_delivered_carrier_date, o.order_delivered_customer_date)) AS days_carrier_to_customer,
    AVG(DATE_DIFF('day', o.order_estimated_delivery_date, o.order_delivered_customer_date)) AS days_vs_estimate,
    COUNT(*) AS orders
FROM analytics.fact_orders f
JOIN raw_olist.orders o ON o.order_id = f.order_key
WHERE f.order_status = 'delivered'
GROUP BY lateness;

------------------------------------------------------------------------
-- Q5. Monthly cohort retention curve
------------------------------------------------------------------------
WITH first_purchase AS (
    SELECT
        customer_key,
        date_trunc('month', MIN(order_purchase_timestamp))::DATE AS cohort_month
    FROM analytics.fact_orders
    GROUP BY customer_key
),
orders_with_cohort AS (
    SELECT
        f.customer_key,
        fp.cohort_month,
        date_trunc('month', f.order_purchase_timestamp)::DATE AS activity_month,
        DATE_DIFF('month', fp.cohort_month, date_trunc('month', f.order_purchase_timestamp)) AS months_since_first
    FROM analytics.fact_orders f
    JOIN first_purchase fp ON fp.customer_key = f.customer_key
)
SELECT
    cohort_month,
    months_since_first,
    COUNT(DISTINCT customer_key) AS active_customers
FROM orders_with_cohort
WHERE months_since_first BETWEEN 0 AND 12
GROUP BY cohort_month, months_since_first
ORDER BY cohort_month, months_since_first;

------------------------------------------------------------------------
-- Q6. Payment behavior by category (installment count, payment type mix)
------------------------------------------------------------------------
SELECT
    p.category_en,
    COUNT(*)                                                AS orders,
    AVG(f.max_installments)                                 AS avg_installments,
    SUM(CASE WHEN primary_payment_type='credit_card' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS pct_credit_card,
    SUM(CASE WHEN primary_payment_type='boleto'      THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS pct_boleto
FROM analytics.fact_orders f
JOIN analytics.dim_product p ON p.product_key = f.product_key
WHERE f.order_status = 'delivered'
GROUP BY p.category_en
HAVING COUNT(*) >= 200
ORDER BY avg_installments DESC
LIMIT 20;

------------------------------------------------------------------------
-- Q7. Seller scorecard — worst review-to-volume ratio
------------------------------------------------------------------------
SELECT
    s.seller_key,
    s.seller_state,
    COUNT(*)                            AS delivered_orders,
    AVG(f.review_score)                 AS avg_review,
    SUM(CASE WHEN f.review_score <= 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS pct_low_review,
    SUM(f.gross_revenue)                AS total_revenue,
    SUM(f.gross_revenue) *
        (SUM(CASE WHEN f.review_score <= 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) AS revenue_at_risk
FROM analytics.fact_orders f
JOIN analytics.dim_seller s ON s.seller_key = f.seller_key
WHERE f.order_status = 'delivered'
GROUP BY s.seller_key, s.seller_state
HAVING COUNT(*) >= 50
ORDER BY pct_low_review DESC
LIMIT 25;

------------------------------------------------------------------------
-- Q8. Freight as a percentage of order value, by region + category
------------------------------------------------------------------------
SELECT
    c.customer_state,
    p.category_en,
    COUNT(*)                                              AS orders,
    SUM(f.gross_revenue)                                  AS revenue,
    SUM(f.total_freight)                                  AS freight,
    SUM(f.total_freight) * 1.0 / NULLIF(SUM(f.gross_revenue), 0) AS freight_share
FROM analytics.fact_orders f
JOIN analytics.dim_customer c ON c.customer_key = f.customer_key
JOIN analytics.dim_product  p ON p.product_key  = f.product_key
WHERE f.order_status = 'delivered'
GROUP BY c.customer_state, p.category_en
HAVING COUNT(*) >= 30
ORDER BY freight_share DESC
LIMIT 30;

------------------------------------------------------------------------
-- Q9. Seasonality — day of week × month of year
------------------------------------------------------------------------
SELECT
    d.year,
    d.month_name,
    d.day_of_week,
    d.day_name,
    COUNT(*)             AS orders,
    SUM(f.gross_revenue) AS revenue
FROM analytics.fact_orders f
JOIN analytics.dim_date d ON d.date_key = f.purchase_date_key
WHERE f.order_status = 'delivered'
GROUP BY d.year, d.month, d.month_name, d.day_of_week, d.day_name
ORDER BY d.year, d.month, d.day_of_week;

------------------------------------------------------------------------
-- Q10. Seller-state → customer-state flow concentration
------------------------------------------------------------------------
SELECT
    s.seller_state,
    c.customer_state,
    COUNT(*)                AS orders,
    AVG(f.fulfillment_days) AS avg_fulfillment_days,
    SUM(f.gross_revenue)    AS revenue
FROM analytics.fact_orders f
JOIN analytics.dim_seller   s ON s.seller_key   = f.seller_key
JOIN analytics.dim_customer c ON c.customer_key = f.customer_key
WHERE f.order_status = 'delivered'
GROUP BY s.seller_state, c.customer_state
ORDER BY orders DESC
LIMIT 25;
