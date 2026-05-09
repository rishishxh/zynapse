"""
API Routes — QUANT COMMERCE (MongoDB-backed)
Compatible with Python 3.7+

Endpoints:
  GET  /api/products            paginated list, search, category, sort, filters
  GET  /api/products/{asin}     single product by ASIN
  GET  /api/categories          all category names
  GET  /api/recommended         top best-sellers by demand_score
  GET  /api/demand/{asin}       AI demand prediction
  GET  /api/stats               dataset summary
  GET  /api/trends              demand trends by category
  GET  /api/predictions         bulk AI predictions (top N products)
  GET  /api/inventory           inventory overview with reorder alerts
  POST /api/predict             Random Forest demand prediction (custom input)
  GET  /api/images/{asin}       serve product image from GridFS
  POST /api/orders              save an order
  GET  /api/orders              get user's orders
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.mongo_loader import get_df
from app.core.rf_model import predict_demand, get_model, get_model_stats
from app.core.database import get_gridfs, orders_col
from datetime import datetime
import io

router = APIRouter(prefix="/api", tags=["products"])

_SORT = {
    "price_asc":    ("price",             True),
    "price_desc":   ("price",             False),
    "rating_desc":  ("stars",             False),
    "demand_desc":  ("demand_score",      False),
    "popular_desc": ("boughtInLastMonth",  False),
}


@router.get("/products")
async def list_products(
    page:       int   = Query(default=1,    ge=1),
    limit:      int   = Query(default=20,   ge=1, le=10000),
    search:     str   = Query(default=None),
    category:   str   = Query(default=None),
    sort_by:    str   = Query(default=None),
    min_price:  float = Query(default=None, ge=0),
    max_price:  float = Query(default=None, ge=0),
    min_stars:  float = Query(default=None, ge=0, le=5),
    bestseller: bool  = Query(default=None),
):
    import pandas as pd

    df = get_df()
    filtered = df

    if search:
        filtered = filtered[filtered["title"].str.contains(search, case=False, na=False)]
    if category:
        filtered = filtered[filtered["categoryName"] == category]
    if min_price is not None:
        filtered = filtered[filtered["price"] >= min_price]
    if max_price is not None:
        filtered = filtered[filtered["price"] <= max_price]
    if min_stars is not None:
        filtered = filtered[filtered["stars"] >= min_stars]
    if bestseller is not None:
        filtered = filtered[filtered["isBestSeller"] == bestseller]
    if sort_by and sort_by in _SORT:
        col, asc = _SORT[sort_by]
        filtered = filtered.sort_values(by=col, ascending=asc, na_position="last")

    # ── merge user-added products ──────────────────────────────────────────
    user_rows = get_all_user_products()
    user_records = []
    for p in user_rows:
        try:
            price = float(p.get("price", 0))
            stars = float(p.get("stars", 0))
            bought = int(p.get("boughtInLastMonth", 0))
            bs = str(p.get("isBestSeller", "FALSE")).upper() == "TRUE"
            title = p.get("title", "")
            cat   = p.get("categoryName", "")
            img   = p.get("image_filename", "")
            asin  = int(p.get("asin", 0)) if p.get("asin") else 0

            # apply same filters
            if search and search.lower() not in title.lower():
                continue
            if category and cat != category:
                continue
            if min_price is not None and price < min_price:
                continue
            if max_price is not None and price > max_price:
                continue
            if min_stars is not None and stars < min_stars:
                continue
            if bestseller is not None and bs != bestseller:
                continue

            user_records.append({
                "asin":              asin,
                "title":             title,
                "categoryName":      cat,
                "price":             price,
                "stars":             stars,
                "boughtInLastMonth": bought,
                "isBestSeller":      bs,
                "demand_score":      round(stars * 0.25 * 25 + min(bought / 10, 25) + (25 if bs else 0), 2),
                "is_user_product":   True,
                "image_filename":    img,
                "owner_email":       p.get("owner_email", ""),
                "description":       p.get("description", ""),
                "added_on":          p.get("added_on", ""),
            })
        except Exception:
            continue

    # combine: user products first (they're newest), then dataset products
    dataset_records = filtered.to_dict(orient="records")
    for r in dataset_records:
        r["is_user_product"] = False
        r["image_filename"]  = ""

    combined = user_records + dataset_records

    total = len(combined)
    start = (page - 1) * limit
    page_slice = combined[start: start + limit]

    return {
        "total": total,
        "page":  page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
        "data":  page_slice,
    }


@router.get("/products/{asin}")
async def get_product(asin: int):
    # check user products first (they have real asins > max dataset asin)
    all_up = get_all_user_products()
    for p in all_up:
        try:
            if int(p.get("asin", -1)) == asin:
                price  = float(p.get("price", 0))
                stars  = float(p.get("stars", 0))
                bought = int(p.get("boughtInLastMonth", 0))
                bs     = str(p.get("isBestSeller", "FALSE")).upper() == "TRUE"
                return {
                    "asin":              asin,
                    "title":             p.get("title", ""),
                    "categoryName":      p.get("categoryName", ""),
                    "price":             price,
                    "stars":             stars,
                    "boughtInLastMonth": bought,
                    "isBestSeller":      bs,
                    "demand_score":      round(stars * 0.25 * 25 + min(bought / 10, 25) + (25 if bs else 0), 2),
                    "is_user_product":   True,
                    "image_filename":    p.get("image_filename", ""),
                    "owner_email":       p.get("owner_email", ""),
                    "description":       p.get("description", ""),
                    "added_on":          p.get("added_on", ""),
                }
        except Exception:
            continue

    # fall back to dataset
    df = get_df()
    match = df[df["asin"] == asin]
    if match.empty:
        raise HTTPException(status_code=404, detail="Product {} not found".format(asin))
    row = match.iloc[0].to_dict()
    row["is_user_product"] = False
    row["image_filename"]  = ""
    return row


@router.get("/categories")
async def list_categories():
    df = get_df()
    cats = sorted(df["categoryName"].dropna().unique().tolist())
    return {"count": len(cats), "data": cats}


@router.get("/recommended")
async def recommended_products(limit: int = Query(default=10, ge=1, le=50)):
    df = get_df()
    best = df[df["isBestSeller"] == True]
    if best.empty:
        best = df
    top = best.nlargest(limit, "demand_score")
    return {"count": len(top), "data": top.to_dict(orient="records")}


@router.get("/demand/{asin}")
async def demand_prediction(asin: int):
    # check user products first
    all_up = get_all_user_products()
    for p in all_up:
        try:
            if int(p.get("asin", -1)) == asin:
                price  = float(p.get("price", 0))
                stars  = float(p.get("stars", 0))
                bought = int(p.get("boughtInLastMonth", 0))
                bs     = str(p.get("isBestSeller", "FALSE")).upper() == "TRUE"
                # compute equal-weight demand score inline
                from app.core.mongo_loader import get_df as _gdf
                _df = _gdf()
                bmax = float(_df["boughtInLastMonth"].max())
                pmin = float(_df["price"].min())
                pmax = float(_df["price"].max())
                sn = ((stars - 1.0) / 4.0) * 100.0
                bn = (bought / bmax) * 100.0 if bmax else 0.0
                bsn = 100.0 if bs else 0.0
                prn = (1.0 - (price - pmin) / (pmax - pmin)) * 100.0 if pmax > pmin else 50.0
                score = round((sn + bn + bsn + prn) * 0.25, 2)
                level = "High" if score >= 60 else ("Medium" if score >= 35 else "Low")
                conf  = round(min(95.0, (score / 100.0) * 95), 1)
                return {
                    "asin":              asin,
                    "title":             p.get("title", ""),
                    "demand_level":      level,
                    "demand_score":      score,
                    "confidence_score":  conf,
                    "stars":             stars,
                    "bought_last_month": bought,
                    "is_user_product":   True,
                }
        except Exception:
            continue

    # fall back to dataset
    df = get_df()
    match = df[df["asin"] == asin]
    if match.empty:
        raise HTTPException(status_code=404, detail="Product {} not found".format(asin))

    row   = match.iloc[0]
    score = float(row["demand_score"])
    level = "High" if score >= 60 else ("Medium" if score >= 35 else "Low")
    conf  = round(min(95.0, (score / 100.0) * 95), 1)

    return {
        "asin":              asin,
        "title":             row["title"],
        "demand_level":      level,
        "demand_score":      round(score, 2),
        "confidence_score":  conf,
        "stars":             float(row["stars"]),
        "bought_last_month": int(row["boughtInLastMonth"]),
        "is_user_product":   False,
    }


@router.get("/stats")
async def dataset_stats():
    df = get_df()
    return {
        "total_products":   len(df),
        "total_categories": int(df["categoryName"].nunique()),
        "best_sellers":     int(df["isBestSeller"].sum()),
        "avg_price":        round(float(df["price"].mean()), 2),
        "avg_stars":        round(float(df["stars"].mean()), 2),
        "avg_demand_score": round(float(df["demand_score"].mean()), 2),
        "price_min":        round(float(df["price"].min()), 2),
        "price_max":        round(float(df["price"].max()), 2),
    }


# ── /api/trends ───────────────────────────────────────────────────────────────
# Returns demand trend data per category: avg demand score, avg stars,
# total units bought, product count, best-seller count.
# Used by demand_trends.html
@router.get("/trends")
async def demand_trends(top: int = Query(default=20, ge=1, le=126)):
    df = get_df()

    grp = df.groupby("categoryName").agg(
        product_count    = ("asin",             "count"),
        avg_demand_score = ("demand_score",     "mean"),
        avg_stars        = ("stars",            "mean"),
        total_bought     = ("boughtInLastMonth", "sum"),
        best_sellers     = ("isBestSeller",      "sum"),
    ).reset_index()

    grp = grp.sort_values("avg_demand_score", ascending=False).head(top)

    # Trend label based on avg_demand_score distribution
    def trend_label(score):
        if score >= 60:
            return "Surging"
        elif score >= 50:
            return "Rising"
        elif score >= 35:
            return "Stable"
        else:
            return "Declining"

    result = []
    for _, row in grp.iterrows():
        result.append({
            "category":        row["categoryName"],
            "product_count":   int(row["product_count"]),
            "avg_demand_score": round(float(row["avg_demand_score"]), 2),
            "avg_stars":       round(float(row["avg_stars"]), 2),
            "total_bought":    int(row["total_bought"]),
            "best_sellers":    int(row["best_sellers"]),
            "trend":           trend_label(float(row["avg_demand_score"])),
        })

    return {"count": len(result), "data": result}


# ── /api/predictions ──────────────────────────────────────────────────────────
# Bulk AI demand predictions for top N products.
# Scores every product using demand_score formula and returns ranked list.
# Used by predictions.html
@router.get("/predictions")
async def bulk_predictions(
    limit:    int = Query(default=50,  ge=1, le=200),
    category: str = Query(default=None),
    level:    str = Query(default=None, description="High | Medium | Low"),
):
    df = get_df()
    filtered = df

    if category:
        filtered = filtered[filtered["categoryName"] == category]

    # Sort by demand_score descending
    filtered = filtered.sort_values("demand_score", ascending=False).head(limit)

    def classify(score):
        if score >= 60:
            return "High"
        elif score >= 35:
            return "Medium"
        return "Low"

    def confidence(score):
        return round(min(95.0, (score / 100.0) * 95), 1)

    result = []
    for _, row in filtered.iterrows():
        score = float(row["demand_score"])
        lvl   = classify(score)
        if level and lvl != level:
            continue
        result.append({
            "asin":           int(row["asin"]),
            "title":          row["title"],
            "category":       row["categoryName"],
            "price":          round(float(row["price"]), 2),
            "stars":          float(row["stars"]),
            "bought_last_month": int(row["boughtInLastMonth"]),
            "demand_score":   round(score, 2),
            "demand_level":   lvl,
            "confidence":     confidence(score),
            "is_best_seller": bool(row["isBestSeller"]),
        })

    # Distribution summary
    all_levels = [r["demand_level"] for r in result]
    summary = {
        "High":   all_levels.count("High"),
        "Medium": all_levels.count("Medium"),
        "Low":    all_levels.count("Low"),
    }

    return {"count": len(result), "summary": summary, "data": result}


# ── /api/inventory ────────────────────────────────────────────────────────────
# Inventory overview: category breakdown, reorder alerts (low demand + low bought),
# top stock movers, overall health metrics.
# Used by inventory.html
@router.get("/inventory")
async def inventory_overview(limit: int = Query(default=30, ge=1, le=100)):
    df = get_df()

    # Overall metrics
    total        = len(df)
    best_sellers = int(df["isBestSeller"].sum())
    avg_score    = round(float(df["demand_score"].mean()), 2)

    # Reorder alerts: demand_score < 35 (Low) AND boughtInLastMonth < 100
    alerts_df = df[(df["demand_score"] < 35) & (df["boughtInLastMonth"] < 100)]
    alerts_df = alerts_df.sort_values("demand_score").head(limit)

    alerts = []
    for _, row in alerts_df.iterrows():
        alerts.append({
            "asin":           int(row["asin"]),
            "title":          row["title"],
            "category":       row["categoryName"],
            "price":          round(float(row["price"]), 2),
            "stars":          float(row["stars"]),
            "bought_last_month": int(row["boughtInLastMonth"]),
            "demand_score":   round(float(row["demand_score"]), 2),
            "demand_level":   "Low",
            "alert":          "Reorder Recommended",
        })

    # Top movers: highest boughtInLastMonth
    movers_df = df.nlargest(limit, "boughtInLastMonth")
    movers = []
    for _, row in movers_df.iterrows():
        score = float(row["demand_score"])
        movers.append({
            "asin":           int(row["asin"]),
            "title":          row["title"],
            "category":       row["categoryName"],
            "price":          round(float(row["price"]), 2),
            "stars":          float(row["stars"]),
            "bought_last_month": int(row["boughtInLastMonth"]),
            "demand_score":   round(score, 2),
            "demand_level":   "High" if score >= 60 else ("Medium" if score >= 35 else "Low"),
            "is_best_seller": bool(row["isBestSeller"]),
        })

    # Category breakdown
    cat_grp = df.groupby("categoryName").agg(
        count        = ("asin",             "count"),
        avg_score    = ("demand_score",     "mean"),
        total_bought = ("boughtInLastMonth", "sum"),
    ).reset_index().sort_values("total_bought", ascending=False).head(15)

    categories = []
    for _, row in cat_grp.iterrows():
        categories.append({
            "category":    row["categoryName"],
            "count":       int(row["count"]),
            "avg_score":   round(float(row["avg_score"]), 2),
            "total_bought": int(row["total_bought"]),
        })

    return {
        "metrics": {
            "total_products": total,
            "best_sellers":   best_sellers,
            "avg_demand_score": avg_score,
            "reorder_alerts": len(alerts),
            "high_demand":    int((df["demand_score"] >= 60).sum()),
            "medium_demand":  int(((df["demand_score"] >= 35) & (df["demand_score"] < 60)).sum()),
            "low_demand":     int((df["demand_score"] < 35).sum()),
        },
        "reorder_alerts": alerts,
        "top_movers":     movers,
        "categories":     categories,
    }


# ── /api/predict ──────────────────────────────────────────────────────────────
# Random Forest demand prediction from user-supplied product features.
# Used by predict.html
class PredictRequest(BaseModel):
    price:             float
    stars:             float
    boughtInLastMonth: int
    isBestSeller:      bool  = False
    categoryName:      str   = ""


@router.post("/predict")
async def rf_predict(body: PredictRequest):
    if body.price <= 0:
        raise HTTPException(status_code=422, detail="price must be > 0")
    if not (1.0 <= body.stars <= 5.0):
        raise HTTPException(status_code=422, detail="stars must be between 1 and 5")
    if body.boughtInLastMonth < 0:
        raise HTTPException(status_code=422, detail="boughtInLastMonth must be >= 0")

    result = predict_demand(
        price             = body.price,
        stars             = body.stars,
        bought_last_month = body.boughtInLastMonth,
        is_best_seller    = body.isBestSeller,
        category_name     = body.categoryName,
    )
    return result


# -- /api/predict/warmup --
@router.get("/predict/warmup")
async def warmup_model():
    """Pre-train the RF model so first prediction is instant."""
    get_model()
    return {"status": "ready"}


# -- /api/model-stats --
@router.get("/model-stats")
async def model_stats():
    """Returns RF train/test split sizes and accuracy metrics."""
    return get_model_stats()


# ── /api/category-analysis ────────────────────────────────────────────────────
# Full deep-dive for one category: KMeans segments, top/bottom products,
# price buckets, stars distribution, scatter data, bought chart.
# Used by category_analysis.html
@router.get("/category-analysis")
async def category_analysis(category: str = Query(...)):
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    df = get_df()
    cat_df = df[df["categoryName"] == category].copy()

    if cat_df.empty:
        raise HTTPException(status_code=404, detail="Category '{}' not found".format(category))

    # ── stats ──
    stats = {
        "product_count":       int(len(cat_df)),
        "avg_price":           round(float(cat_df["price"].mean()), 2),
        "avg_stars":           round(float(cat_df["stars"].mean()), 2),
        "avg_demand_score":    round(float(cat_df["demand_score"].mean()), 2),
        "total_bought":        int(cat_df["boughtInLastMonth"].sum()),
        "best_sellers":        int(cat_df["isBestSeller"].sum()),
        "price_min":           round(float(cat_df["price"].min()), 2),
        "price_max":           round(float(cat_df["price"].max()), 2),
        "max_demand_score":    round(float(cat_df["demand_score"].max()), 2),
        "high_demand_count":   int((cat_df["demand_score"] >= 60).sum()),
        "medium_demand_count": int(((cat_df["demand_score"] >= 35) & (cat_df["demand_score"] < 60)).sum()),
        "low_demand_count":    int((cat_df["demand_score"] < 35).sum()),
    }

    # ── KMeans clustering on price + demand_score ──
    features  = cat_df[["price", "demand_score"]].values.astype(float)
    n_clusters = min(3, len(cat_df))
    scaler    = StandardScaler()
    X_scaled  = scaler.fit_transform(features)
    km        = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels    = km.fit_predict(X_scaled)
    cat_df["cluster"] = labels

    cluster_scores = cat_df.groupby("cluster")["demand_score"].mean().sort_values(ascending=False)
    label_map = {cid: ["Hot","Warm","Cold"][i] for i, cid in enumerate(cluster_scores.index)}
    cat_df["segment"] = cat_df["cluster"].map(label_map)

    cluster_summary = []
    for seg in ["Hot", "Warm", "Cold"]:
        s = cat_df[cat_df["segment"] == seg]
        if s.empty: continue
        cluster_summary.append({
            "segment":          seg,
            "count":            int(len(s)),
            "avg_demand_score": round(float(s["demand_score"].mean()), 2),
            "avg_price":        round(float(s["price"].mean()), 2),
            "avg_stars":        round(float(s["stars"].mean()), 2),
            "total_bought":     int(s["boughtInLastMonth"].sum()),
            "best_sellers":     int(s["isBestSeller"].sum()),
        })

    def classify(score):
        return "High" if score >= 60 else ("Medium" if score >= 35 else "Low")

    def conf(score):
        return round(min(95.0, (score / 200.0) * 95), 1)

    # ── Top 10 products ──
    top_products = []
    for _, row in cat_df.nlargest(10, "demand_score").iterrows():
        score = float(row["demand_score"])
        top_products.append({
            "asin":              int(row["asin"]),
            "title":             row["title"],
            "price":             round(float(row["price"]), 2),
            "stars":             float(row["stars"]),
            "bought_last_month": int(row["boughtInLastMonth"]),
            "demand_score":      round(score, 2),
            "demand_level":      classify(score),
            "confidence":        conf(score),
            "is_best_seller":    bool(row["isBestSeller"]),
            "segment":           str(row["segment"]),
        })

    # ── Bottom 5 (reorder candidates) ──
    bottom_products = []
    for _, row in cat_df.nsmallest(5, "demand_score").iterrows():
        score = float(row["demand_score"])
        bottom_products.append({
            "asin":              int(row["asin"]),
            "title":             row["title"],
            "price":             round(float(row["price"]), 2),
            "stars":             float(row["stars"]),
            "bought_last_month": int(row["boughtInLastMonth"]),
            "demand_score":      round(score, 2),
            "demand_level":      classify(score),
            "segment":           str(row["segment"]),
        })

    # ── Price distribution (5 buckets) ──
    pmin, pmax = float(cat_df["price"].min()), float(cat_df["price"].max())
    bsize = (pmax - pmin) / 5 if pmax > pmin else 1
    price_buckets = []
    for i in range(5):
        lo, hi = pmin + i * bsize, pmin + (i + 1) * bsize
        price_buckets.append({
            "label": "₹{}-{}".format(int(lo), int(hi)),
            "count": int(((cat_df["price"] >= lo) & (cat_df["price"] < hi)).sum()),
        })

    # ── Stars distribution ──
    stars_dist = [
        {"stars": s, "count": int(((cat_df["stars"] >= s) & (cat_df["stars"] < s + 1)).sum())}
        for s in [1, 2, 3, 4, 5]
    ]

    # ── Scatter (capped 300) ──
    scatter = []
    for _, row in cat_df.sample(min(300, len(cat_df)), random_state=42).iterrows():
        scatter.append({
            "x": round(float(row["price"]), 2),
            "y": round(float(row["demand_score"]), 2),
            "segment": str(row["segment"]),
            "title": row["title"][:45],
        })

    # ── Top 10 by units bought ──
    bought_chart = []
    for _, row in cat_df.nlargest(10, "boughtInLastMonth").iterrows():
        bought_chart.append({
            "title":  row["title"][:30],
            "bought": int(row["boughtInLastMonth"]),
            "score":  round(float(row["demand_score"]), 2),
        })

    return {
        "category":        category,
        "stats":           stats,
        "cluster_summary": cluster_summary,
        "top_products":    top_products,
        "bottom_products": bottom_products,
        "price_buckets":   price_buckets,
        "stars_dist":      stars_dist,
        "scatter":         scatter,
        "bought_chart":    bought_chart,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AUTH & USER PRODUCT ENDPOINTS
# POST /api/auth/register       create account
# POST /api/auth/login          sign in
# GET  /api/auth/me             get profile (requires ?email=)
# PUT  /api/auth/me             update profile
# GET  /api/user/products       list user's added products
# POST /api/user/products       add a product
# DELETE /api/user/products/{id} delete a product
# ══════════════════════════════════════════════════════════════════════════════
from app.core.mongo_user_store import (
    register_user, login_user, get_user, update_user, safe_user,
    add_user_product, get_user_products, delete_user_product,
    get_all_user_products
)


class RegisterBody(BaseModel):
    email:      str
    password:   str
    name:       str
    phone:      str = ""
    department: str = ""
    city:       str = ""
    role:       str = "Analyst"


class LoginBody(BaseModel):
    email:    str
    password: str


class UpdateProfileBody(BaseModel):
    email:        str
    name:         str  = ""
    phone:        str  = ""
    department:   str  = ""
    city:         str  = ""
    role:         str  = ""
    new_password: str  = ""


class AddProductBody(BaseModel):
    owner_email:      str
    title:            str
    categoryName:     str
    price:            float
    stars:            float
    boughtInLastMonth: int  = 0
    isBestSeller:     bool  = False
    description:      str   = ""


@router.post("/auth/register")
async def api_register(body: RegisterBody):
    if not body.email or not body.password or not body.name:
        raise HTTPException(status_code=422, detail="email, password and name are required")
    user, err = register_user(
        body.email, body.password, body.name,
        body.phone, body.department, body.city, body.role
    )
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"success": True, "user": safe_user(user)}


@router.post("/auth/login")
async def api_login(body: LoginBody):
    user, err = login_user(body.email, body.password)
    if err:
        raise HTTPException(status_code=401, detail=err)
    return {"success": True, "user": safe_user(user)}


@router.get("/auth/me")
async def api_me(email: str = Query(...)):
    user = get_user(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return safe_user(user)


@router.put("/auth/me")
async def api_update_profile(body: UpdateProfileBody):
    updates = {k: v for k, v in body.dict().items() if v}
    user, err = update_user(body.email, updates)
    if err:
        raise HTTPException(status_code=404, detail=err)
    return {"success": True, "user": safe_user(user)}


@router.get("/user/products")
async def api_user_products(email: str = Query(...)):
    return {"data": get_user_products(email)}


@router.post("/user/products")
async def api_add_product(body: AddProductBody):
    if not body.title or not body.categoryName or body.price <= 0:
        raise HTTPException(status_code=422, detail="title, category and price > 0 required")
    if not (1.0 <= body.stars <= 5.0):
        raise HTTPException(status_code=422, detail="stars must be 1-5")
    p = add_user_product(
        body.owner_email, body.title, body.categoryName,
        body.price, body.stars, body.boughtInLastMonth,
        body.isBestSeller, body.description, ""
    )
    return {"success": True, "product": p}


# ── /api/user/products/upload-image ──────────────────────────────────────────
@router.post("/user/products/upload-image")
async def upload_product_image(
    product_id: int = Query(...),
    email:      str = Query(...),
):
    """Handled via multipart — see main.py for the actual upload route."""
    return {"detail": "Use POST /upload-product-image instead"}


@router.delete("/user/products/{product_id}")
async def api_delete_product(product_id: int, email: str = Query(...)):
    ok = delete_user_product(email, product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"success": True}


# ── /api/dataset/build ────────────────────────────────────────────────────────
# Builds/rebuilds products_with_demand.csv (balanced, with demand scores).
# GET  returns stats about the current file.
# POST rebuilds it from scratch.
@router.get("/dataset/info")
async def dataset_info():
    """Return stats about the current balanced training dataset."""
    import os
    from app.core.dataset_builder import OUT_CSV
    if not os.path.exists(OUT_CSV):
        return {"exists": False, "message": "Not built yet. POST /api/dataset/build to create it."}
    import pandas as pd
    df = pd.read_csv(OUT_CSV, encoding="utf-8")
    dist = df["demand_level"].value_counts().to_dict()
    return {
        "exists":       True,
        "total_rows":   len(df),
        "distribution": dist,
        "columns":      list(df.columns),
        "file":         "data/products_with_demand.csv",
    }


@router.post("/dataset/build")
async def build_dataset_endpoint():
    """Rebuild the balanced training dataset CSV."""
    from app.core.dataset_builder import build_dataset
    df = build_dataset(save=True)
    dist = df["demand_level"].value_counts().to_dict()
    return {
        "success":      True,
        "total_rows":   len(df),
        "distribution": dist,
        "file":         "data/products_with_demand.csv",
        "message":      "Balanced dataset built successfully.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# GRIDFS IMAGE ENDPOINT
# Serves product images directly from MongoDB GridFS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/images/{asin:path}")
async def get_product_image(asin: str):
    """Serve a product image from GridFS by ASIN. Accepts /api/images/123 or /api/images/123.jpg"""
    fs = get_gridfs()
    # Strip .jpg extension if present so both formats work
    clean_asin = asin.replace(".jpg", "").replace(".jpeg", "").replace(".png", "")
    filename = f"{clean_asin}.jpg"

    try:
        grid_file = fs.find_one({"filename": filename})
        if grid_file is None:
            raise HTTPException(status_code=404, detail="Image not found")

        image_data = grid_file.read()
        return StreamingResponse(
            io.BytesIO(image_data),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ORDERS ENDPOINTS
# POST /api/orders    — save a new order
# GET  /api/orders    — get orders for a user
# ══════════════════════════════════════════════════════════════════════════════

class OrderBody(BaseModel):
    user_email:      str
    items:           list  # list of asin integers
    subtotal:        float
    shipping:        float
    total:           float
    payment_method:  str
    delivery_speed:  str
    address:         dict  # {name, address, city, pin, phone}


@router.post("/orders")
async def create_order(body: OrderBody):
    """Save a new order to MongoDB."""
    import random
    order_id = f"ZYN-{random.randint(100000, 999999)}"

    doc = {
        "order_id":        order_id,
        "user_email":      body.user_email.lower(),
        "items":           body.items,
        "subtotal":        body.subtotal,
        "shipping":        body.shipping,
        "total":           body.total,
        "payment_method":  body.payment_method,
        "delivery_speed":  body.delivery_speed,
        "address":         body.address,
        "status":          "confirmed",
        "created_at":      datetime.now().isoformat(),
    }
    orders_col().insert_one(doc)
    return {"success": True, "order_id": order_id}


@router.get("/orders")
async def get_orders(email: str = Query(...)):
    """Get all orders for a user."""
    orders = list(orders_col().find(
        {"user_email": email.lower()},
        {"_id": 0}
    ).sort("created_at", -1))
    return {"data": orders, "count": len(orders)}


# ══════════════════════════════════════════════════════════════════════════════
# MONGODB STATUS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/db/status")
async def db_status():
    """Return MongoDB connection status and collection counts."""
    from app.core.database import get_db, ping
    if not ping():
        return {"connected": False}
    db = get_db()
    return {
        "connected":    True,
        "database":     db.name,
        "products":     db["products"].count_documents({}),
        "users":        db["users"].count_documents({}),
        "user_products": db["user_products"].count_documents({}),
        "orders":       db["orders"].count_documents({}),
        "gridfs_files": db["fs.files"].count_documents({}),
    }
