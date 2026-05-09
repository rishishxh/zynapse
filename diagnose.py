"""
Run: python diagnose.py
Writes results to diagnose_output.txt
"""
import os, sys

out = []

def log(msg):
    out.append(msg)
    print(msg)

log("=== QUANT COMMERCE IMAGE DIAGNOSIS ===\n")

# 1. Check CSV
try:
    import pandas as pd
    df = pd.read_csv("data/products.csv", nrows=10)
    log("CSV columns: " + str(df.columns.tolist()))
    log("asin dtype: " + str(df["asin"].dtype))
    log("Sample ASINs: " + str(df["asin"].tolist()))
    log("Sample asin type in Python: " + str(type(df["asin"].iloc[0])))
    # Check what to_dict returns for asin
    rec = df.iloc[0].to_dict()
    log("to_dict asin value: " + repr(rec["asin"]))
    log("to_dict asin type: " + str(type(rec["asin"])))
except Exception as e:
    log("CSV ERROR: " + str(e))

log("")

# 2. Check image files exist for those ASINs
try:
    import pandas as pd
    df = pd.read_csv("data/products.csv", nrows=20)
    log("Checking image files for first 20 ASINs:")
    for asin in df["asin"].tolist():
        # Exactly what JS builds: /static/images/{asin}.jpg
        # Server maps that to: static/images/{asin}.jpg
        path = os.path.join("static", "images", str(asin) + ".jpg")
        exists = os.path.exists(path)
        log("  static/images/{}.jpg -> {}".format(asin, "EXISTS" if exists else "MISSING"))
except Exception as e:
    log("IMAGE CHECK ERROR: " + str(e))

log("")

# 3. Check what the API actually returns for asin
try:
    import pandas as pd
    df = pd.read_csv("data/products.csv", dtype={"asin": "int64", "price": "float32", "stars": "float32", "boughtInLastMonth": "int32", "isBestSeller": "bool"})
    df["demand_score"] = (df["stars"] * 20.0) + (df["boughtInLastMonth"] * 0.1)
    rec = df.iloc[0].to_dict()
    log("API would return asin as: " + repr(rec["asin"]) + " (type: " + str(type(rec["asin"])) + ")")
    # What JS would build
    asin_val = rec["asin"]
    url = "/static/images/{}.jpg".format(asin_val)
    log("JS would build URL: " + url)
    # Check that file
    path = "static/images/{}.jpg".format(asin_val)
    log("File on disk: " + path + " -> " + ("EXISTS" if os.path.exists(path) else "MISSING"))
except Exception as e:
    log("API SIMULATION ERROR: " + str(e))

log("")

# 4. Check static mount path
log("STATIC_DIR = " + os.path.join(os.path.dirname(os.path.abspath("main.py")), "static"))
log("Images folder: " + ("EXISTS" if os.path.isdir("static/images") else "MISSING"))
log("Assets folder: " + ("EXISTS" if os.path.isdir("static/assets") else "MISSING"))
log("placeholder_product.png: " + ("EXISTS" if os.path.exists("static/assets/placeholder_product.png") else "MISSING"))

# 5. Count images
try:
    imgs = os.listdir("static/images")
    log("Total images in static/images: " + str(len(imgs)))
    log("First 5 image filenames: " + str(sorted(imgs)[:5]))
    log("Last 5 image filenames: " + str(sorted(imgs)[-5:]))
except Exception as e:
    log("IMAGE COUNT ERROR: " + str(e))

log("")

# 6. Check if numpy int64 causes issues in string formatting
try:
    import numpy as np
    test_val = np.int64(34229)
    url = "/static/images/{}.jpg".format(test_val)
    log("numpy int64 in format string: " + url)
    log("str(numpy int64): " + str(test_val))
except Exception as e:
    log("NUMPY TEST ERROR: " + str(e))

# Write to file
with open("diagnose_output.txt", "w") as f:
    f.write("\n".join(out))

log("\nOutput saved to diagnose_output.txt")
