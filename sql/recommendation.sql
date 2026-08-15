SELECT
    oi.product_id,
    COUNT(*) AS purchase_count,
    COUNT(DISTINCT oi.order_id) AS order_count,
    COUNT(DISTINCT o.customer_id) AS customer_count,
    ROUND(SUM(oi.price), 2) AS revenue
FROM olist_order_items oi
JOIN olist_orders o
    ON oi.order_id = o.order_id
GROUP BY oi.product_id
ORDER BY purchase_count DESC
LIMIT 100;


-- ------------------------------------------------------------
-- 2. Category-level product popularity
-- ------------------------------------------------------------

SELECT
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    oi.product_id,
    COUNT(*) AS purchase_count,
    COUNT(DISTINCT o.customer_id) AS customer_count
FROM olist_order_items oi
JOIN olist_orders o
    ON oi.order_id = o.order_id
JOIN olist_products p
    ON oi.product_id = p.product_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY
    category,
    oi.product_id
ORDER BY
    category,
    purchase_count DESC;


-- ------------------------------------------------------------
-- 3. Customer-product purchase interactions
-- ------------------------------------------------------------
--
-- One row represents a customer purchasing a product.
-- Purchase count is retained as a simple interaction strength.
-- ------------------------------------------------------------

SELECT
    c.customer_unique_id,
    oi.product_id,
    COUNT(*) AS purchase_count,
    COUNT(DISTINCT o.order_id) AS order_count,
    MIN(o.order_purchase_timestamp) AS first_purchase,
    MAX(o.order_purchase_timestamp) AS last_purchase,
    SUM(oi.price) AS product_spend
FROM olist_customers c
JOIN olist_orders o
    ON c.customer_id = o.customer_id
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
GROUP BY
    c.customer_unique_id,
    oi.product_id;


-- ------------------------------------------------------------
-- 4. Customer-product interaction with recency
-- ------------------------------------------------------------

WITH interaction_base AS (
    SELECT
        c.customer_unique_id,
        oi.product_id,
        COUNT(*) AS purchase_count,
        MAX(o.order_purchase_timestamp) AS last_purchase
    FROM olist_customers c
    JOIN olist_orders o
        ON c.customer_id = o.customer_id
    JOIN olist_order_items oi
        ON o.order_id = oi.order_id
    GROUP BY
        c.customer_unique_id,
        oi.product_id
),
dataset_end AS (
    SELECT MAX(order_purchase_timestamp) AS max_purchase_timestamp
    FROM olist_orders
)
SELECT
    i.customer_unique_id,
    i.product_id,
    i.purchase_count,
    i.last_purchase,
    EXTRACT(
        EPOCH FROM (
            d.max_purchase_timestamp - i.last_purchase
        )
    ) / 86400.0 AS days_since_last_purchase
FROM interaction_base i
CROSS JOIN dataset_end d
ORDER BY
    i.customer_unique_id,
    i.last_purchase DESC;


-- ------------------------------------------------------------
-- 5. Customer category preferences
-- ------------------------------------------------------------

SELECT
    c.customer_unique_id,
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    COUNT(*) AS purchase_count,
    SUM(oi.price) AS category_spend
FROM olist_customers c
JOIN olist_orders o
    ON c.customer_id = o.customer_id
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
JOIN olist_products p
    ON oi.product_id = p.product_id
LEFT JOIN product_category_name_translation t
    ON p.product_category_name = t.product_category_name
GROUP BY
    c.customer_unique_id,
    category
ORDER BY
    c.customer_unique_id,
    purchase_count DESC;


-- ------------------------------------------------------------
-- 6. Customer preferred categories
-- ------------------------------------------------------------

WITH category_preferences AS (
    SELECT
        c.customer_unique_id,
        COALESCE(
            t.product_category_name_english,
            p.product_category_name,
            'Unknown'
        ) AS category,
        COUNT(*) AS purchase_count,
        SUM(oi.price) AS category_spend
    FROM olist_customers c
    JOIN olist_orders o
        ON c.customer_id = o.customer_id
    JOIN olist_order_items oi
        ON o.order_id = oi.order_id
    JOIN olist_products p
        ON oi.product_id = p.product_id
    LEFT JOIN product_category_name_translation t
        ON p.product_category_name = t.product_category_name
    GROUP BY c.customer_unique_id, category
),
ranked_preferences AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_unique_id
            ORDER BY purchase_count DESC, category_spend DESC
        ) AS category_rank
    FROM category_preferences
)
SELECT
    customer_unique_id,
    category,
    purchase_count,
    ROUND(category_spend, 2) AS category_spend
