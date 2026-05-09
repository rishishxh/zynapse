"""
User Store — QUANT COMMERCE
CSV-backed user accounts and user-added products.
Files: data/users.csv, data/user_products.csv
"""
import os
import hashlib
import csv
from datetime import datetime

BASE_DIR         = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USERS_CSV        = os.path.join(BASE_DIR, "data", "users.csv")
USER_PRODUCTS_CSV = os.path.join(BASE_DIR, "data", "user_products.csv")

USERS_FIELDS = ["email","password_hash","name","phone","department","city","role","joined"]
PROD_FIELDS  = ["asin","id","owner_email","title","categoryName","price","stars",
                "boughtInLastMonth","isBestSeller","description","image_filename","added_on"]


def _hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ── users ──────────────────────────────────────────────────────────────────

def _read_users():
    if not os.path.exists(USERS_CSV):
        return []
    with open(USERS_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_users(rows):
    with open(USERS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=USERS_FIELDS)
        w.writeheader()
        w.writerows(rows)


def get_user(email):
    for u in _read_users():
        if u["email"].lower() == email.lower():
            return u
    return None


def register_user(email, password, name, phone="", department="", city="", role="Analyst"):
    if get_user(email):
        return None, "Email already registered"
    rows = _read_users()
    rows.append({
        "email":         email.lower(),
        "password_hash": _hash(password),
        "name":          name,
        "phone":         phone,
        "department":    department,
        "city":          city,
        "role":          role,
        "joined":        datetime.now().strftime("%Y-%m-%d"),
    })
    _write_users(rows)
    return get_user(email), None


def login_user(email, password):
    u = get_user(email)
    if not u:
        return None, "Email not found"
    if u["password_hash"] != _hash(password):
        return None, "Incorrect password"
    return u, None


def update_user(email, updates):
    rows = _read_users()
    for i, u in enumerate(rows):
        if u["email"].lower() == email.lower():
            for k, v in updates.items():
                if k in USERS_FIELDS and k not in ("email", "password_hash", "joined"):
                    rows[i][k] = v
            if "new_password" in updates and updates["new_password"]:
                rows[i]["password_hash"] = _hash(updates["new_password"])
            _write_users(rows)
            return rows[i], None
    return None, "User not found"


def safe_user(u):
    """Return user dict without password hash."""
    return {k: v for k, v in u.items() if k != "password_hash"}


# ── user products ──────────────────────────────────────────────────────────

def _read_user_products():
    if not os.path.exists(USER_PRODUCTS_CSV):
        return []
    with open(USER_PRODUCTS_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("id")]   # skip blank rows


def _write_user_products(rows):
    with open(USER_PRODUCTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PROD_FIELDS)
        w.writeheader()
        w.writerows(rows)


def _next_id():
    rows = _read_user_products()
    if not rows:
        return 1
    return max(int(r["id"]) for r in rows) + 1


def _next_asin():
    """Return max(products.csv asin) + 1, then keep incrementing for each new user product."""
    import pandas as pd
    products_csv = os.path.join(BASE_DIR, "data", "products.csv")
    base_max = 0
    if os.path.exists(products_csv):
        try:
            df = pd.read_csv(products_csv, usecols=["asin"], dtype={"asin": "int64"})
            base_max = int(df["asin"].max())
        except Exception:
            base_max = 60000  # fallback if CSV unreadable

    # also account for any already-assigned user product asins
    rows = _read_user_products()
    user_asins = [int(r["asin"]) for r in rows if r.get("asin")]
    if user_asins:
        base_max = max(base_max, max(user_asins))

    return base_max + 1


def add_user_product(owner_email, title, category, price, stars,
                     bought, is_best_seller, description="", image_filename=""):
    rows = _read_user_products()
    new_id   = _next_id()
    new_asin = _next_asin()
    new = {
        "asin":             new_asin,
        "id":               new_id,
        "owner_email":      owner_email.lower(),
        "title":            title,
        "categoryName":     category,
        "price":            price,
        "stars":            stars,
        "boughtInLastMonth": bought,
        "isBestSeller":     "TRUE" if is_best_seller else "FALSE",
        "description":      description,
        "image_filename":   image_filename,
        "added_on":         datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    rows.append(new)
    _write_user_products(rows)
    return new


def get_user_products(owner_email):
    return [r for r in _read_user_products()
            if r["owner_email"].lower() == owner_email.lower()]


def delete_user_product(owner_email, product_id):
    rows = _read_user_products()
    new  = [r for r in rows
            if not (r["owner_email"].lower() == owner_email.lower()
                    and str(r["id"]) == str(product_id))]
    if len(new) == len(rows):
        return False
    _write_user_products(new)
    return True


def get_all_user_products():
    """Return all user-added products from CSV."""
    return _read_user_products()
