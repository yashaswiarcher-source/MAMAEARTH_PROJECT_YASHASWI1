-- ============================================================
-- Task 3 — Reports (sql/reports.sql)
-- Run THIRD, against the loaded RAW (uncleaned) data:
--   sqlite3 mamaearth.db < sql/reports.sql
-- Verified outputs are pasted above each query.
-- ============================================================

-- ------------------------------------------------------------
-- (a) Order totals. Revenue per row = quantity * price * (1 - discount_pct/100),
--     NULL discount treated as 0% via COALESCE. Joins orders to products.
--     Expected / verified output:
--       180 | 99860.20 | 554.78
-- ------------------------------------------------------------
SELECT
    COUNT(*) AS total_orders,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
    ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON o.product_id = p.product_id;

-- ------------------------------------------------------------
-- (b) COUNT(*) vs COUNT(column): COUNT(rating) skips NULLs, so the
--     difference is exactly the number of unrated orders.
--     Expected / verified output:
--       180 | 165 | 15
-- ------------------------------------------------------------
SELECT
    COUNT(*)              AS all_orders,
    COUNT(rating)         AS rated_orders,
    COUNT(*) - COUNT(rating) AS unrated_orders
FROM orders;

-- ------------------------------------------------------------
-- (c1) LEFT JOIN with a genuine zero-match row: customers with no orders.
--      Expected / verified output:
--        C045 | Vihaan
-- ------------------------------------------------------------
SELECT c.customer_id, c.name
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- ------------------------------------------------------------
-- (c2) Independent NOT IN cross-check — returns the same customer,
--      confirming the LEFT JOIN result rather than trusting it blindly.
--      Expected / verified output:
--        C045 | Vihaan
-- ------------------------------------------------------------
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);

-- ------------------------------------------------------------
-- (d) GROUP BY + HAVING: city-level return rates, only cities above 20%.
--     Expected / verified output:
--       Jaipur    | 19 | 8  | 42.1
--       Lucknow   | 49 | 15 | 30.6
--       Bangalore | 33 | 8  | 24.2
-- ------------------------------------------------------------
SELECT
    c.city,
    COUNT(*)                                   AS total_orders,
    SUM(o.returned)                            AS returned_orders,
    ROUND(100.0 * SUM(o.returned) / COUNT(*), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;

-- ------------------------------------------------------------
-- (e1) Top 5 customers by total_spend (discount-aware revenue, same
--      formula as (a)). customer_id ASC is the tie-break so the ranking
--      is deterministic when two customers spend the same amount —
--      without it, equal-spend rows could swap order between runs.
--      Expected / verified output:
--        C043 | Reyansh | 12920.00
--        C026 | Isha    | 8371.60
--        C008 | Meera   | 4564.60
--        C011 | Arjun   | 4111.00
--        C042 | Sanya   | 3785.00
-- ------------------------------------------------------------
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products  p ON o.product_id  = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 5;

-- ------------------------------------------------------------
-- (e2) Same ranking, LIMIT 3 OFFSET 2 -> ranks 3-5 without
--      re-deriving the top 5. Must return the last three rows of (e1),
--      same order.
--      Expected / verified output:
--        C008 | Meera | 4564.60
--        C011 | Arjun | 4111.00
--        C042 | Sanya | 3785.00
-- ------------------------------------------------------------
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products  p ON o.product_id  = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;

-- ------------------------------------------------------------
-- (f) Three-table JOIN with GROUP BY: revenue by category.
--     (Only orders+products are strictly needed, but the three-way
--      join must compile cleanly — Part 3's pipeline reuses it.)
--     Expected / verified output:
--       Haircare       | 54 | 44956.10
--       Skincare       | 60 | 27346.00
--       Babycare       | 30 | 16805.00
--       PersonalCare   | 36 | 10753.10
-- ------------------------------------------------------------
SELECT
    p.category,
    COUNT(*)  AS order_count,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products  p ON o.product_id  = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;

-- ------------------------------------------------------------
-- (g) LIKE pattern match: customers whose name starts with 'A'.
--     Expected / verified output (10 rows):
--       C001 | Aarav     C003 | Aditi     C004 | Ananya    C011 | Arjun
--       C021 | Aryan     C030 | Anika     C031 | Aditya    C036 | Aisha
--       C041 | Ayaan     C044 | Aria
-- ------------------------------------------------------------
SELECT customer_id, name
FROM customers
WHERE name LIKE 'A%'
ORDER BY customer_id;

-- ------------------------------------------------------------
-- (h) DISTINCT acquisition sources across all customers.
--     Expected / verified output (4 rows):
--       Ad | Organic | Referral | Social
-- ------------------------------------------------------------
SELECT DISTINCT acquisition_source
FROM customers
ORDER BY acquisition_source;

-- ------------------------------------------------------------
-- (i) ALTER TABLE + UPDATE with CASE: add loyalty_tier, then assign
--     Gold to Tier-1 cities, Silver otherwise (no WHERE — every row
--     gets a value).
--     Expected / verified output of the verification SELECT:
--       Gold | 28
--       Silver | 17
-- ------------------------------------------------------------
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);

UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;

SELECT loyalty_tier, COUNT(*) AS customers
FROM customers
GROUP BY loyalty_tier;
