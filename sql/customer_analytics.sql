SELECT
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    COUNT(DISTINCT o.order_id) AS order_count,
    MIN(o.order_purchase_timestamp) AS first_order_date,
    MAX(o.order_purchase_timestamp) AS last_order_date
FROM olist_customers c
JOIN olist_orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_unique_id, c.customer_city, c.customer_state
ORDER BY order_count DESC;


-- 2. Repeat customer distribution
WITH customer_orders AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_count
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
)
SELECT
    CASE WHEN order_count = 1 THEN 'One-time customer'
         ELSE 'Repeat customer' END AS customer_type,
    COUNT(*) AS customer_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM customer_orders
GROUP BY customer_type
ORDER BY customer_count DESC;


-- 3. Customer order-frequency statistics
WITH customer_orders AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_count
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
)
SELECT
    ROUND(AVG(order_count), 2) AS average_orders_per_customer,
    MIN(order_count) AS minimum_orders,
    MAX(order_count) AS maximum_orders,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY order_count) AS median_orders
FROM customer_orders;


-- 4. Customer monetary-value summary
-- Revenue uses order_items price + freight_value.
-- Payments are not joined here to avoid double counting orders with
-- multiple payment records.
WITH customer_revenue AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(oi.price + oi.freight_value) AS total_spend
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_unique_id
)
SELECT
    COUNT(*) AS customers,
    ROUND(AVG(total_spend), 2) AS average_customer_spend,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total_spend)::numeric, 2)
        AS median_customer_spend,
    ROUND(MIN(total_spend), 2) AS minimum_customer_spend,
    ROUND(MAX(total_spend), 2) AS maximum_customer_spend
FROM customer_revenue;


-- 5. Top customers by spend
WITH customer_revenue AS (
    SELECT
        c.customer_unique_id,
        c.customer_city,
        c.customer_state,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(oi.price + oi.freight_value) AS total_spend
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_unique_id, c.customer_city, c.customer_state
)
SELECT customer_unique_id, customer_city, customer_state,
       order_count, ROUND(total_spend, 2) AS total_spend
FROM customer_revenue
ORDER BY total_spend DESC
LIMIT 20;


-- 6. Average order value by customer
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        SUM(oi.price + oi.freight_value) AS order_value
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_unique_id, o.order_id
)
SELECT
    customer_unique_id,
    COUNT(*) AS order_count,
    ROUND(AVG(order_value), 2) AS average_order_value,
    ROUND(SUM(order_value), 2) AS total_spend
FROM customer_orders
GROUP BY customer_unique_id
ORDER BY total_spend DESC;


-- 7. Customer category diversity
SELECT
    c.customer_unique_id,
    COUNT(DISTINCT p.product_category_name) AS category_count
FROM olist_customers c
JOIN olist_orders o ON c.customer_id = o.customer_id
JOIN olist_order_items oi ON o.order_id = oi.order_id
JOIN olist_products p ON oi.product_id = p.product_id
GROUP BY c.customer_unique_id
ORDER BY category_count DESC;


-- 8. Customer product diversity
SELECT
    c.customer_unique_id,
    COUNT(DISTINCT oi.product_id) AS unique_products_purchased,
    COUNT(*) AS item_line_count
FROM olist_customers c
JOIN olist_orders o ON c.customer_id = o.customer_id
JOIN olist_order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_unique_id
ORDER BY unique_products_purchased DESC;


-- 9. Customer review behavior
SELECT
    c.customer_unique_id,
    COUNT(r.review_id) AS review_count,
    ROUND(AVG(r.review_score), 2) AS average_review_score,
    COUNT(*) FILTER (WHERE r.review_score <= 2) AS negative_review_count,
    COUNT(*) FILTER (WHERE r.review_score >= 4) AS positive_review_count
FROM olist_customers c
JOIN olist_orders o ON c.customer_id = o.customer_id
LEFT JOIN olist_order_reviews r ON o.order_id = r.order_id
GROUP BY c.customer_unique_id
ORDER BY average_review_score DESC NULLS LAST;


-- 10. Most-used customer payment method
WITH customer_payments AS (
    SELECT
        c.customer_unique_id,
        op.payment_type,
        COUNT(*) AS payment_count,
        SUM(op.payment_value) AS payment_value
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_payments op ON o.order_id = op.order_id
    GROUP BY c.customer_unique_id, op.payment_type
),
ranked_payments AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY customer_unique_id
               ORDER BY payment_count DESC, payment_value DESC
           ) AS payment_rank
    FROM customer_payments
)
SELECT
    customer_unique_id,
    payment_type AS most_used_payment_type,
    payment_count,
    ROUND(payment_value, 2) AS payment_value
FROM ranked_payments
WHERE payment_rank = 1
ORDER BY payment_count DESC;


-- 11. Customer geography
SELECT
    c.customer_state,
    COUNT(DISTINCT c.customer_unique_id) AS customer_count,
    COUNT(DISTINCT o.order_id) AS order_count,
    ROUND(SUM(oi.price + oi.freight_value), 2) AS total_revenue
FROM olist_customers c
JOIN olist_orders o ON c.customer_id = o.customer_id
JOIN olist_order_items oi ON o.order_id = oi.order_id
GROUP BY c.customer_state
ORDER BY total_revenue DESC;


