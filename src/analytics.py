from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from src.config import (
    FREE_SHIPPING_THRESHOLD_EUR,
    HIGH_CONFIDENCE_R2,
    LOW_CONFIDENCE_R2,
    MIN_ORDER_SURCHARGE_EUR,
    MIN_ORDER_VALUE_EUR,
    SAFETY_BUFFER_BUSINESS_DAYS,
    SHIPPING_COST_EUR,
)

RiskLabel = Literal["kritisch", "bald fällig", "beobachten", "niedrig", "unsicher"]


@dataclass
class BundleCostResult:
    bundle_value_eur: float
    total_shipping_eur: float
    total_surcharge_eur: float
    total_cost_eur: float


def _today() -> pd.Timestamp:
    return pd.Timestamp.today().normalize()


def classify_confidence(r2: float | int | None) -> str:
    if r2 is None or pd.isna(r2):
        return "unknown"
    r2 = float(r2)
    if r2 >= HIGH_CONFIDENCE_R2:
        return "high"
    if r2 >= LOW_CONFIDENCE_R2:
        return "medium"
    return "low"


def classify_risk(
    days_left: float | int | None,
    safe_order_date: pd.Timestamp | pd.NaT,
    confidence: str,
) -> RiskLabel:
    today = _today()

    if days_left is None or pd.isna(days_left):
        return "unsicher"

    days_left = float(days_left)

    if confidence == "low":
        return "unsicher"

    if pd.notna(safe_order_date) and pd.Timestamp(safe_order_date).normalize() <= today:
        return "kritisch"

    if days_left <= 3:
        return "kritisch"
    if days_left <= 7:
        return "bald fällig"
    if days_left <= 14:
        return "beobachten"
    return "niedrig"


def enrich_latest_snapshot(latest_snapshot: pd.DataFrame, pricing: pd.DataFrame) -> pd.DataFrame:
    if latest_snapshot.empty:
        return latest_snapshot.copy()

    df = latest_snapshot.copy()

    if not pricing.empty and "part_number" in df.columns and "part_number" in pricing.columns:
        pricing_cols = [
            c for c in [
                "part_number",
                "price_per_meter_eur",
                "delivery_time_days",
                "packaging_unit_m",
                "product_name",
            ]
            if c in pricing.columns
        ]
        pricing_dedup = pricing[pricing_cols].drop_duplicates(subset=["part_number"])
        df = df.merge(pricing_dedup, on="part_number", how="left", suffixes=("", "_pricing"))

    current_length = pd.to_numeric(df.get("daily_avg_cable_length_m"), errors="coerce")
    depletion_rate = pd.to_numeric(df.get("depletion_rate_m_per_day"), errors="coerce")
    order_threshold = pd.to_numeric(df.get("order_threshold_m"), errors="coerce")
    r2 = pd.to_numeric(df.get("r_squared"), errors="coerce")

    delivery_days = pd.to_numeric(df.get("delivery_time_days"), errors="coerce").fillna(3)
    packaging_unit = pd.to_numeric(df.get("packaging_unit_m"), errors="coerce").fillna(100)
    price_per_meter = pd.to_numeric(df.get("price_per_meter_eur"), errors="coerce").fillna(0.0)
    initial_length = pd.to_numeric(df.get("initial_cable_length_m"), errors="coerce").fillna(0)

    # Defensive cleaning
    current_length = current_length.clip(lower=0)
    order_threshold = order_threshold.clip(lower=0)
    delivery_days = delivery_days.clip(lower=1)
    packaging_unit = packaging_unit.clip(lower=1)
    initial_length = initial_length.clip(lower=0)

    valid_rate = depletion_rate.notna() & (depletion_rate > 0)

    days_left = pd.Series(np.nan, index=df.index, dtype="float64")
    threshold_days_left = pd.Series(np.nan, index=df.index, dtype="float64")

    days_left.loc[valid_rate] = current_length.loc[valid_rate] / depletion_rate.loc[valid_rate]
    threshold_days_left.loc[valid_rate] = (
        (current_length.loc[valid_rate] - order_threshold.loc[valid_rate]).clip(lower=0)
        / depletion_rate.loc[valid_rate]
    )

    today = _today()
    predicted_empty_date = today + pd.to_timedelta(days_left, unit="D")
    predicted_threshold_date = today + pd.to_timedelta(threshold_days_left, unit="D")

    safe_order_dates: list[pd.Timestamp | pd.NaT] = []
    for empty_dt, lt in zip(predicted_empty_date, delivery_days, strict=False):
        if pd.isna(empty_dt):
            safe_order_dates.append(pd.NaT)
            continue
        offset_days = int(np.ceil(float(lt))) + SAFETY_BUFFER_BUSINESS_DAYS
        safe_order_dates.append(pd.Timestamp(empty_dt) - BDay(offset_days))

    reorder_qty_m = np.maximum(initial_length, packaging_unit)
    reorder_qty_m = np.ceil(reorder_qty_m / packaging_unit) * packaging_unit
    estimated_order_value = reorder_qty_m * price_per_meter

    df["current_length_m"] = current_length.round(2)
    df["days_left"] = days_left.round(2)
    df["predicted_empty_date"] = pd.to_datetime(predicted_empty_date).dt.normalize()
    df["predicted_threshold_date"] = pd.to_datetime(predicted_threshold_date).dt.normalize()
    df["latest_safe_order_date"] = pd.to_datetime(safe_order_dates)
    df["reorder_qty_m"] = reorder_qty_m.round(0)
    df["estimated_order_value_eur"] = estimated_order_value.round(2)
    df["forecast_confidence"] = r2.apply(classify_confidence)
    df["risk_label"] = [
        classify_risk(dl, sod, conf)
        for dl, sod, conf in zip(
            df["days_left"],
            df["latest_safe_order_date"],
            df["forecast_confidence"],
            strict=False,
        )
    ]
    df["needs_attention"] = df["risk_label"].isin(["kritisch", "bald fällig", "unsicher"])

    return df


