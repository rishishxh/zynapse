"""
Main Application — ZYNAPSE
FastAPI server — static files + API
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.mongo_loader import load_data, get_df
from app.core.database import ping as mongo_ping, ensure_indexes
from app.api.routes import router as api_router
import os, shutil, uuid

# ================= BASE PATH =================
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
USER_IMG_DIR = os.path.join(STATIC_DIR, "user_images")
os.makedirs(USER_IMG_DIR, exist_ok=True)

# ================= LIFESPAN =================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # MongoDB connection check
    if mongo_ping():
        print("[MongoDB] ✅ Connected successfully")
        ensure_indexes()
    else:
        print("[MongoDB] ⚠️  Not connected — falling back to CSV")
    load_data()
    from app.core.rf_model import get_model
    get_model()
    # build balanced training dataset on startup
    from app.core.dataset_builder import build_dataset
    build_dataset(save=True)
    yield

# ================= APP INIT =================
app = FastAPI(
    title="ZYNAPSE",
    version="2.0.0",
    lifespan=lifespan
)

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= API ROUTES =================
app.include_router(api_router)

# ================= STATIC FILES (ONLY ONE HANDLER) =================
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR, check_dir=True),
    name="static"
)

# ================= HTML ROUTES =================
@app.get("/")
async def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/index.html")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/marketplace.html")
async def marketplace():
    return FileResponse(os.path.join(STATIC_DIR, "marketplace.html"))

@app.get("/product.html")
async def product():
    return FileResponse(os.path.join(STATIC_DIR, "product.html"))

@app.get("/checkout.html")
async def checkout():
    return FileResponse(os.path.join(STATIC_DIR, "checkout.html"))

@app.get("/login.html")
async def login():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

@app.get("/admin.html")
async def admin():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))

@app.get("/demand_trends.html")
async def demand_trends():
    return FileResponse(os.path.join(STATIC_DIR, "demand_trends.html"))

@app.get("/predictions.html")
async def predictions():
    return FileResponse(os.path.join(STATIC_DIR, "predictions.html"))

@app.get("/inventory.html")
async def inventory():
    return FileResponse(os.path.join(STATIC_DIR, "inventory.html"))

@app.get("/predict.html")
async def predict_page():
    return FileResponse(os.path.join(STATIC_DIR, "predict.html"))

@app.get("/category_analysis.html")
async def category_analysis_page():
    return FileResponse(os.path.join(STATIC_DIR, "category_analysis.html"))

@app.get("/add_product.html")
async def add_product_page():
    return FileResponse(os.path.join(STATIC_DIR, "add_product.html"))

@app.get("/my_products.html")
async def my_products_page():
    return FileResponse(os.path.join(STATIC_DIR, "my_products.html"))

# ── image upload for user products ──
@app.post("/api/upload-product-image")
async def upload_product_image(
    file: UploadFile = File(...),
    product_id: str  = Form(...),
    email: str       = Form(...),
):
    allowed = {".jpg", ".jpeg", ".png", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return JSONResponse(status_code=400, content={"detail": "Only jpg/png/webp allowed"})

    # read file bytes once so we can write to two locations
    file_bytes = await file.read()

    # save to user_images/ with descriptive name
    filename = "up_{}_{}{}" .format(email.split("@")[0], product_id, ext)
    dest_user = os.path.join(USER_IMG_DIR, filename)
    with open(dest_user, "wb") as f:
        f.write(file_bytes)

    # update MongoDB — find the asin for this product_id
    from app.core.database import user_products_col
    up_doc = user_products_col().find_one({"id": int(product_id), "owner_email": email.lower()})
    asin_val = None
    if up_doc:
        asin_val = up_doc.get("asin")
        user_products_col().update_one(
            {"id": int(product_id), "owner_email": email.lower()},
            {"$set": {"image_filename": filename}}
        )

    # also save to static/images/{asin}.jpg so marketplace loads it natively
    if asin_val:
        img_name = str(asin_val) + ".jpg"
        dest_img = os.path.join(STATIC_DIR, "images", img_name)
        with open(dest_img, "wb") as f:
            f.write(file_bytes)

    return {
        "success":  True,
        "filename": filename,
        "url":      "/static/user_images/" + filename,
        "asin_img": "/static/images/" + str(asin_val) + ".jpg" if asin_val else None,
    }

# ── serve user uploaded images ──
@app.get("/static/user_images/{filename}")
async def serve_user_image(filename: str):
    path = os.path.join(USER_IMG_DIR, filename)
    if not os.path.isfile(path):
        return FileResponse(os.path.join(STATIC_DIR, "assets", "placeholder_product.png"), media_type="image/png")
    ext = filename.rsplit(".", 1)[-1].lower()
    media = "image/jpeg" if ext in ("jpg","jpeg") else "image/png"
    return FileResponse(path, media_type=media)

@app.get("/profile.html")
async def profile_page():
    return FileResponse(os.path.join(STATIC_DIR, "profile.html"))

@app.get("/register.html")
async def register_page():
    return FileResponse(os.path.join(STATIC_DIR, "register.html"))

# ================= TEST =================
@app.get("/test-data")
async def test_data():
    df = get_df()
    return {"total_products": len(df)}

# ================= RUN =================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)