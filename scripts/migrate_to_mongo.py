"""
MongoDB Migration Script — ZYNAPSE
Migrates all data from CSV files + images folder into MongoDB.

Usage:
    python3 scripts/migrate_to_mongo.py

What it does:
    1. Inserts 10,000 products from products_with_demand.csv
    2. Inserts users from users.csv
    3. Inserts user_products from user_products.csv
    4. Uploads ~44,000 product images into GridFS
    5. Creates indexes for fast queries
"""
import os
import sys
import csv
import time
import glob

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.core.database import (
    get_db, get_gridfs, products_col, users_col,
    user_products_col, ensure_indexes, ping
)


DATA_DIR   = os.path.join(PROJECT_ROOT, "data")
IMAGES_DIR = os.path.join(PROJECT_ROOT, "static", "images")


def migrate_products():
    """Migrate products_with_demand.csv → products collection."""
    csv_path = os.path.join(DATA_DIR, "products_with_demand.csv")
    if not os.path.exists(csv_path):
        print("[!] products_with_demand.csv not found. Skipping.")
        return

    col = products_col()

    # Check if already migrated
    existing = col.count_documents({})
    if existing > 0:
        print(f"[Products] Already have {existing} documents. Dropping and re-importing...")
        col.drop()

    print("[Products] Reading CSV...")
    seen_asins = set()
    docs = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asin = int(row.get("asin", 0))
            if asin in seen_asins:
                continue  # skip duplicate ASINs from balanced dataset
            seen_asins.add(asin)
            doc = {
                "asin":              asin,
                "title":             row.get("title", ""),
                "categoryName":      row.get("categoryName", ""),
                "price":             float(row.get("price", 0)),
                "stars":             float(row.get("stars", 0)),
                "boughtInLastMonth": int(row.get("boughtInLastMonth", 0)),
                "isBestSeller":      row.get("isBestSeller", "False").strip().lower() == "true",
                "demand_score":      float(row.get("demand_score", 0)),
                "demand_level":      row.get("demand_level", ""),
                "stars_norm":        float(row.get("stars_norm", 0)),
                "bought_norm":       float(row.get("bought_norm", 0)),
                "bs_norm":           float(row.get("bs_norm", 0)),
                "price_norm":        float(row.get("price_norm", 0)),
                "is_user_product":   False,
            }
            docs.append(doc)

    # Bulk insert
    if docs:
        col.insert_many(docs, ordered=False)
    print(f"[Products] ✅ Inserted {len(docs)} unique products (skipped {len(seen_asins) - len(docs) if len(seen_asins) != len(docs) else 0} duplicates).")


def migrate_users():
    """Migrate users.csv → users collection."""
    csv_path = os.path.join(DATA_DIR, "users.csv")
    if not os.path.exists(csv_path):
        print("[!] users.csv not found. Skipping.")
        return

    col = users_col()
    existing = col.count_documents({})
    if existing > 0:
        print(f"[Users] Already have {existing} users. Dropping and re-importing...")
        col.drop()

    docs = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = {
                "email":         row.get("email", "").strip().lower(),
                "password_hash": row.get("password_hash", ""),
                "name":          row.get("name", ""),
                "phone":         row.get("phone", ""),
                "department":    row.get("department", ""),
                "city":          row.get("city", ""),
                "role":          row.get("role", "Analyst"),
                "joined":        row.get("joined", ""),
            }
            if doc["email"]:
                docs.append(doc)

    if docs:
        col.insert_many(docs, ordered=False)
    print(f"[Users] ✅ Inserted {len(docs)} users.")