FROM ranked_preferences
WHERE category_rank <= 5
ORDER BY customer_unique_id, category_rank;


-- ------------------------------------------------------------
-- 7. Products purchased together in the same order
-- ------------------------------------------------------------
--
-- This is the SQL foundation for item-item collaborative filtering.
-- Self-pairs and duplicate pair directions are removed.
-- ------------------------------------------------------------

SELECT
    oi1.product_id AS product_a,
    oi2.product_id AS product_b,
    COUNT(DISTINCT oi1.order_id) AS co_purchase_orders
FROM olist_order_items oi1
JOIN olist_order_items oi2
    ON oi1.order_id = oi2.order_id
   AND oi1.product_id < oi2.product_id
GROUP BY
    oi1.product_id,
    oi2.product_id
ORDER BY co_purchase_orders DESC
LIMIT 100;


-- ------------------------------------------------------------
-- 8. Category-aware product co-purchases
-- ------------------------------------------------------------

WITH product_pairs AS (
    SELECT
        oi1.product_id AS product_a,
        oi2.product_id AS product_b,
        COUNT(DISTINCT oi1.order_id) AS co_purchase_orders
    FROM olist_order_items oi1
    JOIN olist_order_items oi2
        ON oi1.order_id = oi2.order_id
       AND oi1.product_id < oi2.product_id
    GROUP BY oi1.product_id, oi2.product_id
)
SELECT
    pp.product_a,
    p1.product_category_name AS product_a_category,
    pp.product_b,
    p2.product_category_name AS product_b_category,
    pp.co_purchase_orders
FROM product_pairs pp
JOIN olist_products p1
    ON pp.product_a = p1.product_id
JOIN olist_products p2
    ON pp.product_b = p2.product_id
ORDER BY pp.co_purchase_orders DESC
LIMIT 100;


-- ------------------------------------------------------------
-- 9. Customer purchase history
-- ------------------------------------------------------------

SELECT
    c.customer_unique_id,
    o.order_id,
    o.order_purchase_timestamp,
    oi.product_id,
    p.product_category_name,
    oi.price,
    oi.freight_value
FROM olist_customers c
JOIN olist_orders o
    ON c.customer_id = o.customer_id
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
JOIN olist_products p
    ON oi.product_id = p.product_id
ORDER BY
    c.customer_unique_id,
    o.order_purchase_timestamp DESC;


-- ------------------------------------------------------------
-- 10. Candidate products not previously purchased
-- ------------------------------------------------------------

SELECT
    c.customer_unique_id,
    p.product_id
FROM (
    SELECT DISTINCT customer_unique_id
    FROM olist_customers
) c
CROSS JOIN olist_products p
WHERE NOT EXISTS (
    SELECT 1
    FROM olist_customers c2
    JOIN olist_orders o
        ON c2.customer_id = o.customer_id
    JOIN olist_order_items oi
        ON o.order_id = oi.order_id
    WHERE c2.customer_unique_id = c.customer_unique_id
      AND oi.product_id = p.product_id
)
LIMIT 1000;


-- ------------------------------------------------------------
-- 11. Time-aware interaction split
-- ------------------------------------------------------------
--
-- Defines a global temporal cutoff at the 80th percentile of order
-- purchase timestamps. Python will later use the same principle for
-- recommendation evaluation.
-- ------------------------------------------------------------

WITH cutoff AS (
    SELECT PERCENTILE_CONT(0.80)
        WITHIN GROUP (
            ORDER BY order_purchase_timestamp
        ) AS cutoff_timestamp
    FROM olist_orders
)
SELECT
    CASE
        WHEN o.order_purchase_timestamp <= c.cutoff_timestamp
            THEN 'train'
        ELSE 'test'
    END AS split,
    COUNT(DISTINCT o.order_id) AS orders,
    COUNT(DISTINCT o.customer_id) AS customers,
    COUNT(*) AS item_interactions
