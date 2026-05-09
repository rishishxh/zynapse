"""
MongoDB Connection Manager — ZYNAPSE
Database: zynapse
Collections: products, users, user_products, orders, cart
GridFS: product images (fs.files + fs.chunks)
"""
import os
from pymongo import MongoClient
import gridfs

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB", "zynapse")

_client = None
_db     = None
_gridfs = None


def get_client():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_db():
    global _db
    if _db is None:
        _db = get_client()[DB_NAME]
    return _db


def get_gridfs():
    global _gridfs
    if _gridfs is None:
        _gridfs = gridfs.GridFS(get_db())
    return _gridfs


# ── Collection shortcuts ──
def products_col():
    return get_db()["products"]

def users_col():
    return get_db()["users"]

def user_products_col():
    return get_db()["user_products"]

def orders_col():
    return get_db()["orders"]

def cart_col():
    return get_db()["cart"]


def ensure_indexes():
    """Create indexes for fast queries."""
    products_col().create_index("asin", unique=True)
    products_col().create_index("categoryName")
    products_col().create_index("demand_score")
    products_col().create_index("price")
    products_col().create_index("stars")
    products_col().create_index([("title", "text")])

    users_col().create_index("email", unique=True)

    user_products_col().create_index("asin", unique=True)
    user_products_col().create_index("owner_email")

    orders_col().create_index("user_email")
    orders_col().create_index("created_at")

    cart_col().create_index("user_email", unique=True)

    print("[MongoDB] Indexes created.")


def ping():
    """Test connectivity."""
    try:
        get_client().admin.command("ping")
        return True
    except Exception as e:
        print(f"[MongoDB] Connection failed: {e}")
        return False
