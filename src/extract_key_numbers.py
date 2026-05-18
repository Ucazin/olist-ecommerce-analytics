"""
extract_key_numbers.py — Pull the exact numbers needed to populate
README headline findings and MEMO.md from the built warehouse.

Run after src/run_pipeline.py. Output is plain text to stdout.
"""

import duckdb

con = duckdb.connect("olist.duckdb", read_only=True)

print("\n--- A. Overall (delivered orders) ---")
print(con.execute("""
    SELECT
        COUNT(*) AS orders,
        COUNT(DISTINCT customer_key) AS customers,
        ROUND(SUM(gross_revenue), 0) AS revenue_brl,
        ROUND(AVG(review_score), 2) AS avg_review,
        ROUND(AVG(CASE WHEN delivery_lag_days > 0 THEN 100.0 ELSE 0.0 END), 2) AS pct_late,
        ROUND(AVG(fulfillment_days), 1) AS avg_fulfillment_days
    FROM analytics.fact_orders WHERE order_status = 'delivered'
""").df().to_string(index=False))

print("\n--- B. Review score by lateness bucket ---")
print(con.execute("""
    SELECT
        CASE WHEN delivery_lag_days <= 0 THEN '1. on time'
             WHEN delivery_lag_days BETWEEN 1 AND 7 THEN '2. 1-7d late'
             ELSE '3. 8+d late' END AS bucket,
        COUNT(*) AS orders,
        ROUND(AVG(review_score), 2) AS avg_review,
        ROUND(AVG(CASE WHEN review_score <= 2 THEN 100.0 ELSE 0 END), 2) AS pct_one_two_star
    FROM analytics.fact_orders
    WHERE order_status = 'delivered' AND review_score IS NOT NULL
    GROUP BY bucket ORDER BY bucket
""").df().to_string(index=False))

print("\n--- C. Top 5 revenue categories ---")
print(con.execute("""
    SELECT p.category_en,
           ROUND(SUM(f.gross_revenue), 0) AS revenue_brl,
           ROUND(SUM(f.gross_revenue) * 100.0 / SUM(SUM(f.gross_revenue)) OVER (), 2) AS pct_share
    FROM analytics.fact_orders f
    JOIN analytics.dim_product p ON p.product_key = f.product_key
    WHERE f.order_status = 'delivered'
    GROUP BY p.category_en ORDER BY revenue_brl DESC LIMIT 5
""").df().to_string(index=False))

print("\n--- D. Revenue at risk (late orders × low review rate × revenue) ---")
print(con.execute("""
    WITH r AS (
        SELECT
            ROUND(SUM(gross_revenue), 0) AS revenue_late,
            ROUND(AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0 END), 4) AS pct_low_when_late
        FROM analytics.fact_orders
        WHERE order_status = 'delivered' AND delivery_lag_days > 0
    )
    SELECT *, ROUND(revenue_late * pct_low_when_late, 0) AS revenue_at_risk_brl FROM r
""").df().to_string(index=False))

print("\n--- E. Top 5 states by CLV ---")
print(con.execute("""
    SELECT c.customer_state,
           COUNT(DISTINCT f.customer_key) AS customers,
           ROUND(SUM(f.gross_revenue) / COUNT(DISTINCT f.customer_key), 2) AS avg_clv
    FROM analytics.fact_orders f
    JOIN analytics.dim_customer c ON c.customer_key = f.customer_key
    WHERE f.order_status = 'delivered'
    GROUP BY c.customer_state HAVING COUNT(DISTINCT f.customer_key) >= 100
    ORDER BY avg_clv DESC LIMIT 5
""").df().to_string(index=False))

print("\n--- F. Bottleneck breakdown ---")
print(con.execute("""
    SELECT
        CASE WHEN delivery_lag_days <= 0 THEN 'on_time' ELSE 'late' END AS lateness,
        COUNT(*) AS orders,
        ROUND(AVG(DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_carrier_date)), 1) AS seller_dispatch_days,
        ROUND(AVG(DATE_DIFF('day', o.order_delivered_carrier_date, o.order_delivered_customer_date)), 1) AS carrier_transit_days
    FROM analytics.fact_orders f
    JOIN raw_olist.orders o ON o.order_id = f.order_key
    WHERE f.order_status = 'delivered'
    GROUP BY lateness
""").df().to_string(index=False))

print("\n--- G. Repeat purchase rate by lateness ---")
print(con.execute("""
    WITH labeled AS (
        SELECT
            f.*,
            CASE WHEN delivery_lag_days <= 0 THEN 'on_time'
                 WHEN delivery_lag_days BETWEEN 1 AND 7 THEN 'late_1_7d'
                 ELSE 'late_8d_plus' END AS lateness_bucket
        FROM analytics.fact_orders f
        WHERE order_status = 'delivered'
    ),
    rp AS (
        SELECT l.order_key, l.customer_key, l.lateness_bucket,
               MAX(CASE WHEN f2.order_purchase_timestamp > l.order_purchase_timestamp
                         AND f2.order_purchase_timestamp <= l.order_purchase_timestamp + INTERVAL 90 DAY
                    THEN 1 ELSE 0 END) AS repeated_90d
        FROM labeled l
        LEFT JOIN analytics.fact_orders f2 ON f2.customer_key = l.customer_key AND f2.order_key <> l.order_key
        GROUP BY l.order_key, l.customer_key, l.lateness_bucket
    )
    SELECT lateness_bucket,
           COUNT(*) AS orders,
           ROUND(AVG(repeated_90d) * 100, 2) AS repeat_rate_90d_pct
    FROM rp GROUP BY lateness_bucket
    ORDER BY ARRAY_POSITION(['on_time','late_1_7d','late_8d_plus'], lateness_bucket)
""").df().to_string(index=False))