FROM olist_orders o
CROSS JOIN cutoff c
GROUP BY split
ORDER BY split;


-- ------------------------------------------------------------
-- 12. Training interactions for time-aware evaluation
-- ------------------------------------------------------------

WITH cutoff AS (
    SELECT PERCENTILE_CONT(0.80)
        WITHIN GROUP (
            ORDER BY order_purchase_timestamp
        ) AS cutoff_timestamp
    FROM olist_orders
)
SELECT
    c.customer_unique_id,
    oi.product_id,
    COUNT(*) AS interaction_strength
FROM olist_customers c
JOIN olist_orders o
    ON c.customer_id = o.customer_id
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
CROSS JOIN cutoff
WHERE o.order_purchase_timestamp <= cutoff.cutoff_timestamp
GROUP BY
    c.customer_unique_id,
    oi.product_id;


-- ------------------------------------------------------------
-- 13. Future interactions for time-aware evaluation
-- ------------------------------------------------------------

WITH cutoff AS (
    SELECT PERCENTILE_CONT(0.80)
        WITHIN GROUP (
            ORDER BY order_purchase_timestamp
        ) AS cutoff_timestamp
    FROM olist_orders
)
SELECT
    c.customer_unique_id,
    oi.product_id,
    COUNT(*) AS future_interaction_strength
FROM olist_customers c
JOIN olist_orders o
    ON c.customer_id = o.customer_id
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
CROSS JOIN cutoff
WHERE o.order_purchase_timestamp > cutoff.cutoff_timestamp
GROUP BY
    c.customer_unique_id,
    oi.product_id;


-- ------------------------------------------------------------
-- 14. Popular products using training-period data only
-- ------------------------------------------------------------

WITH cutoff AS (
    SELECT PERCENTILE_CONT(0.80)
        WITHIN GROUP (
            ORDER BY order_purchase_timestamp
        ) AS cutoff_timestamp
    FROM olist_orders
)
SELECT
    oi.product_id,
    COUNT(*) AS training_purchase_count,
    COUNT(DISTINCT o.customer_id) AS training_customer_count,
    ROUND(SUM(oi.price), 2) AS training_revenue
FROM olist_orders o
JOIN olist_order_items oi
    ON o.order_id = oi.order_id
CROSS JOIN cutoff
WHERE o.order_purchase_timestamp <= cutoff.cutoff_timestamp
GROUP BY oi.product_id
ORDER BY training_purchase_count DESC
LIMIT 100;


-- ------------------------------------------------------------
-- 15. Product co-purchase strength
-- ------------------------------------------------------------
--
-- Jaccard-style support can be calculated from product pair counts.
-- This query exposes pair support and individual product frequencies.
-- ------------------------------------------------------------

WITH product_frequency AS (
    SELECT
        product_id,
        COUNT(DISTINCT order_id) AS product_order_count
    FROM olist_order_items
    GROUP BY product_id
),
product_pairs AS (
    SELECT
        oi1.product_id AS product_a,
        oi2.product_id AS product_b,
        COUNT(DISTINCT oi1.order_id) AS co_purchase_orders
    FROM olist_order_items oi1
    JOIN olist_order_items oi2
        ON oi1.order_id = oi2.order_id
       AND oi1.product_id < oi2.product_id
    GROUP BY oi1.product_id, oi2.product_id
)
SELECT
    pp.product_a,
    pp.product_b,
    pp.co_purchase_orders,
    pf1.product_order_count AS product_a_orders,
    pf2.product_order_count AS product_b_orders,
    ROUND(
        pp.co_purchase_orders::numeric
        / NULLIF(
            pf1.product_order_count
            + pf2.product_order_count
            - pp.co_purchase_orders,
            0
        ),
        4
    ) AS jaccard_similarity
FROM product_pairs pp
JOIN product_frequency pf1
    ON pp.product_a = pf1.product_id
JOIN product_frequency pf2
    ON pp.product_b = pf2.product_id
ORDER BY jaccard_similarity DESC
LIMIT 100;
