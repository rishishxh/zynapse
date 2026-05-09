"""
MongoDB Product Loader — ZYNAPSE
Replaces pandas CSV loader with MongoDB queries.
Provides get_df()-compatible interface for the transition.
"""
import pandas as pd
from app.core.database import products_col, get_db

_df = None


def load_data():
    """Load products from MongoDB into a pandas DataFrame (cached)."""
    global _df
    if _df is not None:
        return

    col = products_col()
    count = col.count_documents({})

    if count == 0:
        print("[MongoLoader] No products in MongoDB. Run migrate_to_mongo.py first!")
        print("[MongoLoader] Falling back to CSV loader...")
        from app.core.loader import load_data as csv_load
        csv_load()
        return

    print(f"[MongoLoader] Loading {count:,} products from MongoDB...")
    cursor = col.find({}, {"_id": 0})
    _df = pd.DataFrame(list(cursor))

    # Ensure correct dtypes
    _df["asin"] = _df["asin"].astype("int64")
    _df["price"] = _df["price"].astype("float32")
    _df["stars"] = _df["stars"].astype("float32")
    _df["boughtInLastMonth"] = _df["boughtInLastMonth"].astype("int32")

    print(f"[MongoLoader] ✅ {len(_df)} rows loaded from MongoDB. "
          f"demand_score range: {_df['demand_score'].min():.1f} - {_df['demand_score'].max():.1f}")


def get_df():
    """Return the cached DataFrame. Falls back to CSV if MongoDB is empty."""
    global _df
    if _df is None:
        # Try CSV fallback
        try:
            from app.core.loader import get_df as csv_get_df
            return csv_get_df()
        except RuntimeError:
            raise RuntimeError("Data not loaded — call load_data() first or run migrate_to_mongo.py")
    return _df
