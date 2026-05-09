"""
Data Loader — ZYNAPSE
Single-load CSV with dtype optimisation and pre-computed demand_score.
Compatible with Python 3.7+
"""
import pandas as pd
import os
from typing import Optional

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRODUCTS_CSV = os.path.join(BASE_DIR, "data", "products.csv")

_df = None  # type: Optional[pd.DataFrame]

_DTYPES = {
    "asin":              "int64",
    "price":             "float32",
    "stars":             "float32",
    "boughtInLastMonth": "int32",
    "isBestSeller":      "bool",
}


def load_data():
    # type: () -> None
    """Load products.csv once at startup. Computes equal-weight demand_score."""
    global _df
    if _df is not None:
        return

    print("[Loader] Reading products.csv ...")
    _df = pd.read_csv(PRODUCTS_CSV, encoding="utf-8", dtype=_DTYPES)

    # ── Equal-Weight Demand Score ──────────────────────────────────────────
    # All 4 factors contribute equally (25% each).
    # Each factor is min-max normalised to [0, 100] before combining
    # so no single factor dominates due to scale differences.
    #
    #   1. stars            (quality signal)      weight = 25%
    #   2. boughtInLastMonth (popularity signal)   weight = 25%
    #   3. isBestSeller     (market validation)    weight = 25%
    #   4. price (inverse)  (affordability signal) weight = 25%

    # stars: 1-5 -> 0-100
    stars_norm = ((_df["stars"] - 1.0) / 4.0) * 100.0

    # boughtInLastMonth: 0-max -> 0-100
    bought_max  = _df["boughtInLastMonth"].max()
    bought_norm = (_df["boughtInLastMonth"] / bought_max) * 100.0

    # isBestSeller: bool -> 0 or 100
    bs_norm = _df["isBestSeller"].astype(float) * 100.0

    # price: inverse normalise (cheaper = higher demand contribution)
    price_min  = _df["price"].min()
    price_max  = _df["price"].max()
    price_norm = (1.0 - (_df["price"] - price_min) / (price_max - price_min)) * 100.0

    # Equal composite score — each factor 25%
    _df["demand_score"] = (
        stars_norm  * 0.25 +
        bought_norm * 0.25 +
        bs_norm     * 0.25 +
        price_norm  * 0.25
    ).round(2)

    # Store normalised columns for use in model training
    _df["stars_norm"]  = stars_norm.round(4)
    _df["bought_norm"] = bought_norm.round(4)
    _df["bs_norm"]     = bs_norm.round(4)
    _df["price_norm"]  = price_norm.round(4)

    print("[Loader] {} rows loaded. demand_score range: {:.1f} - {:.1f}".format(
        len(_df), _df["demand_score"].min(), _df["demand_score"].max()
    ))


def get_df():
    # type: () -> pd.DataFrame
    if _df is None:
        raise RuntimeError("Data not loaded — call load_data() first.")
    return _df