def filter_critical_drums(df: pd.DataFrame, horizon_days: int = 7) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()
    horizon_date = _today() + pd.Timedelta(days=horizon_days)

    cond = out["days_left"].fillna(9999) <= horizon_days
    cond |= out["latest_safe_order_date"].notna() & (
        pd.to_datetime(out["latest_safe_order_date"]).dt.normalize() <= horizon_date
    )
    cond |= out["forecast_confidence"].isin(["low", "unknown"])

    out = out.loc[cond].sort_values(
        ["latest_safe_order_date", "days_left", "estimated_order_value_eur"],
        ascending=[True, True, False],
        na_position="last",
    )
    return out


def compute_cost_components(order_values: pd.Series) -> BundleCostResult:
    total_value = float(order_values.fillna(0.0).sum())
    shipping = 0.0 if total_value >= FREE_SHIPPING_THRESHOLD_EUR else SHIPPING_COST_EUR
    surcharge = MIN_ORDER_SURCHARGE_EUR if total_value < MIN_ORDER_VALUE_EUR else 0.0

    return BundleCostResult(
        bundle_value_eur=round(total_value, 2),
        total_shipping_eur=round(shipping, 2),
        total_surcharge_eur=round(surcharge, 2),
        total_cost_eur=round(total_value + shipping + surcharge, 2),
    )


def compare_individual_vs_bundle(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {
            "individual_total_eur": 0.0,
            "bundle_total_eur": 0.0,
            "savings_eur": 0.0,
            "bundle_value_eur": 0.0,
            "bundle_shipping_eur": 0.0,
            "bundle_surcharge_eur": 0.0,
        }

    individual_total = 0.0
    for value in df["estimated_order_value_eur"].fillna(0.0):
        one = compute_cost_components(pd.Series([value]))
        individual_total += one.total_cost_eur

    bundle = compute_cost_components(df["estimated_order_value_eur"])
    return {
        "individual_total_eur": round(individual_total, 2),
        "bundle_total_eur": bundle.total_cost_eur,
        "savings_eur": round(individual_total - bundle.total_cost_eur, 2),
        "bundle_value_eur": bundle.bundle_value_eur,
        "bundle_shipping_eur": bundle.total_shipping_eur,
        "bundle_surcharge_eur": bundle.total_surcharge_eur,
    }


def build_kpis(df: pd.DataFrame) -> dict[str, float | int]:
    if df.empty:
        return {
            "drums": 0,
            "critical": 0,
            "attention": 0,
            "avg_days_left": 0.0,
            "high_confidence_share": 0.0,
        }

    return {
        "drums": int(df["drum_id"].nunique()) if "drum_id" in df.columns else len(df),
        "critical": int(df["risk_label"].eq("kritisch").sum()),
        "attention": int(df["needs_attention"].sum()),
        "avg_days_left": round(float(df["days_left"].dropna().mean()), 1) if df["days_left"].notna().any() else 0.0,
        "high_confidence_share": round(float(df["forecast_confidence"].eq("high").mean() * 100), 1),
    }