def migrate_user_products():
    """Migrate user_products.csv → user_products collection."""
    csv_path = os.path.join(DATA_DIR, "user_products.csv")
    if not os.path.exists(csv_path):
        print("[!] user_products.csv not found. Skipping.")
        return

    col = user_products_col()
    existing = col.count_documents({})
    if existing > 0:
        print(f"[UserProducts] Already have {existing}. Dropping and re-importing...")
        col.drop()

    docs = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("id"):
                continue
            doc = {
                "asin":              int(row.get("asin", 0)),
                "id":                int(row.get("id", 0)),
                "owner_email":       row.get("owner_email", "").lower(),
                "title":             row.get("title", ""),
                "categoryName":      row.get("categoryName", ""),
                "price":             float(row.get("price", 0)),
                "stars":             float(row.get("stars", 0)),
                "boughtInLastMonth": int(row.get("boughtInLastMonth", 0)),
                "isBestSeller":      row.get("isBestSeller", "FALSE").upper() == "TRUE",
                "description":       row.get("description", ""),
                "image_filename":    row.get("image_filename", ""),
                "added_on":          row.get("added_on", ""),
            }
            docs.append(doc)

    if docs:
        col.insert_many(docs, ordered=False)
    print(f"[UserProducts] ✅ Inserted {len(docs)} user products.")


def migrate_images():
    """Upload product images from static/images/ into GridFS."""
    if not os.path.exists(IMAGES_DIR):
        print("[!] static/images/ directory not found. Skipping.")
        return

    fs = get_gridfs()
    db = get_db()

    # Check if already migrated
    existing = db["fs.files"].count_documents({})
    if existing > 1000:
        print(f"[Images] GridFS already has {existing} files. Skipping upload.")
        print(f"         (Delete fs.files and fs.chunks collections to re-import)")
        return

    # Clear any partial uploads
    if existing > 0:
        db["fs.files"].drop()
        db["fs.chunks"].drop()

    image_files = glob.glob(os.path.join(IMAGES_DIR, "*.jpg"))
    total = len(image_files)
    print(f"[Images] Found {total} images. Starting GridFS upload...")

    start = time.time()
    uploaded = 0
    errors = 0

    for i, img_path in enumerate(image_files):
        try:
            filename = os.path.basename(img_path)
            asin_str = filename.replace(".jpg", "")

            with open(img_path, "rb") as img_file:
                fs.put(
                    img_file,
                    filename=filename,
                    content_type="image/jpeg",
                    asin=asin_str,
                )
            uploaded += 1

            # Progress every 1000
            if (i + 1) % 1000 == 0:
                elapsed = time.time() - start
                rate = (i + 1) / elapsed
                remaining = (total - i - 1) / rate if rate > 0 else 0
                print(f"  [{i+1}/{total}] {uploaded} uploaded | "
                      f"{rate:.0f} img/sec | ~{remaining:.0f}s remaining")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [Error] {img_path}: {e}")

    elapsed = time.time() - start
    print(f"[Images] ✅ Uploaded {uploaded}/{total} images to GridFS "
          f"in {elapsed:.1f}s ({errors} errors)")


def verify():
    """Print final counts."""
    db = get_db()
    print("\n" + "=" * 50)
    print("  MIGRATION COMPLETE — VERIFICATION")
    print("=" * 50)
    print(f"  products:      {products_col().count_documents({}):,} documents")
    print(f"  users:         {users_col().count_documents({}):,} documents")
    print(f"  user_products: {user_products_col().count_documents({}):,} documents")
    print(f"  GridFS images: {db['fs.files'].count_documents({}):,} files")
    print(f"  GridFS chunks: {db['fs.chunks'].count_documents({}):,} chunks")
    print("=" * 50)


if __name__ == "__main__":
    print("=" * 50)
    print("  ZYNAPSE — MongoDB Migration")
    print("=" * 50)

    if not ping():
        print("[FATAL] Cannot connect to MongoDB. Is it running?")
        sys.exit(1)

    print(f"[OK] Connected to MongoDB\n")

    # Phase 1: Structured data
    migrate_products()
    migrate_users()
    migrate_user_products()

    # Phase 2: Indexes
    ensure_indexes()

    # Phase 3: Unstructured data (images)
    print("\n[Images] This will upload ~4GB of images. This may take a few minutes...")
    migrate_images()

    # Verify
    verify()
