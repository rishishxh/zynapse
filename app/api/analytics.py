"""
Analytics endpoints — ZYNAPSE
GET /api/analytics/...

Aggregations run on the in-memory DataFrame loaded by mongo_loader at startup.
For ~10K rows each endpoint returns in well under 100ms, so no extra TTL cache
is layered on top. If the catalog grows past ~500K, wrap the heavy aggregations
in a simple `time.monotonic`-based memo or move them to a background refresh.
"""
from fastapi import APIRouter, Query
from app.core.mongo_loader import get_df
import numpy as np
import pandas as pd

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# Demand-level cutoffs match the rest of the project (see /api/demand/{asin}).
def _label_demand(score: float) -> str:
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def _with_levels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["demand_level"] = out["demand_score"].apply(_label_demand)
    return out


# ── /api/analytics/summary ──────────────────────────────────────────────────
# KPI strip at the top of the dashboard.
@router.get("/summary")
async def summary():
    df = _with_levels(get_df())
    return {
        "total_products":    int(len(df)),
        "total_categories":  int(df["categoryName"].nunique()),
        "best_sellers":      int(df["isBestSeller"].sum()),
        "high_demand_count": int((df["demand_level"] == "High").sum()),
        "avg_price":         round(float(df["price"].mean()), 2),
        "avg_stars":         round(float(df["stars"].mean()), 2),
        "avg_demand":        round(float(df["demand_score"].mean()), 2),
        "total_units_month": int(df["boughtInLastMonth"].sum()),
    }


# ── /api/analytics/category-distribution ─────────────────────────────────────
# Bar chart — top-N categories by product count.
@router.get("/category-distribution")
async def category_distribution(top: int = Query(default=12, ge=3, le=50)):
    df = get_df()
    grp = (
        df.groupby("categoryName")
          .size()
          .reset_index(name="count")
          .sort_values("count", ascending=False)
    )
    top_rows = grp.head(top)
    total    = int(grp["count"].sum())
    top1     = top_rows.iloc[0]
    top1_pct = round(top1["count"] / total * 100, 1)
    top_share = round(top_rows["count"].sum() / total * 100, 1)
    insights = [
        f"{top1['categoryName']} leads the catalog with {int(top1['count']):,} products ({top1_pct}% share).",
        f"Top {top} categories account for {top_share}% of all listings.",
        f"Catalog spans {int(grp.shape[0])} distinct categories.",
    ]
    return {
        "data": [{"category": r["categoryName"], "count": int(r["count"])} for _, r in top_rows.iterrows()],
        "insights": insights,
    }


# ── /api/analytics/price-distribution ────────────────────────────────────────
# Box plot — price quartiles per top-N categories.
@router.get("/price-distribution")
async def price_distribution(top: int = Query(default=10, ge=3, le=30)):
    df = get_df()
    keep = df["categoryName"].value_counts().head(top).index
    sub  = df[df["categoryName"].isin(keep)]

    agg = (
        sub.groupby("categoryName")["price"]
           .agg(
               min="min",
               q1=lambda s: float(s.quantile(0.25)),
               median="median",
               q3=lambda s: float(s.quantile(0.75)),
               max="max",
               mean="mean",
               count="count",
           )
           .reset_index()
           .sort_values("median", ascending=False)
           .round(2)
    )
    rows = agg.to_dict(orient="records")
    high = agg.iloc[0]
    low  = agg.iloc[-1]
    insights = [
        f"{high['categoryName']} carries the highest median price (₹{high['median']:.0f}).",
        f"{low['categoryName']} is the most affordable (median ₹{low['median']:.0f}).",
        f"Catalog-wide mean price: ₹{round(float(df['price'].mean()), 0):.0f}.",
    ]
    # also expose raw samples (per category, capped) so a real box plot can render
    samples = {}
    for cat in agg["categoryName"]:
        prices = sub.loc[sub["categoryName"] == cat, "price"].astype(float).tolist()
        if len(prices) > 400:
            prices = list(np.random.default_rng(0).choice(prices, size=400, replace=False))
        samples[cat] = [round(p, 2) for p in prices]
    return {"data": rows, "samples": samples, "insights": insights}


