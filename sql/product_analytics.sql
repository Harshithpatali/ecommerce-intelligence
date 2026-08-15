SELECT
    p.product_id,
    p.product_category_name,
    COUNT(DISTINCT oi.order_id) AS order_count,
    COUNT(*) AS item_count,
    ROUND(SUM(oi.price), 2) AS product_revenue,
    ROUND(AVG(oi.price), 2) AS average_item_price,
    ROUND(AVG(oi.freight_value), 2) AS average_freight
FROM olist_products p
JOIN olist_order_items oi
    ON p.product_id = oi.product_id
GROUP BY
    p.product_id,
    p.product_category_name
ORDER BY product_revenue DESC;


-- ------------------------------------------------------------
-- 2. Top products by revenue
-- ------------------------------------------------------------

SELECT
    p.product_id,
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    COUNT(*) AS item_count,
    COUNT(DISTINCT oi.order_id) AS order_count,
    ROUND(SUM(oi.price), 2) AS revenue
FROM olist_products p
JOIN olist_order_items oi
    ON p.product_id = oi.product_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY
    p.product_id,
    category
ORDER BY revenue DESC
LIMIT 20;


-- ------------------------------------------------------------
-- 3. Category performance
-- ------------------------------------------------------------

SELECT
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    COUNT(DISTINCT p.product_id) AS product_count,
    COUNT(DISTINCT oi.order_id) AS order_count,
    COUNT(*) AS item_count,
    ROUND(SUM(oi.price), 2) AS product_revenue,
    ROUND(SUM(oi.freight_value), 2) AS freight_revenue,
    ROUND(AVG(oi.price), 2) AS average_item_price
FROM olist_products p
JOIN olist_order_items oi
    ON p.product_id = oi.product_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY category
ORDER BY product_revenue DESC;


-- ------------------------------------------------------------
-- 4. Category revenue share
-- ------------------------------------------------------------

WITH category_revenue AS (
    SELECT
        COALESCE(
            t.product_category_name_english,
            p.product_category_name,
            'Unknown'
        ) AS category,
        SUM(oi.price) AS revenue
    FROM olist_products p
    JOIN olist_order_items oi
        ON p.product_id = oi.product_id
    LEFT JOIN product_category_name_translation t
        ON p.product_category_name = t.product_category_name
    GROUP BY category
)
SELECT
    category,
    ROUND(revenue, 2) AS revenue,
    ROUND(
        100.0 * revenue / SUM(revenue) OVER (),
        2
    ) AS revenue_share_pct
FROM category_revenue
ORDER BY revenue DESC;


-- ------------------------------------------------------------
-- 5. Monthly category revenue
-- ------------------------------------------------------------

SELECT
    DATE_TRUNC(
        'month',
        o.order_purchase_timestamp
    ) AS purchase_month,
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    ROUND(SUM(oi.price), 2) AS revenue,
    COUNT(DISTINCT o.order_id) AS orders
FROM olist_orders o
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
JOIN olist_products p
    ON oi.product_id = p.product_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY
    purchase_month,
    category
ORDER BY
    purchase_month,
    revenue DESC;


-- ------------------------------------------------------------
-- 6. Product price distribution summary
-- ------------------------------------------------------------

SELECT
    COUNT(*) AS item_rows,
    ROUND(MIN(price), 2) AS minimum_price,
    ROUND(
        PERCENTILE_CONT(0.25)
        WITHIN GROUP (ORDER BY price)::numeric,
        2
    ) AS p25_price,
    ROUND(
        PERCENTILE_CONT(0.50)
        WITHIN GROUP (ORDER BY price)::numeric,
        2
    ) AS median_price,
    ROUND(
        PERCENTILE_CONT(0.75)
        WITHIN GROUP (ORDER BY price)::numeric,
        2
    ) AS p75_price,
    ROUND(MAX(price), 2) AS maximum_price,
    ROUND(AVG(price), 2) AS average_price
FROM olist_order_items;


-- ------------------------------------------------------------
-- 7. Freight-to-price relationship
-- ------------------------------------------------------------

SELECT
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    ROUND(AVG(oi.price), 2) AS average_price,
    ROUND(AVG(oi.freight_value), 2) AS average_freight,
    ROUND(
        100.0 * AVG(oi.freight_value)
        / NULLIF(AVG(oi.price), 0),
        2
    ) AS freight_to_price_pct
FROM olist_products p
JOIN olist_order_items oi
    ON p.product_id = oi.product_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY category
ORDER BY freight_to_price_pct DESC;


