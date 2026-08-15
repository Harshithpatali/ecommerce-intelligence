-- ============================================================
-- AI-Powered E-Commerce Customer & Product Intelligence Platform
-- Supabase PostgreSQL Schema
-- ============================================================
--
-- Purpose:
--   Create the raw relational tables required to load the original
--   Olist Brazilian E-Commerce Public Dataset.
--
-- Important:
--   These tables intentionally preserve the source dataset structure.
--   Analytical joins and feature engineering will happen later.
--   Do not modify the raw CSV files to fit this schema.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Customers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_customers (
    customer_id TEXT PRIMARY KEY,
    customer_unique_id TEXT NOT NULL,
    customer_zip_code_prefix INTEGER,
    customer_city TEXT,
    customer_state TEXT
);

-- ------------------------------------------------------------
-- 2. Geolocation
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_geolocation (
    geolocation_zip_code_prefix INTEGER,
    geolocation_lat DOUBLE PRECISION,
    geolocation_lng DOUBLE PRECISION,
    geolocation_city TEXT,
    geolocation_state TEXT
);

-- ------------------------------------------------------------
-- 3. Orders
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    order_status TEXT,
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

-- ------------------------------------------------------------
-- 4. Order Items
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_order_items (
    order_id TEXT NOT NULL,
    order_item_id INTEGER NOT NULL,
    product_id TEXT,
    seller_id TEXT,
    shipping_limit_date TIMESTAMP,
    price NUMERIC(12, 2),
    freight_value NUMERIC(12, 2),
    PRIMARY KEY (order_id, order_item_id)
);

-- ------------------------------------------------------------
-- 5. Order Payments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_order_payments (
    order_id TEXT NOT NULL,
    payment_sequential INTEGER NOT NULL,
    payment_type TEXT,
    payment_installments INTEGER,
    payment_value NUMERIC(12, 2),
    PRIMARY KEY (order_id, payment_sequential)
);

-- ------------------------------------------------------------
-- 6. Order Reviews
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_order_reviews (
    review_id TEXT,
    order_id TEXT NOT NULL,
    review_score INTEGER,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

-- ------------------------------------------------------------
-- 7. Products
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_products (
    product_id TEXT PRIMARY KEY,
    product_category_name TEXT,
    product_name_lenght INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty INTEGER,
    product_weight_g NUMERIC,
    product_length_cm NUMERIC,
    product_height_cm NUMERIC,
    product_width_cm NUMERIC
);

-- ------------------------------------------------------------
-- 8. Sellers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS olist_sellers (
    seller_id TEXT PRIMARY KEY,
    seller_zip_code_prefix INTEGER,
    seller_city TEXT,
    seller_state TEXT
);

-- ------------------------------------------------------------
-- 9. Category Translation
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_category_name_translation (
    product_category_name TEXT PRIMARY KEY,
    product_category_name_english TEXT
);

-- ============================================================
-- Indexes for common analytical joins and filters
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_customers_unique_id
    ON olist_customers (customer_unique_id);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id
    ON olist_orders (customer_id);

CREATE INDEX IF NOT EXISTS idx_orders_purchase_timestamp
    ON olist_orders (order_purchase_timestamp);

CREATE INDEX IF NOT EXISTS idx_order_items_product_id
    ON olist_order_items (product_id);

CREATE INDEX IF NOT EXISTS idx_order_items_seller_id
    ON olist_order_items (seller_id);

CREATE INDEX IF NOT EXISTS idx_order_payments_order_id
    ON olist_order_payments (order_id);

CREATE INDEX IF NOT EXISTS idx_order_reviews_order_id
    ON olist_order_reviews (order_id);

CREATE INDEX IF NOT EXISTS idx_products_category
    ON olist_products (product_category_name);

CREATE INDEX IF NOT EXISTS idx_geolocation_zip
    ON olist_geolocation (geolocation_zip_code_prefix);

-- ============================================================
-- End of schema
-- ============================================================
