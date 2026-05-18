-- =============================================================================
-- 02_dim_model.sql
-- Build a Kimball star schema on top of raw_olist.
-- Grain of fact_orders = one row per order (items aggregated to order-level).
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

-- ---- dim_date --------------------------------------------------------------
DROP TABLE IF EXISTS analytics.dim_date;
CREATE TABLE analytics.dim_date AS
WITH date_range AS (
    SELECT
        MIN(order_purchase_timestamp::DATE) AS min_date,
        MAX(order_purchase_timestamp::DATE) AS max_date
    FROM raw_olist.orders
),
date_spine AS (
    SELECT
        date_trunc('day', dt)::DATE AS calendar_date
    FROM date_range,
         generate_series(min_date, max_date, INTERVAL '1 day') AS g(dt)
)
SELECT
    calendar_date,
    CAST(strftime(calendar_date, '%Y%m%d') AS INTEGER) AS date_key,
    EXTRACT(YEAR  FROM calendar_date) AS year,
    EXTRACT(MONTH FROM calendar_date) AS month,
    EXTRACT(DAY   FROM calendar_date) AS day,
    date_trunc('month',   calendar_date)::DATE AS month_start,
    date_trunc('quarter', calendar_date)::DATE AS quarter_start,
    EXTRACT(DOW    FROM calendar_date) AS day_of_week,
    strftime(calendar_date, '%A')      AS day_name,
    strftime(calendar_date, '%B')      AS month_name,
    CASE WHEN EXTRACT(DOW FROM calendar_date) IN (0,6) THEN TRUE ELSE FALSE END AS is_weekend
FROM date_spine;

-- ---- dim_customer (one row per unique physical customer) -------------------
DROP TABLE IF EXISTS analytics.dim_customer;
CREATE TABLE analytics.dim_customer AS
SELECT
    customer_unique_id AS customer_key,
    ANY_VALUE(customer_state) AS customer_state,
    ANY_VALUE(customer_city)  AS customer_city,
    COUNT(DISTINCT customer_id) AS distinct_order_aliases
FROM raw_olist.customers
GROUP BY customer_unique_id;

-- ---- dim_product (with English category name) ------------------------------
DROP TABLE IF EXISTS analytics.dim_product;
CREATE TABLE analytics.dim_product AS
SELECT
    p.product_id AS product_key,
    COALESCE(t.product_category_name_en, p.product_category_name, 'unknown') AS category_en,
    p.product_category_name AS category_pt,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.product_photos_qty
FROM raw_olist.products p
LEFT JOIN raw_olist.category_translation t USING (product_category_name);

-- ---- dim_seller ------------------------------------------------------------
DROP TABLE IF EXISTS analytics.dim_seller;
CREATE TABLE analytics.dim_seller AS
SELECT
    seller_id AS seller_key,
    seller_state,
    seller_city
FROM raw_olist.sellers;

-- ---- Helper: one payment row per order (sum across installments) -----------
DROP TABLE IF EXISTS analytics._stg_order_payment;
CREATE TABLE analytics._stg_order_payment AS
SELECT
    order_id,
    -- payment_type for the highest-value row; tie-broken by alphabetical order
    ARG_MAX(payment_type, payment_value)  AS primary_payment_type,
    SUM(payment_value)        AS total_payment_value,
    MAX(payment_installments) AS max_installments
FROM raw_olist.order_payments
GROUP BY order_id;

-- ---- Helper: one review row per order (latest review wins) -----------------
DROP TABLE IF EXISTS analytics._stg_order_review;
CREATE TABLE analytics._stg_order_review AS
SELECT
    order_id,
    ARG_MAX(review_score, review_creation_date) AS review_score,
    MAX(review_creation_date) AS review_creation_date
FROM raw_olist.order_reviews
GROUP BY order_id;

-- ---- Helper: order-level items aggregation ---------------------------------
DROP TABLE IF EXISTS analytics._stg_order_items;
CREATE TABLE analytics._stg_order_items AS
SELECT
    order_id,
    COUNT(*)               AS item_count,
    SUM(price)             AS gross_revenue,
    SUM(freight_value)     AS total_freight,
    -- pick the dominant product/seller for the order
    ARG_MAX(product_id, price)  AS primary_product_id,
    ARG_MAX(seller_id,  price)  AS primary_seller_id
FROM raw_olist.order_items
GROUP BY order_id;

-- ---- fact_orders (grain: one row per order) --------------------------------
DROP TABLE IF EXISTS analytics.fact_orders;
CREATE TABLE analytics.fact_orders AS
SELECT
    o.order_id AS order_key,
    c.customer_unique_id AS customer_key,
    i.primary_product_id AS product_key,
    i.primary_seller_id  AS seller_key,
    CAST(strftime(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS purchase_date_key,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.order_status,
    i.item_count,
    i.gross_revenue,
    i.total_freight,
    p.total_payment_value,
    p.primary_payment_type,
    p.max_installments,
    r.review_score,
    -- delivery lag: how many days late vs the estimate (negative = early)
    DATE_DIFF('day', o.order_estimated_delivery_date, o.order_delivered_customer_date) AS delivery_lag_days,
    -- end-to-end fulfillment time
    DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS fulfillment_days
FROM raw_olist.orders o
JOIN raw_olist.customers cust ON cust.customer_id = o.customer_id
JOIN (SELECT DISTINCT customer_id, customer_unique_id FROM raw_olist.customers) c
     ON c.customer_id = o.customer_id
LEFT JOIN analytics._stg_order_items   i ON i.order_id = o.order_id
LEFT JOIN analytics._stg_order_payment p ON p.order_id = o.order_id
LEFT JOIN analytics._stg_order_review  r ON r.order_id = o.order_id;

-- ---- Cleanup intermediates -------------------------------------------------
DROP TABLE analytics._stg_order_items;
DROP TABLE analytics._stg_order_payment;
DROP TABLE analytics._stg_order_review;

-- ---- Sanity ----------------------------------------------------------------
SELECT
    COUNT(*)                                         AS fact_rows,
    COUNT(DISTINCT order_key)                        AS unique_orders,
    SUM(CASE WHEN customer_key IS NULL THEN 1 END)   AS orphan_customer,
    SUM(CASE WHEN product_key IS NULL THEN 1 END)    AS orders_without_items,
    SUM(CASE WHEN review_score IS NULL THEN 1 END)   AS orders_without_review
FROM analytics.fact_orders;
