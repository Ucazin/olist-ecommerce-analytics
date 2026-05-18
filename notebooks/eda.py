"""
eda.py — Generate the chart deck for the Olist warehouse.

Reproduces every visual specified in dashboard/DASHBOARD_SPEC.md as a Python
chart so the portfolio reader can see results without spinning up Power BI.

Run after src/run_pipeline.py has built olist.duckdb. Outputs go to outputs/.

Usage:
    py -3.12 notebooks/eda.py
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import seaborn as sns

DB_PATH = "olist.duckdb"
OUT_DIR = Path("outputs")
OUT_DIR.mkdir(exist_ok=True)

PRIMARY  = "#2E86AB"
POSITIVE = "#06A77D"
WARN     = "#F18F01"
ALERT    = "#C73E1D"
NEUTRAL  = "#4C4C4C"

sns.set_theme(style="whitegrid", context="talk")
plt.rcParams["figure.dpi"] = 110
plt.rcParams["font.family"] = "DejaVu Sans"


def q(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def chart_01_revenue_by_category(con):
    df = q(con, """
        WITH cat_rev AS (
            SELECT p.category_en, SUM(f.gross_revenue) AS revenue
            FROM analytics.fact_orders f
            JOIN analytics.dim_product p ON p.product_key = f.product_key
            WHERE f.order_status = 'delivered'
            GROUP BY p.category_en
        )
        SELECT category_en, revenue
        FROM cat_rev ORDER BY revenue DESC LIMIT 15
    """)
    fig, ax = plt.subplots(figsize=(11, 6.5))
    sns.barplot(data=df, x="revenue", y="category_en", color=PRIMARY, ax=ax)
    ax.set_title("Q1 — Top 15 Product Categories by Revenue")
    ax.set_xlabel("Revenue (R$)")
    ax.set_ylabel("")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"R$ {x/1e6:.1f}M"))
    fig.tight_layout()
    fig.savefig(OUT_DIR / "01_revenue_by_category.png")
    plt.close(fig)


def chart_02_state_clv(con):
    df = q(con, """
        SELECT c.customer_state,
               COUNT(DISTINCT f.customer_key) AS customers,
               SUM(f.gross_revenue) / COUNT(DISTINCT f.customer_key) AS avg_clv
        FROM analytics.fact_orders f
        JOIN analytics.dim_customer c ON c.customer_key = f.customer_key
        WHERE f.order_status = 'delivered'
        GROUP BY c.customer_state
        HAVING COUNT(DISTINCT f.customer_key) >= 100
        ORDER BY avg_clv DESC
    """)
    fig, ax = plt.subplots(figsize=(11, 7))
    sns.barplot(data=df, x="avg_clv", y="customer_state", color=PRIMARY, ax=ax)
    ax.set_title("Q2 — Average Customer Lifetime Value (CLV) by State")
    ax.set_xlabel("Avg CLV (R$)")
    ax.set_ylabel("")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"R$ {x:.0f}"))
    fig.tight_layout()
    fig.savefig(OUT_DIR / "02_state_clv.png")
    plt.close(fig)


def chart_03_review_by_delivery(con):
    df = q(con, """
        SELECT
            CASE
                WHEN delivery_lag_days <= 0            THEN '1. on time'
                WHEN delivery_lag_days BETWEEN 1 AND 7 THEN '2. 1-7 d late'
                ELSE                                        '3. 8+ d late'
            END AS lateness,
            AVG(review_score) AS avg_review,
            COUNT(*)          AS orders
        FROM analytics.fact_orders
        WHERE order_status = 'delivered' AND review_score IS NOT NULL
        GROUP BY lateness
        ORDER BY lateness
    """)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = sns.barplot(data=df, x="lateness", y="avg_review",
                       palette=[POSITIVE, WARN, ALERT], ax=ax)
    ax.set_title("Q3 — Review Score Collapses When Delivery Slips")
    ax.set_ylim(0, 5)
    ax.set_xlabel("")
    ax.set_ylabel("Avg review score (1-5)")
    for bar, (_, row) in zip(bars.patches, df.iterrows()):
        ax.annotate(f"{row['avg_review']:.2f}\n({row['orders']:,} orders)",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "03_review_by_delivery.png")
    plt.close(fig)


def chart_04_bottleneck_decomposition(con):
    df = q(con, """
        SELECT
            CASE WHEN delivery_lag_days <= 0 THEN 'On time' ELSE 'Late' END AS lateness,
            AVG(DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_carrier_date))     AS seller_dispatch,
            AVG(DATE_DIFF('day', o.order_delivered_carrier_date, o.order_delivered_customer_date)) AS carrier_transit,
            COUNT(*) AS orders
        FROM analytics.fact_orders f
        JOIN raw_olist.orders o ON o.order_id = f.order_key
        WHERE f.order_status = 'delivered'
        GROUP BY lateness
    """)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = range(len(df))
    ax.bar(x, df["seller_dispatch"], label="Seller dispatch", color=PRIMARY)
    ax.bar(x, df["carrier_transit"], bottom=df["seller_dispatch"],
           label="Carrier transit", color=WARN)
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["lateness"])
    ax.set_title("Q4 — Where Late Orders Lose Time")
    ax.set_ylabel("Avg days from purchase to customer")
    ax.legend(loc="upper left")
    for i, row in df.iterrows():
        total = row["seller_dispatch"] + row["carrier_transit"]
        ax.text(i, total + 0.5, f"{total:.1f} d", ha="center", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "04_bottleneck_decomposition.png")
    plt.close(fig)


def chart_05_cohort_retention(con):
    df = q(con, """
        WITH first_purchase AS (
            SELECT customer_key,
                   date_trunc('month', MIN(order_purchase_timestamp))::DATE AS cohort_month
            FROM analytics.fact_orders
            GROUP BY customer_key
        ),
        oc AS (
            SELECT f.customer_key, fp.cohort_month,
                   DATE_DIFF('month', fp.cohort_month, date_trunc('month', f.order_purchase_timestamp)) AS m
            FROM analytics.fact_orders f
            JOIN first_purchase fp ON fp.customer_key = f.customer_key
        )
        SELECT cohort_month, m AS months_since_first, COUNT(DISTINCT customer_key) AS active
        FROM oc
        WHERE m BETWEEN 0 AND 6
        GROUP BY cohort_month, m
    """)
    pivot = df.pivot(index="cohort_month", columns="months_since_first", values="active")
    base = pivot[0]
    retention = pivot.div(base, axis=0)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.heatmap(retention, annot=True, fmt=".0%",
                cmap="Blues", cbar_kws={"label": "Retention rate"},
                vmin=0, vmax=0.2, ax=ax)
    ax.set_title("Q5 — Monthly Cohort Retention (first 6 months)")
    ax.set_xlabel("Months since first order")
    ax.set_ylabel("Cohort (month of first order)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "05_cohort_retention.png")
    plt.close(fig)


def chart_06_payment_mix(con):
    df = q(con, """
        SELECT p.category_en,
               COUNT(*) AS orders,
               AVG(f.max_installments) AS avg_installments,
               AVG(CASE WHEN primary_payment_type='credit_card' THEN 1.0 ELSE 0 END) AS pct_credit_card,
               AVG(CASE WHEN primary_payment_type='boleto'      THEN 1.0 ELSE 0 END) AS pct_boleto
        FROM analytics.fact_orders f
        JOIN analytics.dim_product p ON p.product_key = f.product_key
        WHERE f.order_status = 'delivered'
        GROUP BY p.category_en
        HAVING COUNT(*) >= 200
        ORDER BY avg_installments DESC
        LIMIT 12
    """)
    fig, ax = plt.subplots(figsize=(11, 6.5))
    bars = sns.barplot(data=df, x="avg_installments", y="category_en",
                       color=PRIMARY, ax=ax)
    ax.set_title("Q6 — Avg Credit-Card Installments by Category (top 12)")
    ax.set_xlabel("Avg installments")
    ax.set_ylabel("")
    for bar, (_, row) in zip(bars.patches, df.iterrows()):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f"{row['avg_installments']:.1f}x · {row['pct_credit_card']:.0%} CC",
                va="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "06_payment_mix.png")
    plt.close(fig)


def chart_07_worst_sellers(con):
    df = q(con, """
        SELECT s.seller_state,
               COUNT(*) AS delivered_orders,
               AVG(f.review_score) AS avg_review,
               AVG(CASE WHEN f.review_score <= 2 THEN 1.0 ELSE 0 END) AS pct_low_review,
               SUM(f.gross_revenue) AS revenue
        FROM analytics.fact_orders f
        JOIN analytics.dim_seller s ON s.seller_key = f.seller_key
        WHERE f.order_status = 'delivered'
        GROUP BY s.seller_state
        HAVING COUNT(*) >= 200
        ORDER BY pct_low_review DESC
        LIMIT 15
    """)
    df["revenue_at_risk"] = df["revenue"] * df["pct_low_review"]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    bars = sns.barplot(data=df, x="revenue_at_risk", y="seller_state",
                       color=ALERT, ax=ax)
    ax.set_title("Q7 — Revenue-at-Risk by Seller State (low-review share × revenue)")
    ax.set_xlabel("Revenue at risk (R$)")
    ax.set_ylabel("Seller state")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"R$ {x/1000:.0f}k"))
    for bar, (_, row) in zip(bars.patches, df.iterrows()):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f"  {row['pct_low_review']:.0%} low / {row['delivered_orders']:,} orders",
                va="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "07_worst_sellers.png")
    plt.close(fig)


def chart_08_freight_share(con):
    df = q(con, """
        SELECT c.customer_state,
               SUM(f.gross_revenue) AS revenue,
               SUM(f.total_freight) AS freight,
               SUM(f.total_freight) * 1.0 / NULLIF(SUM(f.gross_revenue), 0) AS freight_share
        FROM analytics.fact_orders f
        JOIN analytics.dim_customer c ON c.customer_key = f.customer_key
        WHERE f.order_status = 'delivered'
        GROUP BY c.customer_state
        HAVING SUM(f.gross_revenue) > 10000
        ORDER BY freight_share DESC
    """)
    fig, ax = plt.subplots(figsize=(11, 7))
    palette = [ALERT if v > 0.20 else WARN if v > 0.15 else POSITIVE
               for v in df["freight_share"]]
    sns.barplot(data=df, x="freight_share", y="customer_state",
                palette=palette, ax=ax)
    ax.set_title("Q8 — Freight as a Share of Order Value, by State")
    ax.set_xlabel("Freight share of revenue")
    ax.set_ylabel("")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(OUT_DIR / "08_freight_share.png")
    plt.close(fig)


def chart_09_seasonality(con):
    df = q(con, """
        SELECT d.year, d.month, d.day_of_week,
               COUNT(*) AS orders
        FROM analytics.fact_orders f
        JOIN analytics.dim_date d ON d.date_key = f.purchase_date_key
        WHERE f.order_status = 'delivered'
        GROUP BY d.year, d.month, d.day_of_week
    """)
    # Aggregate across years for DoW × Month heatmap
    df_agg = df.groupby(["month", "day_of_week"])["orders"].sum().reset_index()
    pivot = df_agg.pivot(index="day_of_week", columns="month", values="orders")
    dow_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    pivot.index = [dow_labels[int(i)] for i in pivot.index]
    fig, ax = plt.subplots(figsize=(12, 5.5))
    sns.heatmap(pivot, cmap="YlOrRd", annot=True, fmt=",.0f",
                cbar_kws={"label": "Orders"}, ax=ax)
    ax.set_title("Q9 — Demand Heatmap: Day of Week × Month")
    ax.set_xlabel("Month")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "09_seasonality_heatmap.png")
    plt.close(fig)


def chart_10_monthly_revenue(con):
    df = q(con, """
        SELECT date_trunc('month', order_purchase_timestamp)::DATE AS month,
               SUM(gross_revenue) AS revenue,
               COUNT(*) AS orders
        FROM analytics.fact_orders
        WHERE order_status = 'delivered'
        GROUP BY 1
        ORDER BY 1
    """)
    df["rolling"] = df["revenue"].rolling(3, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(df["month"], df["revenue"], label="Monthly revenue",
            color=PRIMARY, marker="o", linewidth=2)
    ax.plot(df["month"], df["rolling"], label="3-mo rolling avg",
            color=ALERT, linewidth=2, linestyle="--")
    ax.set_title("Q10 — Monthly Revenue with Black Friday Spike (Nov 2017)")
    ax.set_xlabel("")
    ax.set_ylabel("Revenue")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"R$ {x/1e6:.1f}M"))
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "10_monthly_revenue.png")
    plt.close(fig)


def summary(con):
    df = q(con, """
        SELECT
            COUNT(*)                                                        AS orders,
            COUNT(DISTINCT customer_key)                                    AS customers,
            ROUND(SUM(gross_revenue), 2)                                    AS revenue,
            ROUND(AVG(review_score), 2)                                     AS avg_review,
            ROUND(AVG(CASE WHEN delivery_lag_days > 0 THEN 1.0 ELSE 0.0 END), 4) AS pct_late,
            ROUND(AVG(fulfillment_days), 1)                                 AS avg_fulfillment_days
        FROM analytics.fact_orders
        WHERE order_status = 'delivered'
    """)
    print("\n=== Olist Headline Stats (delivered orders) ===")
    print(df.T.to_string(header=False))


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(
            "Warehouse not built. Run src/run_pipeline.py first."
        )
    con = duckdb.connect(DB_PATH, read_only=True)
    chart_01_revenue_by_category(con)
    chart_02_state_clv(con)
    chart_03_review_by_delivery(con)
    chart_04_bottleneck_decomposition(con)
    chart_05_cohort_retention(con)
    chart_06_payment_mix(con)
    chart_07_worst_sellers(con)
    chart_08_freight_share(con)
    chart_09_seasonality(con)
    chart_10_monthly_revenue(con)
    summary(con)
    print(f"\nCharts written to {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
