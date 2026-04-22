from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from src.config import (
    CUTTING_COST_EUR,
    FREE_SHIPPING_THRESHOLD_EUR,
    HIGH_CONFIDENCE_R2,
    LOW_CONFIDENCE_R2,
    MIN_ORDER_SURCHARGE_EUR,
    MIN_ORDER_VALUE_EUR,
    MIN_SENSOR_READINGS_PER_DAY,
    SAFETY_BUFFER_BUSINESS_DAYS,
    SHIPPING_COST_EUR,
    STALE_DATA_WARNING_DAYS,
    STANDARD_CUT_LENGTHS_M,
    WEAK_BATTERY_VOLTAGE_MV,
    WEAK_SIGNAL_STRENGTH_DBM,
)

RiskLabel = Literal["kritisch", "hoch", "mittel", "gut", "unsicher"]
ForecastStatus = Literal[
    "ok",
    "niedrige Prognosesicherheit",
    "kein aktueller Verbrauch",
    "keine Verbrauchsdaten",
    "keine Prognosegüte",
]


@dataclass
class BundleCostResult:
    bundle_value_eur: float
    total_cutting_eur: float
    total_shipping_eur: float
    total_surcharge_eur: float
    total_cost_eur: float


def _today() -> pd.Timestamp:
    return pd.Timestamp.today().normalize()


def get_snapshot_as_of(df: pd.DataFrame) -> pd.Timestamp:
    if df.empty or "date" not in df.columns:
        return _today()

    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        return _today()
    return pd.Timestamp(dates.max()).normalize()


def get_data_freshness(df: pd.DataFrame, warning_days: int = STALE_DATA_WARNING_DAYS) -> dict[str, object]:
    as_of_date = get_snapshot_as_of(df)
    age_days = int((_today() - as_of_date).days)
    return {
        "as_of_date": as_of_date,
        "age_days": age_days,
        "is_stale": age_days > warning_days,
        "warning_days": warning_days,
    }


def classify_confidence(r2: float | int | None) -> str:
    if r2 is None or pd.isna(r2):
        return "unknown"
    r2 = float(r2)
    if r2 >= HIGH_CONFIDENCE_R2:
        return "high"
    if r2 >= LOW_CONFIDENCE_R2:
        return "medium"
    return "low"


def classify_forecast_status(
    depletion_rate: float | int | None,
    confidence: str,
) -> ForecastStatus:
    if depletion_rate is None or pd.isna(depletion_rate):
        return "keine Verbrauchsdaten"

    depletion_rate = float(depletion_rate)
    if depletion_rate <= 0:
        return "kein aktueller Verbrauch"

    if confidence == "low":
        return "niedrige Prognosesicherheit"
    if confidence == "unknown":
        return "keine Prognosegüte"
    return "ok"


def classify_risk(
    days_left: float | int | None,
    safe_order_date: pd.Timestamp | pd.NaT,
    forecast_status: ForecastStatus,
    reference_date: pd.Timestamp,
) -> RiskLabel:
    severity_rank = {"gut": 0, "mittel": 1, "hoch": 2, "kritisch": 3}
    risk: RiskLabel = "gut"

    if pd.notna(safe_order_date):
        days_until_safe_order = int((pd.Timestamp(safe_order_date).normalize() - reference_date).days)
        if days_until_safe_order <= 0:
            risk = "kritisch"
        elif days_until_safe_order <= 7:
            risk = "hoch"
        elif days_until_safe_order <= 30:
            risk = "mittel"

    if days_left is not None and pd.notna(days_left):
        days_left = float(days_left)
        candidate: RiskLabel = "gut"
        if days_left <= 3:
            candidate = "kritisch"
        elif days_left <= 7:
            candidate = "hoch"
        elif days_left <= 14:
            candidate = "mittel"

        if severity_rank[candidate] > severity_rank[risk]:
            risk = candidate

    if risk != "gut":
        return risk

    if forecast_status in {
        "niedrige Prognosesicherheit",
        "keine Prognosegüte",
        "keine Verbrauchsdaten",
        "kein aktueller Verbrauch",
    }:
        return "unsicher"

    return "gut"