-- ------------------------------------------------------------
-- 8. Seller performance
-- ------------------------------------------------------------

SELECT
    s.seller_id,
    s.seller_city,
    s.seller_state,
    COUNT(DISTINCT oi.order_id) AS order_count,
    COUNT(DISTINCT oi.product_id) AS product_count,
    COUNT(*) AS item_count,
    ROUND(SUM(oi.price), 2) AS product_revenue,
    ROUND(AVG(oi.price), 2) AS average_item_price
FROM olist_sellers s
JOIN olist_order_items oi
    ON s.seller_id = oi.seller_id
GROUP BY
    s.seller_id,
    s.seller_city,
    s.seller_state
ORDER BY product_revenue DESC;


-- ------------------------------------------------------------
-- 9. Top sellers by revenue
-- ------------------------------------------------------------

SELECT
    s.seller_id,
    s.seller_city,
    s.seller_state,
    COUNT(DISTINCT oi.order_id) AS orders,
    COUNT(DISTINCT oi.product_id) AS products,
    ROUND(SUM(oi.price), 2) AS revenue
FROM olist_sellers s
JOIN olist_order_items oi
    ON s.seller_id = oi.seller_id
GROUP BY
    s.seller_id,
    s.seller_city,
    s.seller_state
ORDER BY revenue DESC
LIMIT 20;


-- ------------------------------------------------------------
-- 10. Seller customer-review performance
-- ------------------------------------------------------------

SELECT
    s.seller_id,
    COUNT(DISTINCT r.review_id) AS review_count,
    ROUND(AVG(r.review_score), 2) AS average_review_score,
    COUNT(*) FILTER (
        WHERE r.review_score <= 2
    ) AS negative_reviews,
    COUNT(*) FILTER (
        WHERE r.review_score >= 4
    ) AS positive_reviews
FROM olist_sellers s
JOIN olist_order_items oi
    ON s.seller_id = oi.seller_id
JOIN olist_order_reviews r
    ON oi.order_id = r.order_id
GROUP BY s.seller_id
HAVING COUNT(r.review_id) > 0
ORDER BY average_review_score DESC;


-- ------------------------------------------------------------
-- 11. Category review performance
-- ------------------------------------------------------------

SELECT
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    COUNT(DISTINCT r.review_id) AS review_count,
    ROUND(AVG(r.review_score), 2) AS average_review_score,
    COUNT(*) FILTER (
        WHERE r.review_score <= 2
    ) AS negative_reviews,
    COUNT(*) FILTER (
        WHERE r.review_score >= 4
    ) AS positive_reviews
FROM olist_products p
JOIN olist_order_items oi
    ON p.product_id = oi.product_id
JOIN olist_order_reviews r
    ON oi.order_id = r.order_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY category
HAVING COUNT(r.review_id) > 0
ORDER BY average_review_score DESC;


-- ------------------------------------------------------------
-- 12. Product review performance
-- ------------------------------------------------------------

SELECT
    p.product_id,
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    COUNT(DISTINCT r.review_id) AS review_count,
    ROUND(AVG(r.review_score), 2) AS average_review_score,
    COUNT(*) FILTER (
        WHERE r.review_score <= 2
    ) AS negative_reviews
FROM olist_products p
JOIN olist_order_items oi
    ON p.product_id = oi.product_id
JOIN olist_order_reviews r
    ON oi.order_id = r.order_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY p.product_id, category
HAVING COUNT(r.review_id) > 0
ORDER BY average_review_score ASC, review_count DESC
LIMIT 50;


-- ------------------------------------------------------------
-- 13. Product catalog characteristics
-- ------------------------------------------------------------

SELECT
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    COUNT(*) AS products,
    ROUND(AVG(p.product_name_lenght), 2) AS avg_name_length,
    ROUND(AVG(p.product_description_lenght), 2)
        AS avg_description_length,
    ROUND(AVG(p.product_photos_qty), 2) AS avg_photo_count,
    ROUND(AVG(p.product_weight_g), 2) AS avg_weight_g
FROM olist_products p
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY category
ORDER BY products DESC;


-- ------------------------------------------------------------
-- 14. Category order-item concentration
-- ------------------------------------------------------------

WITH category_items AS (
    SELECT
        COALESCE(
            t.product_category_name_english,
            p.product_category_name,
            'Unknown'
        ) AS category,
        COUNT(*) AS item_count
    FROM olist_products p
    JOIN olist_order_items oi
        ON p.product_id = oi.product_id
    LEFT JOIN product_category_name_translation t
        ON p.product_category_name = t.product_category_name
    GROUP BY category
)
SELECT
    category,
    item_count,
    ROUND(
        100.0 * item_count / SUM(item_count) OVER (),
        2
    ) AS item_share_pct
