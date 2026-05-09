"""
Deep Learning Model -- QUANT COMMERCE
Multi-Layer Perceptron Neural Network to predict demand level.

Architecture : Input(5) -> Dense(128,ReLU) -> Dense(64,ReLU) -> Dense(32,ReLU) -> Output(3,Softmax)
Optimizer    : Adam  (lr=0.001)
Regularization: L2  (alpha=0.001)

Feature engineering (EQUAL CONTRIBUTION):
  All 4 factors are pre-normalised to [0,100] before entering the model.
  This ensures each factor contributes equally to the prediction:
    - stars_norm       = (stars - 1) / 4 * 100        (quality)
    - bought_norm      = bought / max_bought * 100     (popularity)
    - bs_norm          = isBestSeller * 100            (market validation)
    - price_norm       = (1 - (price-min)/(max-min)) * 100  (affordability)
    - cat_enc          = label-encoded category

  StandardScaler is still applied on top so the MLP converges faster,
  but since all inputs are already on the same [0,100] scale the scaler
  only fine-tunes — it does NOT introduce any weighting bias.

Train/Test : 80% train (8000) / 20% test (2000), stratified split
"""

import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from app.core.mongo_loader import get_df

_model       = None
_cat_enc     = None
_label_enc   = None
_scaler      = None
_classes     = None
_model_stats = None
# store dataset stats needed to normalise single predictions
_bought_max  = None
_price_min   = None
_price_max   = None


def _demand_label(score):
    # score is 0-100 equal-weight composite
    if score >= 60:
        return "High"
    elif score >= 35:
        return "Medium"
    return "Low"


def get_model():
    global _model, _cat_enc, _label_enc, _scaler, _classes, _model_stats
    global _bought_max, _price_min, _price_max

    if _model is not None:
        return _model, _cat_enc, _label_enc, _scaler, _classes

    df = get_df().copy()

    # Store dataset stats for single-prediction normalisation
    _bought_max = float(df["boughtInLastMonth"].max())
    _price_min  = float(df["price"].min())
    _price_max  = float(df["price"].max())

    # Target
    df["demand_level"] = df["demand_score"].apply(_demand_label)

    # Encode category
    _cat_enc = LabelEncoder()
    df["cat_enc"] = _cat_enc.fit_transform(df["categoryName"].fillna("Unknown"))

    # ── EQUAL-CONTRIBUTION FEATURE MATRIX ──────────────────────────────────
    # Use pre-normalised columns from loader (all on 0-100 scale)
    # + label-encoded category (also scaled by StandardScaler below)
    X = df[["stars_norm", "bought_norm", "bs_norm", "price_norm", "cat_enc"]].values.astype(float)

    # Encode target
    _label_enc = LabelEncoder()
    y = _label_enc.fit_transform(df["demand_level"].values)
    _classes = list(_label_enc.classes_)

    # 80/20 stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # StandardScaler for faster MLP convergence
    # (inputs already equal-scale, scaler just centres them)
    _scaler = StandardScaler()
    X_train = _scaler.fit_transform(X_train)
    X_test  = _scaler.transform(X_test)

    # MLP Neural Network
    _model = MLPClassifier(
        hidden_layer_sizes=(128, 64, 32),
        activation="relu",
        solver="adam",
        alpha=0.001,
        batch_size=64,
        learning_rate_init=0.001,
        max_iter=300,
        early_stopping=False,
        random_state=42,
        verbose=False,
    )

    print("[DL] Training MLP (equal-weight features: stars/bought/bestseller/price)...")
    _model.fit(X_train, y_train)

    y_pred     = _model.predict(X_test)
    accuracy   = round(accuracy_score(y_test, y_pred) * 100, 2)
    y_test_str = _label_enc.inverse_transform(y_test)
    y_pred_str = _label_enc.inverse_transform(y_pred)
    report     = classification_report(y_test_str, y_pred_str, output_dict=True)

    _model_stats = {
        "model_type":     "MLP Neural Network (Deep Learning)",
        "architecture":   "Input(5) -> Dense(128,ReLU) -> Dense(64,ReLU) -> Dense(32,ReLU) -> Output(3,Softmax)",
        "optimizer":      "Adam (lr=0.001)",
        "regularization": "L2 (alpha=0.001)",
        "feature_weights": "Equal (25% each: stars, bought, bestseller, price)",
        "epochs_run":     len(_model.loss_curve_),
        "total_samples":  len(df),
        "train_samples":  len(X_train),
        "test_samples":   len(X_test),
        "accuracy":       accuracy,
        "classes":        _classes,
        "per_class": {
            cls: {
                "precision": round(report[cls]["precision"] * 100, 1),
                "recall":    round(report[cls]["recall"]    * 100, 1),
                "f1_score":  round(report[cls]["f1-score"]  * 100, 1),
                "support":   int(report[cls]["support"]),
            }
            for cls in _classes if cls in report
        }
    }

    print("[DL] Total: {} | Train: {} (80%) | Test: {} (20%)".format(
        len(df), len(X_train), len(X_test)))
    print("[DL] Epochs: {} | Accuracy: {}%".format(len(_model.loss_curve_), accuracy))
    return _model, _cat_enc, _label_enc, _scaler, _classes


def get_model_stats():
    if _model_stats is None:
        get_model()
    return _model_stats


def predict_demand(price, stars, bought_last_month, is_best_seller, category_name):
    model, cat_enc, label_enc, scaler, classes = get_model()

    # Normalise inputs using dataset stats (same scale as training)
    stars_n  = ((float(stars) - 1.0) / 4.0) * 100.0
    bought_n = (float(bought_last_month) / _bought_max) * 100.0 if _bought_max else 0.0
    bs_n     = 100.0 if is_best_seller else 0.0
    price_rng = _price_max - _price_min
    price_n  = (1.0 - (float(price) - _price_min) / price_rng) * 100.0 if price_rng else 50.0

    # Clamp to [0, 100]
    stars_n  = max(0.0, min(100.0, stars_n))
    bought_n = max(0.0, min(100.0, bought_n))
    price_n  = max(0.0, min(100.0, price_n))

    try:
        cat_val = int(cat_enc.transform([category_name])[0])
    except ValueError:
        cat_val = 0

    X_raw = np.array([[stars_n, bought_n, bs_n, price_n, cat_val]], dtype=float)
    X     = scaler.transform(X_raw)

    pred_int   = int(model.predict(X)[0])
    pred_label = label_enc.inverse_transform([pred_int])[0]
    proba      = model.predict_proba(X)[0]
    confidence = round(float(max(proba)) * 100, 1)
    prob_map   = {cls: round(float(p) * 100, 1) for cls, p in zip(classes, proba)}

    # Equal-weight demand score for display (same formula as loader.py)
    demand_score = round(
        stars_n * 0.25 + bought_n * 0.25 + bs_n * 0.25 + price_n * 0.25, 2
    )

    return {
        "demand_level":  pred_label,
        "confidence":    confidence,
        "demand_score":  demand_score,
        "probabilities": prob_map,
    }
