"""============================================================
LAYER 2a: clean_and_eda.py  (Mamaearth Returns & Growth Intelligence)
------------------------------------------------------------
Run AFTER the sql/ layer exists, FROM THE REPO ROOT:

    python analysis/clean_and_eda.py

What it does (strict layer discipline):
  1. Executes sql/schema.sql + sql/seed_data.sql to build mamaearth.db
     (Layer 2 never touches the raw CSVs directly - only via SQL).
  2. PART-2 CLEANING (on top of the SQL-loaded table, CSV untouched):
       - removes double-submit duplicates (same everything, different order_id)
       - keeps blank discount_pct / rating as NULL (genuinely missing,
         never imputed to zero)
  3. Runs the verified report queries on the CLEANED table.
  4. Writes narrator/findings.json - the ONLY input the GenAI layer
     (narrator/generate_narrative.py) is allowed to read.
============================================================"""
import csv
import json
import os
import sqlite3
import sys

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "mamaearth.db")
FINDINGS_PATH = os.path.join(REPO_ROOT, "narrator", "findings.json")


def build_database():
    """Execute sql/schema.sql then sql/seed_data.sql against mamaearth.db.

    The .import/.mode dot-commands in seed_data.sql are sqlite3-CLI syntax,
    so this function replays them with the Python csv module - the SQL
    statements themselves run verbatim from the files.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(open(os.path.join(REPO_ROOT, "sql", "schema.sql")).read())

    sql_accum = []
    def flush():
        if sql_accum:
            conn.executescript("\n".join(sql_accum))
            sql_accum.clear()

    for line in open(os.path.join(REPO_ROOT, "sql", "seed_data.sql")):
        s = line.strip()
        if s.startswith(".import"):
            flush()
            parts = s.split()
            csv_rel, table = parts[-2], parts[-1]   # handles optional --skip N
            with open(os.path.join(REPO_ROOT, csv_rel), newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            placeholders = ",".join(["?"] * len(rows[0]))
            conn.executemany(
                f"INSERT INTO {table} VALUES ({placeholders})", rows[1:]
            )
        elif s.startswith("."):
            continue
        else:
            sql_accum.append(line)
    flush()
    conn.commit()
    return conn


def clean_orders(conn):
    """PART-2 CLEANING. Returns (clean_df, cleaning_log)."""
    raw = pd.read_sql("SELECT * FROM orders", conn)
    log = {"raw_orders": len(raw)}

    # 1) Double-submit duplicates: identical on every business field,
    #    different order_id. Keep first occurrence. CSV is NOT edited.
    fingerprint = ["customer_id", "product_id", "order_date", "quantity",
                   "discount_pct", "payment_method", "rating", "returned"]
    dupes = raw.duplicated(subset=fingerprint, keep="first")
    log["duplicates_removed"] = int(dupes.sum())
    clean = raw[~dupes].copy()

    # 2) Missing values: blanks were converted to NULL by seed_data.sql -
    #    count them, do NOT impute to zero.
    log["missing_discount_pct"] = int(clean["discount_pct"].isna().sum())
    log["missing_rating"] = int(clean["rating"].isna().sum())

    # 3) Payment-method casing is deliberately inconsistent in the raw
    #    CSV (COD/cod, Card/card/CARD, UPI/upi) - normalize it HERE,
    #    in Part 2, not by editing the CSV.
    log["payment_methods_raw"] = int(clean["payment_method"].nunique())
    pay_map = {"COD": "COD", "UPI": "UPI", "CARD": "Card"}
    clean["payment_method"] = (clean["payment_method"].str.strip().str.upper()
                               .map(pay_map))
    log["payment_methods_clean"] = int(clean["payment_method"].nunique())

    # 4) Cleaned relation written back so later runs are reproducible
    clean.to_sql("clean_orders", conn, if_exists="replace", index=False)
    log["clean_orders"] = len(clean)
    return clean, log


def run_reports(conn):
    """Verified aggregates on the CLEANED table only.
    These mirror sql/reports.sql (which documents the raw-state checks)."""
    J = ("FROM clean_orders o "
         "JOIN products p ON o.product_id = p.product_id")
    C = ("FROM clean_orders o "
         "JOIN customers c ON o.customer_id = c.customer_id "
         "JOIN products  p ON o.product_id  = p.product_id")

    rev = "o.quantity * p.price * (1 - COALESCE(o.discount_pct,0)/100.0)"
    lost = f"CASE WHEN o.returned=1 THEN {rev} END"
    ok = "CASE WHEN o.returned=0 THEN 1 ELSE 0 END"
    ret = "CASE WHEN o.returned=1 THEN 1 ELSE 0 END"

    def q(sql):
        return pd.read_sql(sql, conn).to_dict("records")

    reports = {
        "kpis": q(f"""
            SELECT COUNT(*) AS total_orders,
                   SUM({ok}) AS successful_orders,
                   SUM({ret}) AS returned_orders,
                   ROUND(100.0*SUM({ret})/COUNT(*), 2) AS return_rate_pct,
                   ROUND(SUM({rev}), 2) AS gross_revenue,
                   ROUND(SUM(CASE WHEN o.returned=0 THEN {rev} END), 2) AS net_revenue,
                   ROUND(SUM({lost}), 2) AS revenue_lost_to_returns,
                   ROUND(AVG(CASE WHEN o.discount_pct IS NOT NULL THEN o.discount_pct END), 2) AS avg_discount_pct,
                   ROUND(AVG(o.rating), 2) AS avg_rating
            {J}""")[0],
        "by_payment_method": q(f"""
            SELECT o.payment_method AS payment_method, COUNT(*) AS orders,
                   SUM({ret}) AS returns,
                   ROUND(100.0*SUM({ret})/COUNT(*), 2) AS return_rate_pct,
                   ROUND(SUM({lost}), 2) AS revenue_lost
            {J} GROUP BY o.payment_method ORDER BY return_rate_pct DESC"""),
        "monthly_trend": q(f"""
            SELECT strftime('%Y-%m', o.order_date) AS month,
                   ROUND(SUM({rev}), 2) AS gross_revenue,
                   ROUND(SUM(CASE WHEN o.returned=0 THEN {rev} END), 2) AS net_revenue,
                   SUM({ret}) AS returns
            {J} GROUP BY month ORDER BY month"""),
        "by_category": q(f"""
            SELECT p.category AS category, COUNT(*) AS orders,
                   ROUND(100.0*SUM({ret})/COUNT(*), 2) AS return_rate_pct,
                   ROUND(SUM({lost}), 2) AS revenue_lost
            {J} GROUP BY p.category ORDER BY revenue_lost DESC"""),
        "by_city_tier": q(f"""
            SELECT c.city_tier AS city_tier, COUNT(*) AS orders,
                   ROUND(100.0*SUM({ret})/COUNT(*), 2) AS return_rate_pct,
                   ROUND(SUM({lost}), 2) AS revenue_lost
            {C} GROUP BY c.city_tier ORDER BY return_rate_pct DESC"""),
        "by_acquisition_source": q(f"""
            SELECT c.acquisition_source AS acquisition_source, COUNT(*) AS orders,
                   ROUND(100.0*SUM({ret})/COUNT(*), 2) AS return_rate_pct,
                   ROUND(SUM({lost}), 2) AS revenue_lost
            {C} GROUP BY c.acquisition_source ORDER BY return_rate_pct DESC"""),
        "top_returned_products": q(f"""
            SELECT p.product_name AS product_name, p.category AS category,
                   COUNT(*) AS orders, SUM({ret}) AS returns,
                   ROUND(100.0*SUM({ret})/COUNT(*), 2) AS return_rate_pct,
                   ROUND(SUM({lost}), 2) AS revenue_lost
            {J} GROUP BY p.product_id ORDER BY revenue_lost DESC LIMIT 10"""),
        "customer_loyalty": q("""
            WITH co AS (SELECT customer_id, COUNT(*) n_orders,
                               SUM(returned) AS n_returns
                        FROM clean_orders GROUP BY customer_id)
            SELECT CASE WHEN n_orders > 1 THEN 'repeat' ELSE 'one-time' END AS customer_type,
                   COUNT(*) AS customers, ROUND(AVG(n_orders), 2) AS avg_orders,
                   ROUND(100.0*AVG(n_returns)/AVG(n_orders), 2) AS avg_return_rate_pct
            FROM co GROUP BY customer_type"""),
        "rating_vs_returns": q(f"""
            SELECT o.returned, COUNT(*) AS orders, COUNT(o.rating) AS rated_orders,
                   ROUND(AVG(o.rating), 2) AS avg_rating
            FROM clean_orders o GROUP BY o.returned"""),
    }
    return reports


def main():
    os.makedirs(os.path.dirname(FINDINGS_PATH), exist_ok=True)
    conn = build_database()
    clean, log = clean_orders(conn)
    findings = {
        "pipeline": "Layer 1 (SQL) -> Layer 2 (Python) -> Layer 3 (GenAI)",
        "source": "mamaearth.db / clean_orders (deduplicated, missing kept as NULL)",
        "data_quality": log,
        **run_reports(conn),
    }
    with open(FINDINGS_PATH, "w") as f:
        json.dump(findings, f, indent=2)
    conn.close()
    print(f"[clean_and_eda] raw={log['raw_orders']} clean={log['clean_orders']} "
          f"dupes_removed={log['duplicates_removed']} | findings -> {FINDINGS_PATH}")
    return findings


if __name__ == "__main__":
    main()