-- 12. Monthly customer activity
SELECT
    DATE_TRUNC('month', o.order_purchase_timestamp) AS purchase_month,
    COUNT(DISTINCT c.customer_unique_id) AS active_customers,
    COUNT(DISTINCT o.order_id) AS orders,
    ROUND(SUM(oi.price + oi.freight_value), 2) AS revenue
FROM olist_customers c
JOIN olist_orders o ON c.customer_id = o.customer_id
JOIN olist_order_items oi ON o.order_id = oi.order_id
GROUP BY purchase_month
ORDER BY purchase_month;


-- 13. Customer order intervals using LAG
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        LAG(o.order_purchase_timestamp) OVER (
            PARTITION BY c.customer_unique_id
            ORDER BY o.order_purchase_timestamp
        ) AS previous_order_timestamp
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
)
SELECT
    customer_unique_id,
    order_id,
    order_purchase_timestamp,
    previous_order_timestamp,
    EXTRACT(EPOCH FROM (
        order_purchase_timestamp - previous_order_timestamp
    )) / 86400.0 AS days_since_previous_order
FROM customer_orders
WHERE previous_order_timestamp IS NOT NULL
ORDER BY customer_unique_id, order_purchase_timestamp;


-- 14. Repeat-purchase interval statistics
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_purchase_timestamp,
        LAG(o.order_purchase_timestamp) OVER (
            PARTITION BY c.customer_unique_id
            ORDER BY o.order_purchase_timestamp
        ) AS previous_order_timestamp
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
),
intervals AS (
    SELECT EXTRACT(EPOCH FROM (
        order_purchase_timestamp - previous_order_timestamp
    )) / 86400.0 AS days_between_orders
    FROM customer_orders
    WHERE previous_order_timestamp IS NOT NULL
)
SELECT
    COUNT(*) AS repeat_purchase_intervals,
    ROUND(AVG(days_between_orders)::numeric, 2)
        AS average_days_between_orders,
    ROUND(PERCENTILE_CONT(0.50)
        WITHIN GROUP (ORDER BY days_between_orders)::numeric, 2)
        AS median_days_between_orders
FROM intervals;


-- 15. Customer lifetime-style descriptive summary
WITH customer_summary AS (
    SELECT
        c.customer_unique_id,
        MIN(o.order_purchase_timestamp) AS first_purchase,
        MAX(o.order_purchase_timestamp) AS last_purchase,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(oi.price + oi.freight_value) AS total_spend
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_unique_id
)
SELECT
    customer_unique_id,
    order_count,
    ROUND(total_spend, 2) AS total_spend,
    ROUND(EXTRACT(EPOCH FROM (
        last_purchase - first_purchase
    )) / 86400.0, 2) AS customer_active_days,
    first_purchase,
    last_purchase
FROM customer_summary
ORDER BY total_spend DESC;


-- 16. Customer spend deciles
WITH customer_revenue AS (
    SELECT
        c.customer_unique_id,
        SUM(oi.price + oi.freight_value) AS total_spend
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_unique_id
),
ranked_customers AS (
    SELECT *,
           NTILE(10) OVER (ORDER BY total_spend DESC) AS spend_decile
    FROM customer_revenue
)
SELECT
    spend_decile,
    COUNT(*) AS customer_count,
    ROUND(SUM(total_spend), 2) AS revenue,
    ROUND(AVG(total_spend), 2) AS average_customer_spend
FROM ranked_customers
GROUP BY spend_decile
ORDER BY spend_decile;


-- 17. Customer revenue concentration
WITH customer_revenue AS (
    SELECT
        c.customer_unique_id,
        SUM(oi.price + oi.freight_value) AS total_spend
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_unique_id
),
ranked AS (
    SELECT *,
           SUM(total_spend) OVER (
               ORDER BY total_spend DESC
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS cumulative_revenue,
           SUM(total_spend) OVER () AS total_revenue
    FROM customer_revenue
)
SELECT
    customer_unique_id,
    ROUND(total_spend, 2) AS total_spend,
    ROUND(100.0 * cumulative_revenue / total_revenue, 2)
        AS cumulative_revenue_percentage
FROM ranked
ORDER BY total_spend DESC
LIMIT 100;


-- 18. Customer business scorecard
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(oi.price + oi.freight_value) AS total_spend,
        COUNT(DISTINCT oi.product_id) AS unique_products,
        COUNT(DISTINCT p.product_category_name) AS unique_categories
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    JOIN olist_order_items oi ON o.order_id = oi.order_id
    LEFT JOIN olist_products p ON oi.product_id = p.product_id
    GROUP BY c.customer_unique_id
),
customer_reviews AS (
    SELECT
        c.customer_unique_id,
        AVG(r.review_score) AS average_review_score,
        COUNT(r.review_id) AS review_count
    FROM olist_customers c
    JOIN olist_orders o ON c.customer_id = o.customer_id
    LEFT JOIN olist_order_reviews r ON o.order_id = r.order_id
    GROUP BY c.customer_unique_id
)
SELECT
    co.customer_unique_id,
    co.order_count,
    ROUND(co.total_spend, 2) AS total_spend,
    co.unique_products,
    co.unique_categories,
    ROUND(cr.average_review_score, 2) AS average_review_score,
    cr.review_count
FROM customer_orders co
LEFT JOIN customer_reviews cr
    ON co.customer_unique_id = cr.customer_unique_id
ORDER BY co.total_spend DESC;
