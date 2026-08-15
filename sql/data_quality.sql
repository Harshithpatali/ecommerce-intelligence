-- ============================================================
-- AI-Powered E-Commerce Customer & Product Intelligence Platform
-- Data Quality Validation Queries
-- ============================================================
-- Read-only validation queries for the raw Olist tables.
-- ============================================================

-- 1. Row counts
SELECT 'olist_customers' AS table_name, COUNT(*) AS row_count FROM olist_customers
UNION ALL SELECT 'olist_geolocation', COUNT(*) FROM olist_geolocation
UNION ALL SELECT 'olist_order_items', COUNT(*) FROM olist_order_items
UNION ALL SELECT 'olist_order_payments', COUNT(*) FROM olist_order_payments
UNION ALL SELECT 'olist_order_reviews', COUNT(*) FROM olist_order_reviews
UNION ALL SELECT 'olist_orders', COUNT(*) FROM olist_orders
UNION ALL SELECT 'olist_products', COUNT(*) FROM olist_products
UNION ALL SELECT 'olist_sellers', COUNT(*) FROM olist_sellers
UNION ALL SELECT 'product_category_name_translation', COUNT(*) FROM product_category_name_translation
ORDER BY table_name;

-- 2. NULL checks for important identifiers
SELECT 'olist_customers.customer_id' AS column_name, COUNT(*) FILTER (WHERE customer_id IS NULL) AS null_count FROM olist_customers
UNION ALL SELECT 'olist_orders.order_id', COUNT(*) FILTER (WHERE order_id IS NULL) FROM olist_orders
UNION ALL SELECT 'olist_orders.customer_id', COUNT(*) FILTER (WHERE customer_id IS NULL) FROM olist_orders
UNION ALL SELECT 'olist_order_items.order_id', COUNT(*) FILTER (WHERE order_id IS NULL) FROM olist_order_items
UNION ALL SELECT 'olist_order_items.product_id', COUNT(*) FILTER (WHERE product_id IS NULL) FROM olist_order_items
UNION ALL SELECT 'olist_order_items.seller_id', COUNT(*) FILTER (WHERE seller_id IS NULL) FROM olist_order_items
UNION ALL SELECT 'olist_products.product_id', COUNT(*) FILTER (WHERE product_id IS NULL) FROM olist_products
UNION ALL SELECT 'olist_sellers.seller_id', COUNT(*) FILTER (WHERE seller_id IS NULL) FROM olist_sellers
ORDER BY column_name;

-- 3. Duplicate key checks
SELECT customer_id, COUNT(*) AS duplicate_count FROM olist_customers GROUP BY customer_id HAVING COUNT(*) > 1 ORDER BY duplicate_count DESC;
SELECT order_id, COUNT(*) AS duplicate_count FROM olist_orders GROUP BY order_id HAVING COUNT(*) > 1 ORDER BY duplicate_count DESC;
SELECT product_id, COUNT(*) AS duplicate_count FROM olist_products GROUP BY product_id HAVING COUNT(*) > 1 ORDER BY duplicate_count DESC;
SELECT seller_id, COUNT(*) AS duplicate_count FROM olist_sellers GROUP BY seller_id HAVING COUNT(*) > 1 ORDER BY duplicate_count DESC;
SELECT order_id, order_item_id, COUNT(*) AS duplicate_count FROM olist_order_items GROUP BY order_id, order_item_id HAVING COUNT(*) > 1 ORDER BY duplicate_count DESC;
SELECT order_id, payment_sequential, COUNT(*) AS duplicate_count FROM olist_order_payments GROUP BY order_id, payment_sequential HAVING COUNT(*) > 1 ORDER BY duplicate_count DESC;
SELECT review_id, order_id, COUNT(*) AS duplicate_count FROM olist_order_reviews GROUP BY review_id, order_id HAVING COUNT(*) > 1 ORDER BY duplicate_count DESC;

-- 4. Foreign-key integrity checks
SELECT COUNT(*) AS orders_without_customer FROM olist_orders o LEFT JOIN olist_customers c ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL;
SELECT COUNT(*) AS items_without_order FROM olist_order_items oi LEFT JOIN olist_orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL;
SELECT COUNT(*) AS items_without_product FROM olist_order_items oi LEFT JOIN olist_products p ON oi.product_id = p.product_id WHERE p.product_id IS NULL;
SELECT COUNT(*) AS items_without_seller FROM olist_order_items oi LEFT JOIN olist_sellers s ON oi.seller_id = s.seller_id WHERE s.seller_id IS NULL;
SELECT COUNT(*) AS payments_without_order FROM olist_order_payments op LEFT JOIN olist_orders o ON op.order_id = o.order_id WHERE o.order_id IS NULL;
SELECT COUNT(*) AS reviews_without_order FROM olist_order_reviews r LEFT JOIN olist_orders o ON r.order_id = o.order_id WHERE o.order_id IS NULL;

-- 5. Order status distribution
SELECT order_status, COUNT(*) AS order_count, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM olist_orders GROUP BY order_status ORDER BY order_count DESC;

-- 6. Review score validation
SELECT MIN(review_score) AS minimum_score, MAX(review_score) AS maximum_score,
       COUNT(*) FILTER (WHERE review_score IS NULL) AS null_scores,
       COUNT(*) FILTER (WHERE review_score NOT BETWEEN 1 AND 5) AS invalid_scores
FROM olist_order_reviews;

