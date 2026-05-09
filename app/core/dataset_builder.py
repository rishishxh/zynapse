"""
Dataset Builder -- QUANT COMMERCE
Generates data/products_with_demand.csv:
  - All dataset products + user-added products
  - Equal-weight demand_score (25% each factor)
  - demand_level label (High / Medium / Low)
  - Class-balanced via oversampling minority classes
  - Ready for model training / export

Output columns:
  asin, title, categoryName, price, stars, boughtInLastMonth,
  isBestSeller, demand_score, demand_level,
  stars_norm, bought_norm, bs_norm, price_norm, is_user_product
"""
import os
import pandas as pd
import numpy as np

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_CSV    = os.path.join(BASE_DIR, "data", "products_with_demand.csv")
USER_CSV   = os.path.join(BASE_DIR, "data", "user_products.csv")


def _label(score):
    if score >= 60:
        return "High"
    elif score >= 35:
        return "Medium"
    return "Low"


def build_dataset(save=True):
    """
    Build and return a balanced DataFrame with demand scores.
    Optionally saves to data/products_with_demand.csv.
    """
    from app.core.mongo_loader import get_df
    df = get_df().copy()

    # ── compute global normalisation stats from full dataset ──
    bought_max = float(df["boughtInLastMonth"].max())
    price_min  = float(df["price"].min())
    price_max  = float(df["price"].max())

    def _normalise(sub):
        sub = sub.copy()
        sub["stars_norm"]  = ((sub["stars"]  - 1.0) / 4.0) * 100.0
        sub["bought_norm"] = (sub["boughtInLastMonth"] / bought_max) * 100.0
        sub["bs_norm"]     = sub["isBestSeller"].astype(float) * 100.0
        sub["price_norm"]  = (1.0 - (sub["price"] - price_min) / (price_max - price_min)) * 100.0
        sub["demand_score"] = (
            sub["stars_norm"]  * 0.25 +
            sub["bought_norm"] * 0.25 +
            sub["bs_norm"]     * 0.25 +
            sub["price_norm"]  * 0.25
        ).round(2)
        sub["demand_level"]    = sub["demand_score"].apply(_label)
        sub["is_user_product"] = False
        return sub

    df = _normalise(df)

    # ── append user-added products ──
    if os.path.exists(USER_CSV):
        try:
            udf = pd.read_csv(USER_CSV, encoding="utf-8")
            udf = udf[udf["asin"].notna()].copy()
            udf["asin"]              = udf["asin"].astype(int)
            udf["price"]             = udf["price"].astype(float)
            udf["stars"]             = udf["stars"].astype(float)
            udf["boughtInLastMonth"] = udf["boughtInLastMonth"].fillna(0).astype(int)
            udf["isBestSeller"]      = udf["isBestSeller"].astype(str).str.upper() == "TRUE"
            udf = _normalise(udf)
            udf["is_user_product"] = True
            # keep only columns present in main df
            common = [c for c in df.columns if c in udf.columns]
            df = pd.concat([df, udf[common]], ignore_index=True)
            print("[Builder] Added {} user products.".format(len(udf)))
        except Exception as e:
            print("[Builder] Warning: could not load user products:", e)

    # ── class distribution before balancing ──
    dist = df["demand_level"].value_counts()
    print("[Builder] Before balancing:", dist.to_dict())

    # ── balance classes via oversampling minority to match majority ──
    max_count = int(dist.max())
    balanced_parts = []
    for level in ["High", "Medium", "Low"]:
        part = df[df["demand_level"] == level]
        if len(part) == 0:
            continue
        if len(part) < max_count:
            # oversample with replacement
            extra = part.sample(max_count - len(part), replace=True, random_state=42)
            part  = pd.concat([part, extra], ignore_index=True)
        balanced_parts.append(part)

    balanced = pd.concat(balanced_parts, ignore_index=True)
    # shuffle
    balanced = balanced.sample(frac=1, random_state=42).reset_index(drop=True)

    dist2 = balanced["demand_level"].value_counts()
    print("[Builder] After balancing: ", dist2.to_dict())
    print("[Builder] Total rows: {}".format(len(balanced)))

    # ── select output columns ──
    out_cols = [
        "asin", "title", "categoryName", "price", "stars",
        "boughtInLastMonth", "isBestSeller", "demand_score", "demand_level",
        "stars_norm", "bought_norm", "bs_norm", "price_norm", "is_user_product"
    ]
    out_cols = [c for c in out_cols if c in balanced.columns]
    result = balanced[out_cols]

    if save:
        result.to_csv(OUT_CSV, index=False, encoding="utf-8")
        print("[Builder] Saved to", OUT_CSV)

    return result


def get_balanced_df():
    """Return balanced dataset, building it if not already on disk."""
    if not os.path.exists(OUT_CSV):
        return build_dataset(save=True)
    return pd.read_csv(OUT_CSV, encoding="utf-8")
