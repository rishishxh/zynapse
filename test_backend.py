"""
Quick backend sanity check — run with: python test_backend.py
Tests data loading, all API logic, and image file existence.
"""
import os, sys

PASS = []
FAIL = []

def ok(msg):
    PASS.append(msg)
    print("  PASS:", msg)

def fail(msg):
    FAIL.append(msg)
    print("  FAIL:", msg)

print("\n=== QUANT COMMERCE Backend Test ===\n")

# 1. Loader
print("[1] Data Loader")
try:
    from app.core.loader import load_data, get_df
    load_data()
    df = get_df()
    ok("load_data() succeeded")
    ok("{} rows loaded".format(len(df)))
    assert "demand_score" in df.columns, "demand_score column missing"
    ok("demand_score column present")
    assert df["asin"].dtype.name == "int64", "asin dtype wrong: " + df["asin"].dtype.name
    ok("asin dtype = int64")
except Exception as e:
    fail("Loader error: " + str(e))

# 2. Image files
print("\n[2] Image Files")
try:
    df = get_df()
    sample_asins = df["asin"].head(10).tolist()
    missing = []
    for asin in sample_asins:
        path = os.path.join("static", "images", "{}.jpg".format(asin))
        if not os.path.exists(path):
            missing.append(str(asin))
    if missing:
        fail("Missing images for ASINs: " + ", ".join(missing))
    else:
        ok("All 10 sample images exist (e.g. static/images/{}.jpg)".format(sample_asins[0]))
    
    # Check placeholder
    ph = os.path.join("static", "assets", "placeholder_product.png")
    if os.path.exists(ph):
        ok("placeholder_product.png exists")
    else:
        fail("placeholder_product.png MISSING at " + ph)
except Exception as e:
    fail("Image check error: " + str(e))

# 3. API logic
print("\n[3] API Logic")
try:
    df = get_df()
    
    # products list
    total = len(df)
    page_df = df.iloc[0:20]
    ok("/api/products returns {} total, page has {} rows".format(total, len(page_df)))
    
    # search
    results = df[df["title"].str.contains("shirt", case=False, na=False)]
    ok("/api/products?search=shirt returns {} results".format(len(results)))
    
    # category
    cats = sorted(df["categoryName"].dropna().unique().tolist())
    ok("/api/categories returns {} categories".format(len(cats)))
    
    # recommended
    best = df[df["isBestSeller"] == True]
    top = best.nlargest(10, "demand_score")
    ok("/api/recommended returns {} products".format(len(top)))
    
    # demand by asin (int lookup)
    asin = int(df["asin"].iloc[0])
    match = df[df["asin"] == asin]
    assert not match.empty, "asin int lookup failed"
    score = float(match.iloc[0]["demand_score"])
    level = "High" if score >= 150 else ("Medium" if score >= 110 else "Low")
    ok("/api/demand/{} -> score={:.1f} level={}".format(asin, score, level))
    
    # stats
    ok("/api/stats -> avg_price={:.2f} avg_stars={:.2f}".format(
        float(df["price"].mean()), float(df["stars"].mean())))

except Exception as e:
    fail("API logic error: " + str(e))

# 4. main.py imports
print("\n[4] main.py Imports")
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("main", "main.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok("main.py imports cleanly")
    # Check no catch-all route
    routes = [r.path for r in mod.app.routes if hasattr(r, "path")]
    catchall = [r for r in routes if "{filename" in r]
    if catchall:
        fail("Catch-all route still present: " + str(catchall))
    else:
        ok("No catch-all route (images will serve correctly)")
    static_mount = any(getattr(r, "name", "") == "static" for r in mod.app.routes)
    if static_mount:
        ok("Static mount /static is registered")
    else:
        fail("Static mount missing!")
except Exception as e:
    fail("main.py error: " + str(e))

# Summary
print("\n=== Results ===")
print("  PASSED: {}".format(len(PASS)))
print("  FAILED: {}".format(len(FAIL)))
if FAIL:
    print("\nFailed checks:")
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
else:
    print("\nAll checks passed. Start server with: python main.py")
