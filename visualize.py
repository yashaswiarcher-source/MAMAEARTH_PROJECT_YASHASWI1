"""============================================================
LAYER 2b: visualize.py
------------------------------------------------------------
Run AFTER analysis/clean_and_eda.py (needs narrator/findings.json),
FROM THE REPO ROOT:

    python analysis/visualize.py

Draws BOTH charts strictly from narrator/findings.json - the same
SQL-verified numbers the GenAI layer will narrate. No new math here.
============================================================"""
import json
import os

import matplotlib.pyplot as plt

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINDINGS = json.load(open(os.path.join(REPO_ROOT, "narrator", "findings.json")))
OUT = os.path.join(REPO_ROOT, "visualizations")
os.makedirs(OUT, exist_ok=True)

# Mamaearth palette
GREEN, DARK, LIGHT, AMBER = "#66bb6a", "#1b5e20", "#c8e6c9", "#ffb300"


def return_rate_by_payment():
    rows = FINDINGS["by_payment_method"]
    labels = [r["payment_method"] for r in rows]
    rates = [r["return_rate_pct"] for r in rows]
    lost = [r["revenue_lost"] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, rates, color=[DARK, GREEN, LIGHT],
                  edgecolor="white", width=0.6)
    avg = FINDINGS["kpis"]["return_rate_pct"]
    ax.axhline(avg, color=AMBER, ls="--", lw=1.5,
               label=f"Overall return rate = {avg}%")
    for b, r, l in zip(bars, rates, lost):
        ax.text(b.get_x() + b.get_width() / 2, r + 0.8, f"{r}%",
                ha="center", fontsize=11, fontweight="bold", color=DARK)
        ax.text(b.get_x() + b.get_width() / 2, r / 2, f"₹{l:,.0f}\nlost",
                ha="center", va="center", fontsize=9, color="white")
    ax.set_title("Return Rate by Payment Method\n(bars = % of orders returned,"
                 " labels = revenue lost to returns)", fontsize=12, color=DARK)
    ax.set_ylabel("Return rate (%)")
    ax.set_ylim(0, max(rates) * 1.25)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "return_rate_by_payment.png"), dpi=150)
    plt.close(fig)


def monthly_revenue_trend():
    rows = FINDINGS["monthly_trend"]
    months = [r["month"] for r in rows]
    gross = [r["gross_revenue"] for r in rows]
    net = [r["net_revenue"] for r in rows]
    returns = [r["returns"] for r in rows]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(months, gross, color=LIGHT, label="Gross revenue")
    ax.bar(months, net, color=GREEN, label="Net revenue (after returns)")
    for i, (g, n) in enumerate(zip(gross, net)):
        ax.text(i, g + 400, f"₹{g/1000:.1f}K", ha="center", fontsize=9, color=DARK)
        ax.text(i, n / 2, f"₹{n/1000:.1f}K", ha="center", fontsize=9, color="white")
    ax2 = ax.twinx()
    ax2.plot(months, returns, color=AMBER, marker="o", lw=2,
             label="Returns (count, right axis)")
    ax2.set_ylabel("Returns (count)", color=AMBER)
    ax2.tick_params(axis="y", colors=AMBER)
    ax.set_title("Monthly Revenue Trend - Gross vs Net, with Return Volume",
                 fontsize=12, color=DARK)
    ax.set_ylabel("Revenue (₹)")
    ax.legend(loc="upper right", frameon=False)
    ax.spines[["top"]].set_visible(False)
    ax2.spines[["top"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "monthly_revenue_trend.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    return_rate_by_payment()
    monthly_revenue_trend()
    print("[visualize] wrote visualizations/return_rate_by_payment.png")
    print("[visualize] wrote visualizations/monthly_revenue_trend.png")
