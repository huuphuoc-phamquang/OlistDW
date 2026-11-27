"""Prepare Olist seller segmentation inputs (steps 1-3, without fitting clusters)."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.preprocessing import StandardScaler


REQUIRED = {
    "sellers": ["seller_id", "seller_city", "seller_state"],
    "order_items": ["order_id", "order_item_id", "seller_id", "product_id", "price", "freight_value"],
    "orders": ["order_id", "order_status", "order_purchase_timestamp",
               "order_delivered_customer_date", "order_estimated_delivery_date"],
    "products": ["product_id", "product_category_name"],
    "order_reviews": ["order_id", "review_score"],
}
KEYS = {"sellers": ["seller_id"], "orders": ["order_id"],
        "products": ["product_id"], "order_items": ["order_id", "order_item_id"]}
MODEL_FEATURES = [
    "order_count", "avg_order_value", "category_count", "freight_to_price_ratio",
    "review_score_mean", "late_delivery_rate", "delivery_days_mean", "recency_days", "tenure_days",
]
LOG_FEATURES = ["order_count", "avg_order_value", "category_count", "freight_to_price_ratio",
                "delivery_days_mean", "recency_days", "tenure_days"]


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sources(source):
    """Read the chosen Kaggle SQLite database or its equivalent raw CSV tables."""
    source = Path(source)
    tables, manifest = {}, {}
    if source.is_file():
        if source.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
            raise ValueError("Source file must be a SQLite database.")
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for name in REQUIRED:
                if name not in available:
                    raise ValueError(f"Missing SQLite table: {name}")
                tables[name] = pd.read_sql_query(f'SELECT * FROM "{name}"', connection)
        manifest["sqlite"] = {"name": source.name, "sha256": file_sha256(source)}
    elif source.is_dir():
        for name in REQUIRED:
            candidates = [source / f"{name}.csv", source / f"olist_{name}_dataset.csv"]
            existing = [path for path in candidates if path.is_file()]
            if len(existing) != 1:
                raise ValueError(f"Expected one raw CSV for {name}, found {len(existing)} in {source}")
            path = existing[0]
            tables[name] = pd.read_csv(path, dtype={column: "string" for column in REQUIRED[name]
                                                  if column.endswith("_id")})
            manifest[name] = {"name": path.name, "sha256": file_sha256(path)}
    else:
        raise FileNotFoundError(f"Olist source not found: {source}")
    return tables, manifest


def prepare_data(tables):
    """Step 1: validate grain/relationships and retain delivered sale items."""
    tables = {name: frame.copy() for name, frame in tables.items()}
    audit = {"source_rows": {}, "exact_duplicates_removed": {}, "invalid_dates": {}}
    for name, columns in REQUIRED.items():
        frame = tables[name]
        missing = set(columns) - set(frame.columns)
        if missing:
            raise ValueError(f"{name}: missing columns {sorted(missing)}")
        audit["source_rows"][name] = len(frame)
        audit["exact_duplicates_removed"][name] = int(frame.duplicated().sum())
        frame = frame.drop_duplicates().copy()
        for column in frame.columns:
            if column.endswith("_id"):
                frame[column] = frame[column].astype("string").str.strip().replace("", pd.NA)
        if name in KEYS:
            keys = KEYS[name]
            if frame[keys].isna().any().any() or frame.duplicated(keys).any():
                raise ValueError(f"{name}: null or conflicting duplicate key {keys}")
        tables[name] = frame
    sellers, items, orders, products, reviews = (tables[name] for name in REQUIRED)
    for column in ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        parsed = pd.to_datetime(orders[column], errors="coerce", format="mixed")
        audit["invalid_dates"][column] = int((orders[column].notna() & parsed.isna()).sum())
        orders[column] = parsed
    for column in ["price", "freight_value"]:
        items[column] = pd.to_numeric(items[column], errors="coerce")
        if not np.isfinite(items[column]).all() or (items[column] < 0).any():
            raise ValueError(f"order_items.{column}: missing, nonnumeric, infinite or negative value")
    for column, dimension, key in [("seller_id", sellers, "seller_id"),
                                    ("product_id", products, "product_id"),
                                    ("order_id", orders, "order_id")]:
        invalid = items[column].isna() | ~items[column].isin(dimension[key])
        if invalid.any():
            raise ValueError(f"order_items.{column}: {int(invalid.sum())} unmatched keys")
    if reviews["order_id"].isna().any() or not reviews["order_id"].isin(orders["order_id"]).all():
        raise ValueError("order_reviews: null or unmatched order_id")
    reviews["review_score"] = pd.to_numeric(reviews["review_score"], errors="coerce")
    invalid_score = reviews["review_score"].isna() | ~reviews["review_score"].between(1, 5)
    audit["invalid_review_scores"] = int(invalid_score.sum())
    reviews.loc[invalid_score, "review_score"] = np.nan
    # Collapse reviews BEFORE joining: multiple reviews must not multiply sale items.
    order_reviews = reviews.groupby("order_id", as_index=False).agg(review_score=("review_score", "mean"))
    joined = items.merge(orders[REQUIRED["orders"]], on="order_id", validate="many_to_one")
    audit["item_rows_by_order_status"] = {str(k): int(v) for k, v in joined["order_status"].value_counts(dropna=False).items()}
    delivered = joined["order_status"].eq("delivered")
    valid_purchase = joined["order_purchase_timestamp"].notna()
    audit["delivered_items_missing_purchase_date"] = int((delivered & ~valid_purchase).sum())
    sales = joined.loc[delivered & valid_purchase].copy()
    if sales.empty:
        raise ValueError("No delivered sale items with a valid purchase date.")
    sales = sales.merge(products[REQUIRED["products"]], on="product_id", validate="many_to_one")
    sales = sales.merge(order_reviews, on="order_id", how="left", validate="many_to_one")
    audit["eligible_item_rows"] = len(sales)
    audit["eligible_orders"] = int(sales["order_id"].nunique())
    audit["multi_seller_orders"] = int((sales.groupby("order_id")["seller_id"].nunique() > 1).sum())
    audit["orders_with_multiple_reviews"] = int((reviews.groupby("order_id").size() > 1).sum())
    return sales, sellers, audit


def create_features(sales, sellers):
    """Step 2: aggregate item values and order-level service metrics separately."""
    # One row per seller-order prevents item-heavy orders receiving extra weight.
    seller_orders = sales.groupby(["seller_id", "order_id"], as_index=False).agg(
        order_sales=("price", "sum"), order_freight=("freight_value", "sum"),
        purchase_at=("order_purchase_timestamp", "first"),
        delivered_at=("order_delivered_customer_date", "first"),
        estimated_at=("order_estimated_delivery_date", "first"),
        review_score=("review_score", "first"),
    )
    duration = (seller_orders["delivered_at"] - seller_orders["purchase_at"]).dt.total_seconds() / 86400
    valid_delivery = duration.notna() & duration.ge(0)
    seller_orders["delivery_days"] = duration.where(valid_delivery)
    valid_deadline = (valid_delivery & seller_orders["estimated_at"].notna()
                      & seller_orders["estimated_at"].ge(seller_orders["purchase_at"].dt.normalize()))
    # Estimated delivery is a calendar date: delivery later on that same date is on time.
    seller_orders["late_delivery"] = (
        seller_orders["delivered_at"].dt.normalize() > seller_orders["estimated_at"].dt.normalize()
    ).astype(float).where(valid_deadline)
    reference_date = sales["order_purchase_timestamp"].max().normalize() + pd.Timedelta(days=1)
    profiles = seller_orders.groupby("seller_id").agg(
        order_count=("order_id", "nunique"), total_sales=("order_sales", "sum"),
        total_freight=("order_freight", "sum"), avg_order_value=("order_sales", "mean"),
        review_score_mean=("review_score", "mean"), reviewed_order_count=("review_score", "count"),
        late_delivery_rate=("late_delivery", "mean"), delivery_days_mean=("delivery_days", "mean"),
        valid_delivery_order_count=("delivery_days", "count"),
        valid_deadline_order_count=("late_delivery", "count"),
        first_sale_at=("purchase_at", "min"), last_sale_at=("purchase_at", "max"),
    )
    item_profiles = sales.groupby("seller_id").agg(
        item_count=("order_item_id", "size"), product_count=("product_id", "nunique"),
        category_count=("product_category_name", "nunique"),
    )
    profiles = profiles.join(item_profiles)
    profiles["freight_to_price_ratio"] = profiles["total_freight"] / profiles["total_sales"].replace(0, np.nan)
    profiles["recency_days"] = (reference_date - profiles["last_sale_at"].dt.normalize()).dt.days
    profiles["tenure_days"] = (reference_date - profiles["first_sale_at"].dt.normalize()).dt.days
    profiles["review_coverage"] = profiles["reviewed_order_count"] / profiles["order_count"]
    profiles = profiles.reset_index().merge(sellers[REQUIRED["sellers"]], on="seller_id", validate="one_to_one")
    profiles = profiles.sort_values("seller_id").reset_index(drop=True)
    excluded = sellers.loc[~sellers["seller_id"].isin(profiles["seller_id"]), REQUIRED["sellers"]].copy()
    excluded["reason"] = "No delivered sale items with a valid purchase date"
    details = {
        "reference_date": reference_date.isoformat(),
        "purchase_start": sales["order_purchase_timestamp"].min().isoformat(),
        "purchase_end": sales["order_purchase_timestamp"].max().isoformat(),
        "eligible_sellers": len(profiles), "excluded_sellers": len(excluded),
        "invalid_delivery_seller_orders": int((~valid_delivery).sum()),
        "invalid_deadline_seller_orders": int((~valid_deadline).sum()),
    }
    return profiles, excluded.sort_values("seller_id"), details


def preprocess_features(profiles):
    """Step 3: median imputation, log1p for skewed features, then z-score scaling."""
    raw = profiles.set_index("seller_id")[MODEL_FEATURES].astype(float)
    raw = raw.replace([np.inf, -np.inf], np.nan)
    if (raw < 0).any().any():
        raise ValueError("Unexpected negative feature value.")
    medians = raw.median()
    if medians.isna().any():
        raise ValueError(f"Entirely missing features: {medians.index[medians.isna()].tolist()}")
    imputed = raw.fillna(medians)
    transformed = imputed.copy()
    transformed[LOG_FEATURES] = np.log1p(transformed[LOG_FEATURES])
    scaler = StandardScaler()
    matrix = pd.DataFrame(scaler.fit_transform(transformed), index=raw.index, columns=MODEL_FEATURES)
    if not np.isfinite(matrix.to_numpy()).all() or not matrix.index.is_unique:
        raise ValueError("Model input contains nonfinite values or duplicate sellers.")
    q1, q3 = raw.quantile(.25), raw.quantile(.75)
    outliers = (raw.lt(q1 - 1.5 * (q3 - q1)) | raw.gt(q3 + 1.5 * (q3 - q1))).sum()
    metadata = {
        "feature_order": MODEL_FEATURES, "log1p_features": LOG_FEATURES,
        "imputation": "per-feature median before log1p", "medians": medians.to_dict(),
        "scaler": "StandardScaler (population variance, ddof=0)",
        "mean": dict(zip(MODEL_FEATURES, scaler.mean_.tolist())),
        "scale": dict(zip(MODEL_FEATURES, scaler.scale_.tolist())),
        "variance": dict(zip(MODEL_FEATURES, scaler.var_.tolist())),
        "missing_before_imputation": raw.isna().sum().to_dict(),
        "iqr_outlier_counts": outliers.to_dict(),
        "outlier_policy": "Retain all eligible sellers; no clipping or automatic outlier deletion.",
        "constant_features": [name for name, variance in zip(MODEL_FEATURES, scaler.var_) if variance == 0],
        "versions": {"python": platform.python_version(), "pandas": pd.__version__,
                     "numpy": np.__version__, "scikit_learn": sklearn.__version__},
    }
    return matrix, metadata


def export_results(profiles, excluded, matrix, audit, metadata, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(output / "seller_features.csv", index=False, float_format="%.10g")
    excluded.to_csv(output / "excluded_sellers.csv", index=False)
    matrix.to_csv(output / "seller_model_input.csv", index=True, float_format="%.10g")
    profiles[MODEL_FEATURES].describe().T.to_csv(output / "feature_summary.csv", float_format="%.10g")
    for name, value in [("data_quality.json", audit), ("preprocessing.json", metadata)]:
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def run(source, output):
    tables, manifest = load_sources(source)
    sales, sellers, audit = prepare_data(tables)
    profiles, excluded, details = create_features(sales, sellers)
    matrix, metadata = preprocess_features(profiles)
    audit.update(details)
    audit["source_manifest"] = manifest
    audit["model_shape"] = list(matrix.shape)
    # Independent controls at item grain, BEFORE seller-order aggregation.
    assert len(profiles) + len(excluded) == len(sellers)
    assert profiles["seller_id"].tolist() == matrix.index.tolist()
    assert profiles["item_count"].sum() == len(sales)
    assert np.isclose(profiles["total_sales"].sum(), sales["price"].sum())
    assert np.isclose(profiles["total_freight"].sum(), sales["freight_value"].sum())
    export_results(profiles, excluded, matrix, audit, metadata, output)
    return profiles, matrix, audit, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Olist SQLite file or raw CSV directory")
    parser.add_argument("--output", type=Path, default=Path("artifacts/seller_segmentation"))
    args = parser.parse_args()
    _, matrix, audit, _ = run(args.source, args.output)
    print(json.dumps({"shape": list(matrix.shape), "reference_date": audit["reference_date"],
                      "excluded_sellers": audit["excluded_sellers"]}, indent=2))