-- 7. Payment value validation
SELECT COUNT(*) AS payment_rows,
       COUNT(*) FILTER (WHERE payment_value IS NULL) AS null_payment_values,
       COUNT(*) FILTER (WHERE payment_value < 0) AS negative_payment_values,
       MIN(payment_value) AS minimum_payment_value, MAX(payment_value) AS maximum_payment_value,
       AVG(payment_value) AS average_payment_value
FROM olist_order_payments;

-- 8. Order item price and freight validation
SELECT COUNT(*) AS item_rows,
       COUNT(*) FILTER (WHERE price IS NULL) AS null_prices,
       COUNT(*) FILTER (WHERE price < 0) AS negative_prices,
       COUNT(*) FILTER (WHERE freight_value IS NULL) AS null_freight_values,
       COUNT(*) FILTER (WHERE freight_value < 0) AS negative_freight_values,
       MIN(price) AS minimum_price, MAX(price) AS maximum_price,
       MIN(freight_value) AS minimum_freight, MAX(freight_value) AS maximum_freight
FROM olist_order_items;

-- 9. Product dimension validation
SELECT COUNT(*) AS product_rows,
       COUNT(*) FILTER (WHERE product_category_name IS NULL) AS missing_category,
       COUNT(*) FILTER (WHERE product_weight_g < 0) AS negative_weight,
       COUNT(*) FILTER (WHERE product_length_cm < 0) AS negative_length,
       COUNT(*) FILTER (WHERE product_height_cm < 0) AS negative_height,
       COUNT(*) FILTER (WHERE product_width_cm < 0) AS negative_width
FROM olist_products;

-- 10. Date range validation
SELECT MIN(order_purchase_timestamp) AS first_order_purchase,
       MAX(order_purchase_timestamp) AS last_order_purchase,
       COUNT(*) FILTER (WHERE order_purchase_timestamp IS NULL) AS missing_purchase_timestamp
FROM olist_orders;

-- 11. Delivery-date consistency
SELECT COUNT(*) AS delivered_orders,
       COUNT(*) FILTER (WHERE order_delivered_customer_date < order_purchase_timestamp) AS delivered_before_purchase,
       COUNT(*) FILTER (WHERE order_delivered_customer_date < order_approved_at) AS delivered_before_approval,
       COUNT(*) FILTER (WHERE order_delivered_customer_date < order_delivered_carrier_date) AS delivered_before_carrier
FROM olist_orders WHERE order_delivered_customer_date IS NOT NULL;

-- 12. Estimated delivery consistency
SELECT COUNT(*) AS orders_with_estimate,
       COUNT(*) FILTER (WHERE order_estimated_delivery_date < order_purchase_timestamp) AS estimate_before_purchase
FROM olist_orders WHERE order_estimated_delivery_date IS NOT NULL;

-- 13. Geolocation ZIP-prefix multiplicity (expected in the source data)
SELECT geolocation_zip_code_prefix, COUNT(*) AS records_per_zip_prefix
FROM olist_geolocation GROUP BY geolocation_zip_code_prefix
HAVING COUNT(*) > 1 ORDER BY records_per_zip_prefix DESC LIMIT 20;

-- 14. Category translation coverage
SELECT COUNT(*) AS translation_rows,
       COUNT(*) FILTER (WHERE product_category_name IS NULL) AS null_category_names,
       COUNT(*) FILTER (WHERE product_category_name_english IS NULL) AS missing_english_translation
FROM product_category_name_translation;

-- 15. Products with untranslated categories
SELECT p.product_category_name, COUNT(*) AS product_count
FROM olist_products p
LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL
GROUP BY p.product_category_name ORDER BY product_count DESC;

-- 16. Compact quality dashboard
WITH quality_checks AS (
    SELECT 'orders_without_customer' AS check_name, COUNT(*)::BIGINT AS issue_count
    FROM olist_orders o LEFT JOIN olist_customers c ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL
    UNION ALL SELECT 'items_without_order', COUNT(*)::BIGINT
    FROM olist_order_items oi LEFT JOIN olist_orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL
    UNION ALL SELECT 'items_without_product', COUNT(*)::BIGINT
    FROM olist_order_items oi LEFT JOIN olist_products p ON oi.product_id = p.product_id WHERE p.product_id IS NULL
    UNION ALL SELECT 'items_without_seller', COUNT(*)::BIGINT
    FROM olist_order_items oi LEFT JOIN olist_sellers s ON oi.seller_id = s.seller_id WHERE s.seller_id IS NULL
    UNION ALL SELECT 'payments_without_order', COUNT(*)::BIGINT
    FROM olist_order_payments op LEFT JOIN olist_orders o ON op.order_id = o.order_id WHERE o.order_id IS NULL
    UNION ALL SELECT 'reviews_without_order', COUNT(*)::BIGINT
    FROM olist_order_reviews r LEFT JOIN olist_orders o ON r.order_id = o.order_id WHERE o.order_id IS NULL
    UNION ALL SELECT 'invalid_review_scores', COUNT(*)::BIGINT
    FROM olist_order_reviews WHERE review_score IS NOT NULL AND review_score NOT BETWEEN 1 AND 5
    UNION ALL SELECT 'negative_payment_values', COUNT(*)::BIGINT
    FROM olist_order_payments WHERE payment_value < 0
    UNION ALL SELECT 'negative_product_prices', COUNT(*)::BIGINT
    FROM olist_order_items WHERE price < 0
)
SELECT check_name, issue_count,
       CASE WHEN issue_count = 0 THEN 'PASS' ELSE 'REVIEW' END AS status
FROM quality_checks
ORDER BY CASE WHEN issue_count = 0 THEN 1 ELSE 0 END, check_name;