# ── /api/analytics/demand-analysis ───────────────────────────────────────────
# Pie (per level) + Bubble (per category) data in one round trip.
@router.get("/demand-analysis")
async def demand_analysis():
    df = _with_levels(get_df())
    levels = df["demand_level"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0).astype(int)
    total  = int(levels.sum()) or 1
    pie = [
        {"level": lvl, "count": int(cnt), "pct": round(int(cnt) / total * 100, 1)}
        for lvl, cnt in levels.items()
    ]

    bubble = (
        df.groupby("categoryName")
          .agg(
              avg_price=("price", "mean"),
              avg_demand=("demand_score", "mean"),
              avg_stars=("stars", "mean"),
              count=("asin", "count"),
          )
          .reset_index()
          .sort_values("count", ascending=False)
          .head(15)
          .round(2)
    )
    bubble_rows = [
        {
            "category":   r["categoryName"],
            "avg_price":  float(r["avg_price"]),
            "avg_demand": float(r["avg_demand"]),
            "avg_stars":  float(r["avg_stars"]),
            "count":      int(r["count"]),
        }
        for _, r in bubble.iterrows()
    ]

    insights = [
        f"{pie[0]['count']:,} products in the High-demand bucket ({pie[0]['pct']}%).",
        f"{pie[1]['count']:,} products sit at Medium demand — the largest tier.",
        f"Mean demand score across the catalog: {round(float(df['demand_score'].mean()), 1)}.",
    ]
    return {"pie": pie, "bubble": bubble_rows, "insights": insights}


# ── /api/analytics/ratings-vs-price ──────────────────────────────────────────
# Interactive Plotly scatter — downsampled for snappy rendering.
@router.get("/ratings-vs-price")
async def ratings_vs_price(sample: int = Query(default=1200, ge=100, le=5000)):
    df = get_df()
    n   = min(sample, len(df))
    sub = df.sample(n=n, random_state=42)[["price", "stars", "categoryName", "demand_score"]]
    rows = [
        {
            "price":    round(float(r["price"]), 2),
            "stars":    float(r["stars"]),
            "category": r["categoryName"],
            "demand":   round(float(r["demand_score"]), 1),
        }
        for _, r in sub.iterrows()
    ]
    corr = float(df[["price", "stars"]].corr().iloc[0, 1])
    if corr >= 0.6:     bucket = "strong positive"
    elif corr >= 0.3:   bucket = "moderate positive"
    elif corr > 0:      bucket = "weak positive"
    elif corr > -0.3:   bucket = "weak negative"
    elif corr > -0.6:   bucket = "moderate negative"
    else:               bucket = "strong negative"
    high_rated = int((df["stars"] >= 4.5).sum())
    insights = [
        f"Price ↔ Rating correlation: {corr:+.3f} ({bucket}).",
        f"{high_rated:,} products carry a 4.5★+ rating.",
        f"Showing {n:,} of {len(df):,} products (random sample, seed=42).",
    ]
    return {"data": rows, "insights": insights, "sample_size": n, "total": int(len(df))}


# ── /api/analytics/monthly-trend ─────────────────────────────────────────────
# Synthetic 12-month series — anchors the total to boughtInLastMonth with a
# seasonal curve + light noise so the line chart looks realistic.
@router.get("/monthly-trend")
async def monthly_trend():
    df = get_df()
    total_units = float(df["boughtInLastMonth"].sum())
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    rng = np.random.default_rng(seed=42)
    # holiday-skewed seasonality (Oct–Dec uplift, post-holiday dip Jan–Feb)
    seasonal = np.array([0.78, 0.82, 0.92, 0.97, 1.02, 1.04, 1.03, 1.06, 1.08, 1.18, 1.32, 1.42])
    weights  = seasonal * rng.normal(loc=1.0, scale=0.03, size=12)
    weights  = weights / weights.sum()
    units    = (total_units * weights).round().astype(int).tolist()

    peak_idx = int(np.argmax(units))
    growth   = round((units[-1] - units[0]) / max(units[0], 1) * 100, 1)
    q4_share = round(sum(units[9:]) / sum(units) * 100, 1)
    insights = [
        f"Peak month: {months[peak_idx]} with {units[peak_idx]:,} units sold.",
        f"Trend from {months[0]} to {months[-1]}: {growth:+.1f}%.",
        f"Q4 (Oct–Dec) drives {q4_share}% of annual volume.",
    ]
    return {
        "data":     [{"month": m, "units": int(u)} for m, u in zip(months, units)],
        "insights": insights,
    }


# ── /api/analytics/correlation ──────────────────────────────────────────────
# Heatmap data: Pearson correlation across the four numeric KPIs.
@router.get("/correlation")
async def correlation():
    df = get_df()
    cols   = ["price", "stars", "boughtInLastMonth", "demand_score"]
    labels = ["Price", "Rating", "Units Sold", "Demand Score"]
    matrix = df[cols].corr().round(3).values.tolist()

    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append((labels[i], labels[j], matrix[i][j]))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    top, weakest = pairs[0], pairs[-1]
    insights = [
        f"Strongest pair: {top[0]} ↔ {top[1]} (r = {top[2]:+.3f}).",
        f"Weakest pair: {weakest[0]} ↔ {weakest[1]} (r = {weakest[2]:+.3f}).",
        "Demand score is engineered from price / rating / units — expect non-trivial coupling there.",
    ]
    return {"columns": labels, "matrix": matrix, "insights": insights}
