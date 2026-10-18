-- ============================================================
-- Task 2 — Load seed data (sql/seed_data.sql)
-- Run SECOND (from repo root):  sqlite3 mamaearth.db < sql/seed_data.sql
-- ============================================================

.mode csv

-- .import loads every blank discount_pct / rating cell as an empty
-- string, NOT NULL - confirm with:  SELECT typeof(rating) FROM orders;
-- The two UPDATEs below fix that BEFORE any report runs.
.import --skip 1 data/customers.csv customers
.import --skip 1 data/products.csv  products
.import --skip 1 data/orders.csv    orders

UPDATE orders SET discount_pct = NULL WHERE discount_pct = '';
UPDATE orders SET rating       = NULL WHERE rating       = '';

-- Verification (expected: 45 / 16 / 180)
SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM orders;
