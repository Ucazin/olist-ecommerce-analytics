-- =============================================================================
-- 01_load_raw.sql
-- Load the 9 raw Olist CSVs into DuckDB as typed staging tables.
-- Idempotent: drops and recreates the raw_olist schema on every run.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS raw_olist;

-- ---- Orders ----------------------------------------------------------------
DROP TABLE IF EXISTS raw_olist.orders;
CREATE TABLE raw_olist.orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    CAST(order_purchase_timestamp     AS TIMESTAMP) AS order_purchase_timestamp,
    CAST(order_approved_at            AS TIMESTAMP) AS order_approved_at,
    CAST(order_delivered_carrier_date AS TIMESTAMP) AS order_delivered_carrier_date,
    CAST(order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
    CAST(order_estimated_delivery_date AS TIMESTAMP) AS order_estimated_delivery_date
FROM read_csv_auto('data/raw/olist_orders_dataset.csv', header=true);

-- ---- Order items (one row per item, multiple per order) --------------------
DROP TABLE IF EXISTS raw_olist.order_items;
CREATE TABLE raw_olist.order_items AS
SELECT
    order_id,
    CAST(order_item_id AS INTEGER) AS order_item_id,
    product_id,
    seller_id,
    CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_date,
    CAST(price         AS DECIMAL(12,2))   AS price,
    CAST(freight_value AS DECIMAL(12,2))   AS freight_value
FROM read_csv_auto('data/raw/olist_order_items_dataset.csv', header=true);

-- ---- Order payments (one order can have multiple payment records) ----------
DROP TABLE IF EXISTS raw_olist.order_payments;
CREATE TABLE raw_olist.order_payments AS
SELECT
    order_id,
    CAST(payment_sequential AS INTEGER) AS payment_sequential,
    payment_type,
    CAST(payment_installments AS INTEGER)  AS payment_installments,
    CAST(payment_value       AS DECIMAL(12,2)) AS payment_value
FROM read_csv_auto('data/raw/olist_order_payments_dataset.csv', header=true);

-- ---- Order reviews ---------------------------------------------------------
DROP TABLE IF EXISTS raw_olist.order_reviews;
CREATE TABLE raw_olist.order_reviews AS
SELECT
    review_id,
    order_id,
    CAST(review_score AS INTEGER) AS review_score,
    review_comment_title,
    review_comment_message,
    CAST(review_creation_date    AS TIMESTAMP) AS review_creation_date,
    CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp
FROM read_csv_auto('data/raw/olist_order_reviews_dataset.csv', header=true);

-- ---- Products --------------------------------------------------------------
DROP TABLE IF EXISTS raw_olist.products;
CREATE TABLE raw_olist.products AS
SELECT
    product_id,
    product_category_name,
    CAST(product_name_lenght      AS INTEGER) AS product_name_length,
    CAST(product_description_lenght AS INTEGER) AS product_description_length,
    CAST(product_photos_qty       AS INTEGER) AS product_photos_qty,
    CAST(product_weight_g         AS INTEGER) AS product_weight_g,
    CAST(product_length_cm        AS INTEGER) AS product_length_cm,
    CAST(product_height_cm        AS INTEGER) AS product_height_cm,
    CAST(product_width_cm         AS INTEGER) AS product_width_cm
FROM read_csv_auto('data/raw/olist_products_dataset.csv', header=true);

-- ---- Customers (note: each order has its own customer_id; customer_unique_id
--                tracks the same physical customer across multiple orders) ---
DROP TABLE IF EXISTS raw_olist.customers;
CREATE TABLE raw_olist.customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM read_csv_auto('data/raw/olist_customers_dataset.csv', header=true);

-- ---- Sellers ---------------------------------------------------------------
DROP TABLE IF EXISTS raw_olist.sellers;
CREATE TABLE raw_olist.sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
FROM read_csv_auto('data/raw/olist_sellers_dataset.csv', header=true);

-- ---- Geolocation (zip prefix → lat/lon, multiple rows per prefix) ----------
DROP TABLE IF EXISTS raw_olist.geolocation;
CREATE TABLE raw_olist.geolocation AS
SELECT
    geolocation_zip_code_prefix,
    CAST(geolocation_lat AS DOUBLE) AS geolocation_lat,
    CAST(geolocation_lng AS DOUBLE) AS geolocation_lng,
    geolocation_city,
    geolocation_state
FROM read_csv_auto('data/raw/olist_geolocation_dataset.csv', header=true);

-- ---- Category translation (Portuguese → English) --------------------------
DROP TABLE IF EXISTS raw_olist.category_translation;
CREATE TABLE raw_olist.category_translation AS
SELECT
    product_category_name,
    product_category_name_english AS product_category_name_en
FROM read_csv_auto('data/raw/product_category_name_translation.csv', header=true);

-- ---- Sanity row counts -----------------------------------------------------
SELECT 'orders'                AS table_name, COUNT(*) AS rows FROM raw_olist.orders
UNION ALL SELECT 'order_items',           COUNT(*) FROM raw_olist.order_items
UNION ALL SELECT 'order_payments',        COUNT(*) FROM raw_olist.order_payments
UNION ALL SELECT 'order_reviews',         COUNT(*) FROM raw_olist.order_reviews
UNION ALL SELECT 'products',              COUNT(*) FROM raw_olist.products
UNION ALL SELECT 'customers',             COUNT(*) FROM raw_olist.customers
UNION ALL SELECT 'sellers',               COUNT(*) FROM raw_olist.sellers
UNION ALL SELECT 'geolocation',           COUNT(*) FROM raw_olist.geolocation
UNION ALL SELECT 'category_translation',  COUNT(*) FROM raw_olist.category_translation;
