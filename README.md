# ZYNAPSE

> AI-powered e-commerce analytics & demand prediction platform.

ZYNAPSE is a full-stack web application that combines a product marketplace with a deep-learning demand forecasting engine. It ships with a 10,000-product catalog, a neural-network model that classifies products into **High / Medium / Low** demand tiers, an admin analytics dashboard, and a user-facing marketplace with cart, checkout, and seller tools.

Built with **FastAPI**, **MongoDB (+ GridFS)**, **scikit-learn (MLP)**, and a vanilla-JS / Bootstrap frontend.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
- [Data Migration](#data-migration)
- [API Reference](#api-reference)
- [ML Model](#ml-model)
- [Frontend Pages](#frontend-pages)
- [Development Notes](#development-notes)

---

## Features

### Marketplace
- Browse 10,000 products with search, category filter, sort, price/rating filters
- Product detail pages with images served from MongoDB GridFS
- Shopping cart and checkout flow
- Order history per user

### AI / Analytics
- **Deep-learning demand prediction** — MLP classifier (Dense 128 → 64 → 32 → Softmax 3)
- **Live "what-if" predictor** — POST custom price / rating / category and get a demand class
- **Category analysis** dashboard with price distribution, rating spread, demand mix
- **Inventory dashboard** with reorder alerts driven by predicted demand
- **Analytics dashboard** — KPIs, category distribution, monthly trends, ratings-vs-price scatter, feature correlation heatmap

### Seller / User Tools
- Email + password authentication (register / login / profile)
- "My Products" panel — add, edit, delete listings
- Per-product image upload (saved to disk **and** GridFS)
- Profile management

### Admin
- Admin dashboard (`/admin.html`) for catalog-wide oversight
- Dataset rebuild trigger for retraining the model on a balanced sample

---

## Tech Stack

| Layer | Stack |
| --- | --- |
| Backend | Python 3.7+, FastAPI, Uvicorn |
| Database | MongoDB + GridFS (CSV fallback if Mongo is unreachable) |
| ML | scikit-learn (`MLPClassifier`, `StandardScaler`, `LabelEncoder`), NumPy, pandas |
| Frontend | HTML, Bootstrap 5, vanilla JS, Chart.js |
| Fonts | Outfit, Space Grotesk |

---

## Architecture

```
┌────────────────────────┐      ┌───────────────────────┐
│   Static Frontend      │ ───► │   FastAPI (main.py)   │
│   (Bootstrap + JS)     │      │   /api/* routers      │
└────────────────────────┘      └───────────┬───────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
                │   MongoDB        │ │  MLP model   │ │   GridFS         │
                │   products /     │ │ (in-memory,  │ │   product images │
                │   users / orders │ │  trained on  │ │                  │
                │   user_products  │ │  startup)    │ │                  │
                └──────────────────┘ └──────────────┘ └──────────────────┘
```

On startup (`main.py` lifespan):
1. Pings MongoDB; falls back to CSV if unavailable.
2. Loads the product catalog into an in-memory pandas DataFrame.
3. Builds a balanced training dataset and trains the MLP.
4. Mounts static files and registers `/api` + `/api/analytics` routers.

---

## Project Structure

```
zynapse/
├── main.py                       # FastAPI entrypoint
├── app/
│   ├── api/
│   │   ├── routes.py             # products, auth, orders, predict, inventory
│   │   └── analytics.py          # dashboard aggregations
│   └── core/
│       ├── database.py           # MongoDB + GridFS connection
│       ├── mongo_loader.py       # in-memory DataFrame loader
│       ├── loader.py             # CSV fallback loader
│       ├── rf_model.py           # MLP demand-prediction model
│       ├── dataset_builder.py    # balanced training-set builder
│       ├── mongo_user_store.py   # user CRUD against Mongo
│       └── user_store.py         # user CRUD CSV fallback
├── scripts/
│   └── migrate_to_mongo.py       # one-shot CSV → MongoDB migration
├── data/                         # CSV seed data (products, users, orders)
├── static/                       # HTML pages, JS, CSS, images
│   ├── index.html · marketplace.html · product.html
│   ├── checkout.html · login.html · profile.html
│   ├── admin.html · analytics.html · inventory.html
│   ├── predict.html · predictions.html · demand_trends.html
│   ├── category_analysis.html · my_products.html · add_product.html
│   └── assets/ · images/ · user_images/
├── check_images.py · clean.py · diagnose.py · fix_header.py
└── test_backend.py
```

---

## Getting Started

### Prerequisites
- Python **3.7+** (3.9+ recommended)
- MongoDB **6.x** running locally on `27017` (or a remote URI)
- ~500 MB free disk for the seed image set

### Install

```bash
git clone <your-repo-url> zynapse
cd zynapse

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install fastapi uvicorn[standard] pymongo pandas numpy scikit-learn python-multipart
```

> A `requirements.txt` is not yet committed — the dependencies above match every `import` in the project. Generate one with `pip freeze > requirements.txt` once your environment is set up.

---

## Configuration

ZYNAPSE reads two environment variables (both optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB` | `zynapse` | Database name |

Example:

```bash
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="zynapse"
```

If MongoDB is unreachable, the app logs a warning and serves the catalog from the CSV files in `data/` — useful for quick local demos.

---

## Running the App

```bash
python3 main.py
```

or directly with uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

- App: <http://localhost:8000>
- Interactive API docs: <http://localhost:8000/docs>
- OpenAPI schema: <http://localhost:8000/openapi.json>

---

## Data Migration

To populate MongoDB from the included CSVs and image folder:

```bash
python3 scripts/migrate_to_mongo.py
```

This will:
1. Insert ~10,000 products from `data/products_with_demand.csv`
2. Insert users from `data/users.csv`
3. Insert seller-uploaded products from `data/user_products.csv`
4. Upload product images into GridFS
5. Create indexes for fast queries

---

## API Reference

All endpoints are prefixed with `/api`. Analytics endpoints live under `/api/analytics`.

### Catalog
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/products` | Paginated list with `search`, `category`, `sort_by`, `min_price`, `max_price`, `min_stars`, `bestseller` |
| `GET` | `/products/{asin}` | Single product by ASIN |
| `GET` | `/categories` | All category names |
| `GET` | `/recommended` | Top sellers by demand score |
| `GET` | `/stats` | Dataset summary |
| `GET` | `/images/{asin}` | Stream product image from GridFS |

### AI / Demand
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/demand/{asin}` | Predicted demand for one product |
| `GET` | `/predictions` | Bulk predictions for top N products |
| `GET` | `/trends` | Demand trends grouped by category |
| `GET` | `/inventory` | Inventory overview + reorder alerts |
| `POST` | `/predict` | Predict demand from a custom feature payload |
| `GET` | `/predict/warmup` | Pre-warm the model |
| `GET` | `/model-stats` | Training accuracy & class distribution |
| `GET` | `/category-analysis` | Per-category aggregations |

### Auth & Users
| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/auth/register` | Create an account |
| `POST` | `/auth/login` | Sign in |
| `GET`  | `/auth/me` | Current user |
| `PUT`  | `/auth/me` | Update profile |

### Seller Products
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET`    | `/user/products` | List your listings |
| `POST`   | `/user/products` | Create a listing |
| `POST`   | `/user/products/upload-image` | Upload product image |
| `PUT`    | `/user/products/{id}` | Update a listing |
| `DELETE` | `/user/products/{id}` | Delete a listing |

### Orders
| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/orders` | Save an order |
| `GET`  | `/orders` | Get the signed-in user's orders |

### Analytics (`/api/analytics/*`)
`summary`, `category-distribution`, `price-distribution`, `demand-analysis`, `ratings-vs-price`, `monthly-trend`, `correlation`.

### System
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/db/status` | MongoDB connectivity probe |
| `GET` | `/api/dataset/info` | Training-set metadata |
| `POST` | `/api/dataset/build` | Rebuild the balanced training set |

---

## ML Model

ZYNAPSE uses a scikit-learn **MLPClassifier** to predict demand as a 3-class problem.

```
Input(5) → Dense(128, ReLU) → Dense(64, ReLU) → Dense(32, ReLU) → Softmax(3)
Optimizer : Adam (lr = 0.001)
L2 reg    : alpha = 0.001
Split     : 80% train / 20% test, stratified
```

**Features** (all normalized to `[0, 100]` so each contributes equally before `StandardScaler` is applied):

| Feature | Meaning |
| --- | --- |
| `stars_norm` | `(stars − 1) / 4 × 100` — perceived quality |
| `bought_norm` | `bought / max_bought × 100` — popularity |
| `bs_norm` | `isBestSeller × 100` — market validation |
| `price_norm` | `(1 − (price − min) / (max − min)) × 100` — affordability |
| `cat_enc` | label-encoded category |

**Labels:** `High` (score ≥ 60), `Medium` (35–60), `Low` (< 35).

The model is trained on a **balanced** dataset (built by `dataset_builder.build_dataset`) so the three demand classes contribute equally, preventing the "everything is Medium" collapse you get on the raw distribution.

---

## Frontend Pages

| Page | Purpose |
| --- | --- |
| `index.html` | Landing / dashboard |
| `marketplace.html` | Product grid with filters |
| `product.html` | Product detail view |
| `checkout.html` | Cart + checkout |
| `login.html`, `profile.html` | Auth & account |
| `admin.html` | Admin overview |
| `analytics.html` | KPI + chart dashboard |
| `category_analysis.html` | Per-category drilldown |
| `demand_trends.html` | Demand-tier trends |
| `predict.html` | Live what-if demand predictor |
| `predictions.html` | Bulk model predictions |
| `inventory.html` | Stock + reorder alerts |
| `add_product.html`, `my_products.html` | Seller listings |

Frontend HTML is served directly by FastAPI with `Cache-Control: no-store` so iterative changes show up immediately on refresh.

---

## Development Notes

- **No-cache for HTML** — `main.py` adds a middleware that disables HTML caching to avoid the classic "I deployed but I still see the old page" trap.
- **Image fallback** — `serve_user_image` falls back to `static/assets/placeholder_product.png` if a user image goes missing.
- **GridFS image upload** — when a seller uploads a new image, ZYNAPSE removes any stale GridFS file with the same filename before storing the new one. This prevents collisions with seed images that share newly issued ASINs.
- **CSV fallback** — every Mongo-backed loader has a CSV twin (`loader.py`, `user_store.py`) so the app degrades gracefully when Mongo is offline.
- **Diagnostics** — `diagnose.py`, `test_backend.py`, and `check_images.py` are utility scripts for inspecting the dataset and verifying the backend end-to-end.

---

## License

This project does not yet specify a license. Add one (e.g. MIT, Apache-2.0) before publishing publicly.
