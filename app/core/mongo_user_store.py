"""
MongoDB User Store — ZYNAPSE
Replaces CSV-backed user_store.py with MongoDB collections.
"""
import hashlib
from datetime import datetime
from app.core.database import users_col, user_products_col, products_col


def _hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ── Users ──────────────────────────────────────────────────────────────────

def get_user(email):
    return users_col().find_one({"email": email.lower()}, {"_id": 0})


def register_user(email, password, name, phone="", department="", city="", role="Analyst"):
    if get_user(email):
        return None, "Email already registered"
    doc = {
        "email":         email.lower(),
        "password_hash": _hash(password),
        "name":          name,
        "phone":         phone,
        "department":    department,
        "city":          city,
        "role":          role,
        "joined":        datetime.now().strftime("%Y-%m-%d"),
    }
    users_col().insert_one(doc)
    return get_user(email), None


def login_user(email, password):
    u = get_user(email)
    if not u:
        return None, "Email not found"
    if u["password_hash"] != _hash(password):
        return None, "Incorrect password"
    return u, None


def update_user(email, updates):
    u = get_user(email)
    if not u:
        return None, "User not found"

    set_fields = {}
    allowed = ["name", "phone", "department", "city", "role"]
    for k, v in updates.items():
        if k in allowed and v:
            set_fields[k] = v
    if "new_password" in updates and updates["new_password"]:
        set_fields["password_hash"] = _hash(updates["new_password"])

    if set_fields:
        users_col().update_one({"email": email.lower()}, {"$set": set_fields})
    return get_user(email), None


def safe_user(u):
    """Return user dict without password hash and _id."""
    return {k: v for k, v in u.items() if k not in ("password_hash", "_id")}


# ── User Products ──────────────────────────────────────────────────────────

def _next_asin():
    """Get max asin from both products and user_products, then +1."""
    max_product = 0
    p = products_col().find_one(sort=[("asin", -1)])
    if p:
        max_product = int(p.get("asin", 0))

    max_user = 0
    up = user_products_col().find_one(sort=[("asin", -1)])
    if up:
        max_user = int(up.get("asin", 0))

    return max(max_product, max_user) + 1


def _next_id():
    up = user_products_col().find_one(sort=[("id", -1)])
    if up:
        return int(up.get("id", 0)) + 1
    return 1


def add_user_product(owner_email, title, category, price, stars,
                     bought, is_best_seller, description="", image_filename=""):
    new_id   = _next_id()
    new_asin = _next_asin()
    doc = {
        "asin":              new_asin,
        "id":                new_id,
        "owner_email":       owner_email.lower(),
        "title":             title,
        "categoryName":      category,
        "price":             price,
        "stars":             stars,
        "boughtInLastMonth": bought,
        "isBestSeller":      is_best_seller,
        "description":       description,
        "image_filename":    image_filename,
        "added_on":          datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    user_products_col().insert_one(doc)
    result = user_products_col().find_one({"asin": new_asin}, {"_id": 0})
    return result


def get_user_products(owner_email):
    return list(user_products_col().find(
        {"owner_email": owner_email.lower()},
        {"_id": 0}
    ))


def delete_user_product(owner_email, product_id):
    result = user_products_col().delete_one({
        "owner_email": owner_email.lower(),
        "id": int(product_id)
    })
    return result.deleted_count > 0


def get_all_user_products():
    return list(user_products_col().find({}, {"_id": 0}))