def _display_days_left(days_left: float | int | None, forecast_status: str) -> float | str:
    if days_left is not None and pd.notna(days_left):
        return round(float(days_left), 2)
    if forecast_status == "kein aktueller Verbrauch":
        return "kein aktueller Verbrauch"
    if forecast_status == "keine Verbrauchsdaten":
        return "keine Daten"
    return "—"


def _display_date(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    return str(pd.Timestamp(value).normalize().date())


def _build_review_reason(row: pd.Series) -> str:
    reasons: list[str] = []

    status = str(row.get("forecast_status", ""))
    if status and status != "ok":
        reasons.append(status)

    if bool(row.get("has_low_sensor_coverage", False)):
        reasons.append("wenige Sensorwerte")
    if bool(row.get("has_weak_battery", False)):
        reasons.append("Batterie schwach")
    if bool(row.get("has_weak_signal", False)):
        reasons.append("Funksignal schwach")

    if not reasons:
        return "—"

    ordered: list[str] = []
    for reason in reasons:
        if reason not in ordered:
            ordered.append(reason)
    return ", ".join(ordered)


def display_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()

    if "days_left" in out.columns:
        statuses = out.get("forecast_status", pd.Series("", index=out.index, dtype="object"))
        out["days_left"] = [
            _display_days_left(days_left, status)
            for days_left, status in zip(out["days_left"], statuses, strict=False)
        ]

    for col in ["date", "predicted_empty_date", "predicted_threshold_date", "latest_safe_order_date", "snapshot_as_of_date"]:
        if col in out.columns:
            out[col] = out[col].apply(_display_date)

    return out.where(pd.notnull(out), "—")


def enrich_latest_snapshot(latest_snapshot: pd.DataFrame, pricing: pd.DataFrame) -> pd.DataFrame:
    if latest_snapshot.empty:
        return latest_snapshot.copy()

    df = latest_snapshot.copy()

    if not pricing.empty and "part_number" in df.columns and "part_number" in pricing.columns:
        pricing_cols = [
            c
            for c in [
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

    measurement_date = pd.to_datetime(df.get("date"), errors="coerce").dt.normalize()
    current_length = pd.to_numeric(df.get("daily_avg_cable_length_m"), errors="coerce")
    depletion_rate = pd.to_numeric(df.get("depletion_rate_m_per_day"), errors="coerce")
    order_threshold = pd.to_numeric(df.get("order_threshold_m"), errors="coerce")
    r2 = pd.to_numeric(df.get("r_squared"), errors="coerce")
    sensor_readings = pd.to_numeric(df.get("sensor_readings_count"), errors="coerce")
    avg_battery_voltage = pd.to_numeric(df.get("avg_battery_voltage"), errors="coerce")
    avg_signal_strength = pd.to_numeric(df.get("avg_signal_strength"), errors="coerce")

    delivery_days = pd.to_numeric(df.get("delivery_time_days"), errors="coerce").fillna(3)
    packaging_unit = pd.to_numeric(df.get("packaging_unit_m"), errors="coerce").fillna(100)
    price_per_meter = pd.to_numeric(df.get("price_per_meter_eur"), errors="coerce").fillna(0.0)
    initial_length = pd.to_numeric(df.get("initial_cable_length_m"), errors="coerce").fillna(0)

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

    predicted_empty_date = measurement_date + pd.to_timedelta(days_left, unit="D")
    predicted_threshold_date = measurement_date + pd.to_timedelta(threshold_days_left, unit="D")

    safe_order_dates: list[pd.Timestamp | pd.NaT] = []
    for empty_dt, lt in zip(predicted_empty_date, delivery_days, strict=False):
        if pd.isna(empty_dt):
            safe_order_dates.append(pd.NaT)
            continue
        offset_days = int(np.ceil(float(lt))) + SAFETY_BUFFER_BUSINESS_DAYS
        safe_order_dates.append(pd.Timestamp(empty_dt) - BDay(offset_days))

    safe_order_dates = pd.to_datetime(pd.Series(safe_order_dates, index=df.index)).dt.normalize()

    reorder_qty_m = np.maximum(initial_length, packaging_unit)
    reorder_qty_m = np.ceil(reorder_qty_m / packaging_unit) * packaging_unit
    material_order_value = reorder_qty_m * price_per_meter
    cutting_cost = np.where(np.isin(reorder_qty_m, STANDARD_CUT_LENGTHS_M), 0.0, CUTTING_COST_EUR)
    estimated_order_value = material_order_value + cutting_cost

    snapshot_as_of = get_snapshot_as_of(df)
    freshness = get_data_freshness(df)

    forecast_confidence = r2.apply(classify_confidence)
    forecast_status = [
        classify_forecast_status(rate, confidence)
        for rate, confidence in zip(depletion_rate, forecast_confidence, strict=False)
    ]

    has_low_sensor_coverage = sensor_readings.lt(MIN_SENSOR_READINGS_PER_DAY)
    has_weak_battery = avg_battery_voltage.lt(WEAK_BATTERY_VOLTAGE_MV)
    has_weak_signal = avg_signal_strength.lt(WEAK_SIGNAL_STRENGTH_DBM)

    df["current_length_m"] = current_length.round(2)
    df["days_left"] = days_left.round(2)
    df["predicted_empty_date"] = pd.to_datetime(predicted_empty_date).dt.normalize()
    df["predicted_threshold_date"] = pd.to_datetime(predicted_threshold_date).dt.normalize()
    df["latest_safe_order_date"] = safe_order_dates
    df["reorder_qty_m"] = reorder_qty_m.round(0)
    df["material_order_value_eur"] = material_order_value.round(2)
    df["cutting_cost_eur"] = pd.Series(cutting_cost, index=df.index).round(2)
    df["estimated_order_value_eur"] = estimated_order_value.round(2)
    df["forecast_confidence"] = forecast_confidence
    df["forecast_status"] = forecast_status
    df["has_low_sensor_coverage"] = has_low_sensor_coverage.fillna(False)
    df["has_weak_battery"] = has_weak_battery.fillna(False)
    df["has_weak_signal"] = has_weak_signal.fillna(False)
    df["telemetry_issue"] = df[["has_low_sensor_coverage", "has_weak_battery", "has_weak_signal"]].any(axis=1)
    df["snapshot_as_of_date"] = snapshot_as_of
    df["data_age_days"] = freshness["age_days"]
    df["is_stale_data"] = freshness["is_stale"]

    df["risk_label"] = [
        classify_risk(dl, sod, status, reference_date=snapshot_as_of)
        for dl, sod, status in zip(
            df["days_left"],
            df["latest_safe_order_date"],
            df["forecast_status"],
            strict=False,
        )
    ]

    df["needs_attention"] = df["risk_label"].isin(["kritisch", "hoch", "mittel"])
    df["needs_review"] = df["forecast_status"].isin(
        ["niedrige Prognosesicherheit", "keine Prognosegüte", "keine Verbrauchsdaten", "kein aktueller Verbrauch"]
    ) | df["telemetry_issue"]
    df["review_reason"] = df.apply(_build_review_reason, axis=1)

    return df


def filter_critical_drums(df: pd.DataFrame, horizon_days: int = 7) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()
    horizon_date = get_snapshot_as_of(out) + pd.Timedelta(days=horizon_days)

    cond = out["risk_label"].isin(["kritisch", "hoch", "mittel"])
    cond |= out["days_left"].fillna(9999) <= horizon_days
    cond |= out["latest_safe_order_date"].notna() & (
        pd.to_datetime(out["latest_safe_order_date"]).dt.normalize() <= horizon_date
    )

    out = out.loc[cond].sort_values(
        ["latest_safe_order_date", "days_left", "estimated_order_value_eur"],
        ascending=[True, True, False],
        na_position="last",
    )
    return out


def filter_review_drums(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.loc[df["needs_review"]].copy()
    out = out.sort_values(
        ["review_reason", "latest_safe_order_date", "days_left", "estimated_order_value_eur"],
        ascending=[True, True, True, False],
        na_position="last",
    )
    return out


def compute_cost_components(
    material_values: pd.Series,
    cutting_costs: pd.Series | None = None,
) -> BundleCostResult:
    material_total = float(material_values.fillna(0.0).sum())
    cutting_total = float(cutting_costs.fillna(0.0).sum()) if cutting_costs is not None else 0.0
    shipping = 0.0 if material_total >= FREE_SHIPPING_THRESHOLD_EUR else SHIPPING_COST_EUR
    surcharge = MIN_ORDER_SURCHARGE_EUR if material_total < MIN_ORDER_VALUE_EUR else 0.0

    return BundleCostResult(
        bundle_value_eur=round(material_total, 2),
        total_cutting_eur=round(cutting_total, 2),
        total_shipping_eur=round(shipping, 2),
        total_surcharge_eur=round(surcharge, 2),
        total_cost_eur=round(material_total + cutting_total + shipping + surcharge, 2),
    )


def compare_individual_vs_bundle(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {
            "individual_total_eur": 0.0,
            "bundle_total_eur": 0.0,
            "savings_eur": 0.0,
            "bundle_value_eur": 0.0,
            "bundle_cutting_eur": 0.0,
            "bundle_shipping_eur": 0.0,
            "bundle_surcharge_eur": 0.0,
        }

    material_values = df.get("material_order_value_eur", df.get("estimated_order_value_eur", pd.Series(0.0, index=df.index)))
    cutting_costs = df.get("cutting_cost_eur", pd.Series(0.0, index=df.index))

    individual_total = 0.0
    for material_value, cutting_cost in zip(material_values.fillna(0.0), cutting_costs.fillna(0.0), strict=False):
        one = compute_cost_components(pd.Series([material_value]), pd.Series([cutting_cost]))
        individual_total += one.total_cost_eur

    bundle = compute_cost_components(material_values, cutting_costs)
    return {
        "individual_total_eur": round(individual_total, 2),
        "bundle_total_eur": bundle.total_cost_eur,
        "savings_eur": round(individual_total - bundle.total_cost_eur, 2),
        "bundle_value_eur": bundle.bundle_value_eur,
        "bundle_cutting_eur": bundle.total_cutting_eur,
        "bundle_shipping_eur": bundle.total_shipping_eur,
        "bundle_surcharge_eur": bundle.total_surcharge_eur,
    }


def build_kpis(df: pd.DataFrame, attention_horizon_days: int = 7) -> dict[str, float | int]:
    if df.empty:
        return {
            "drums": 0,
            "critical": 0,
            "attention": 0,
            "review": 0,
            "avg_days_left": 0.0,
            "high_confidence_share": 0.0,
        }

    attention_count = len(filter_critical_drums(df, horizon_days=attention_horizon_days))

    return {
        "drums": int(df["drum_id"].nunique()) if "drum_id" in df.columns else len(df),
        "critical": int(df["risk_label"].eq("kritisch").sum()),
        "attention": int(attention_count),
        "review": int(df["needs_review"].sum()),
        "avg_days_left": round(float(df["days_left"].dropna().mean()), 1)
        if df["days_left"].notna().any()
        else 0.0,
        "high_confidence_share": round(float(df["forecast_confidence"].eq("high").mean() * 100), 1),
    }