FROM category_items
ORDER BY item_count DESC;


-- ------------------------------------------------------------
-- 15. Product sales rank within category
-- ------------------------------------------------------------

WITH product_revenue AS (
    SELECT
        p.product_id,
        COALESCE(
            t.product_category_name_english,
            p.product_category_name,
            'Unknown'
        ) AS category,
        SUM(oi.price) AS revenue
    FROM olist_products p
    JOIN olist_order_items oi
        ON p.product_id = oi.product_id
    LEFT JOIN product_category_name_translation t
        ON p.product_category_name = t.product_category_name
    GROUP BY p.product_id, category
)
SELECT
    product_id,
    category,
    ROUND(revenue, 2) AS revenue,
    DENSE_RANK() OVER (
        PARTITION BY category
        ORDER BY revenue DESC
    ) AS category_revenue_rank
FROM product_revenue
ORDER BY category, category_revenue_rank;


-- ------------------------------------------------------------
-- 16. Seller revenue rank within category
-- ------------------------------------------------------------

WITH seller_category_revenue AS (
    SELECT
        oi.seller_id,
        COALESCE(
            t.product_category_name_english,
            p.product_category_name,
            'Unknown'
        ) AS category,
        SUM(oi.price) AS revenue
    FROM olist_order_items oi
    JOIN olist_products p
        ON oi.product_id = p.product_id
    LEFT JOIN product_category_name_translation t
        ON p.product_category_name = t.product_category_name
    GROUP BY oi.seller_id, category
)
SELECT
    seller_id,
    category,
    ROUND(revenue, 2) AS revenue,
    DENSE_RANK() OVER (
        PARTITION BY category
        ORDER BY revenue DESC
    ) AS seller_category_rank
FROM seller_category_revenue
ORDER BY category, seller_category_rank;


-- ------------------------------------------------------------
-- 17. Delivery performance by category
-- ------------------------------------------------------------

SELECT
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    COUNT(DISTINCT o.order_id) AS orders,
    ROUND(
        AVG(
            EXTRACT(
                EPOCH FROM (
                    o.order_delivered_customer_date
                    - o.order_purchase_timestamp
                )
            ) / 86400.0
        )::numeric,
        2
    ) AS avg_purchase_to_delivery_days,
    ROUND(
        AVG(
            EXTRACT(
                EPOCH FROM (
                    o.order_delivered_customer_date
                    - o.order_estimated_delivery_date
                )
            ) / 86400.0
        )::numeric,
        2
    ) AS avg_delivery_vs_estimate_days
FROM olist_orders o
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
JOIN olist_products p
    ON oi.product_id = p.product_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY category
ORDER BY avg_purchase_to_delivery_days DESC;


-- ------------------------------------------------------------
-- 18. Category-level business scorecard
-- ------------------------------------------------------------

WITH category_sales AS (
    SELECT
        COALESCE(
            t.product_category_name_english,
            p.product_category_name,
            'Unknown'
        ) AS category,
        COUNT(DISTINCT p.product_id) AS product_count,
        COUNT(DISTINCT oi.order_id) AS order_count,
        COUNT(*) AS item_count,
        SUM(oi.price) AS revenue,
        AVG(oi.price) AS average_price
    FROM olist_products p
    JOIN olist_order_items oi
        ON p.product_id = oi.product_id
    LEFT JOIN product_category_name_translation t
        ON p.product_category_name = t.product_category_name
    GROUP BY category
),
category_reviews AS (
    SELECT
        COALESCE(
            t.product_category_name_english,
            p.product_category_name,
            'Unknown'
        ) AS category,
        COUNT(DISTINCT r.review_id) AS review_count,
        AVG(r.review_score) AS average_review_score
    FROM olist_products p
    JOIN olist_order_items oi
        ON p.product_id = oi.product_id
    JOIN olist_order_reviews r
        ON oi.order_id = r.order_id
    LEFT JOIN product_category_name_translation t
        ON p.product_category_name = t.product_category_name
    GROUP BY category
)
SELECT
    cs.category,
    cs.product_count,
    cs.order_count,
    cs.item_count,
    ROUND(cs.revenue, 2) AS revenue,
    ROUND(cs.average_price, 2) AS average_price,
    cr.review_count,
    ROUND(cr.average_review_score, 2) AS average_review_score
FROM category_sales cs
LEFT JOIN category_reviews cr
    ON cs.category = cr.category
ORDER BY cs.revenue DESC;
