from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.analytics import display_snapshot

COLUMN_LABELS: dict[str, str] = {
    "bundle_cutting_eur": "Schnittkosten Bündel",
    "bundle_id": "Bündel-ID",
    "bundle_shipping_eur": "Versand Bündel",
    "bundle_surcharge_eur": "Mindermengenzuschlag Bündel",
    "bundle_total_eur": "Kosten gebündelt",
    "bundle_value_eur": "Materialwert Bündel",
    "current_length_m": "Aktueller Bestand",
    "cutting_cost_eur": "Schnittkosten",
    "data_age_days": "Datenalter",
    "date": "Messdatum",
    "delivery_time_days": "Lieferzeit",
    "drum_count": "Anzahl Trommeln",
    "drum_id": "Trommel",
    "drum_ids": "Trommeln im Bündel",
    "days_left": "Restreichweite",
    "estimated_order_value_eur": "Bestellwert gesamt",
    "forecast_confidence": "Prognosegüte",
    "forecast_status": "Prognosestatus",
    "has_low_sensor_coverage": "Geringe Sensordichte",
    "has_weak_battery": "Batterie schwach",
    "has_weak_signal": "Signal schwach",
    "individual_total_eur": "Kosten einzeln",
    "initial_cable_length_m": "Anfangsbestand",
    "is_stale_data": "Historische Daten",
    "latest_due_date": "Späteste Fälligkeit",
    "latest_safe_order_date": "Spätester Bestelltermin",
    "material_order_value_eur": "Materialwert",
    "order_threshold_m": "Meldebestand",
    "packaging_unit_m": "Verpackungseinheit",
    "part_number": "Artikelnummer",
    "predicted_empty_date": "Voraussichtlich leer am",
    "predicted_threshold_date": "Meldebestand erreicht am",
    "price_per_meter_eur": "Preis pro Meter",
    "priority": "Priorität",
    "product": "Produkt",
    "product_name": "Produktname",
    "rack": "Regal / Bereich",
    "recommended_order_date": "Empfohlener Bestelltermin",
    "reorder_qty_m": "Bestellmenge",
    "review_reason": "Prüfgrund",
    "risk_label": "Risikostatus",
    "r_squared": "R²",
    "sensor_readings_count": "Sensorwerte",
    "snapshot_as_of_date": "Datenstand",
    "avg_battery_voltage": "Batteriespannung",
    "avg_signal_strength": "Signalstärke",
    "telemetry_issue": "Telemetrieproblem",
    "tenant": "Kunde",
}

VALUE_LABELS: dict[str, dict[Any, Any]] = {
    "forecast_confidence": {
        "high": "hoch",
        "medium": "mittel",
        "low": "niedrig",
        "unknown": "unbekannt",
    },
    "priority": {
        "high": "hoch",
        "medium": "mittel",
        "low": "niedrig",
    },
    "telemetry_issue": {True: "Ja", False: "Nein"},
    "has_low_sensor_coverage": {True: "Ja", False: "Nein"},
    "has_weak_battery": {True: "Ja", False: "Nein"},
    "has_weak_signal": {True: "Ja", False: "Nein"},
    "is_stale_data": {True: "Ja", False: "Nein"},
}

DATE_COLUMNS = {
    "date",
    "predicted_empty_date",
    "predicted_threshold_date",
    "latest_safe_order_date",
    "recommended_order_date",
    "latest_due_date",
    "snapshot_as_of_date",
}

METER_COLUMNS = {
    "current_length_m",
    "initial_cable_length_m",
    "order_threshold_m",
    "packaging_unit_m",
    "reorder_qty_m",
}

CURRENCY_COLUMNS = {
    "bundle_cutting_eur",
    "bundle_shipping_eur",
    "bundle_surcharge_eur",
    "bundle_total_eur",
    "bundle_value_eur",
    "cutting_cost_eur",
    "estimated_order_value_eur",
    "individual_total_eur",
    "material_order_value_eur",
    "price_per_meter_eur",
    "savings_eur",
}

DECIMAL_COLUMNS = {"days_left", "delivery_time_days", "r_squared"}
INTEGER_COLUMNS = {"drum_count", "sensor_readings_count", "data_age_days", "drum_id"}
MV_COLUMNS = {"avg_battery_voltage"}
DBM_COLUMNS = {"avg_signal_strength"}


def apply_app_styles() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(120, 120, 140, 0.18);
            border-radius: 14px;
            overflow: hidden;
        }
        div[data-testid="stDataFrame"] thead tr th {
            background: rgba(59, 130, 246, 0.10);
            font-weight: 600;
        }
        div[data-testid="stDataFrame"] tbody tr:nth-child(even) {
            background: rgba(255, 255, 255, 0.015);
        }
        div[data-testid="stDataFrame"] tbody tr:hover {
            background: rgba(59, 130, 246, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def label_for(column: str) -> str:
    return COLUMN_LABELS.get(column, column)


def _is_missing(value: Any) -> bool:
    return value is None or (not isinstance(value, str) and pd.isna(value)) or value == ""


def _format_number(value: Any, digits: int = 1, suffix: str = "") -> str:
    if _is_missing(value) or value == "—":
        return "—"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in {"—", "kein aktueller Verbrauch", "keine Daten", "unbekannt"}:
            return stripped
        try:
            value = float(stripped.replace(".", "").replace(",", "."))
        except ValueError:
            return stripped
    number = float(value)
    formatted = f"{number:,.{digits}f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted}{suffix}"


def _format_integer(value: Any, suffix: str = "", grouped: bool = True) -> str:
    if _is_missing(value) or value == "—":
        return "—"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "—":
            return stripped
        try:
            value = int(float(stripped.replace(".", "").replace(",", ".")))
        except ValueError:
            return stripped
    number = int(round(float(value)))
    rendered = f"{number:,}".replace(",", ".") if grouped else str(number)
    return rendered + suffix


def _format_date(value: Any) -> str:
    if _is_missing(value) or value == "—":
        return "—"
    try:
        return pd.Timestamp(value).strftime("%d.%m.%Y")
    except Exception:
        return str(value)


def _translate_value(column: str, value: Any) -> Any:
    mapping = VALUE_LABELS.get(column, {})
    return mapping.get(value, value)


def format_value(column: str, value: Any) -> Any:
    value = _translate_value(column, value)

    if column in DATE_COLUMNS:
        return _format_date(value)
    if column in CURRENCY_COLUMNS:
        return _format_number(value, digits=2, suffix=" €")
    if column in METER_COLUMNS:
        return _format_number(value, digits=1, suffix=" m")
    if column in DECIMAL_COLUMNS:
        suffix = " Tage" if column == "days_left" else ""
        return _format_number(value, digits=1, suffix=suffix)
    if column in INTEGER_COLUMNS:
        return _format_integer(value, grouped=column != "drum_id")
    if column in MV_COLUMNS:
        return _format_integer(value, suffix=" mV")
    if column in DBM_COLUMNS:
        return _format_integer(value, suffix=" dBm")
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    if _is_missing(value):
        return "—"
    return value


def format_table(df: pd.DataFrame, prepare: bool = True) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = display_snapshot(df.copy()) if prepare else df.copy()

    for column in out.columns:
        out[column] = out[column].apply(lambda value, c=column: format_value(c, value))

    out = out.rename(columns={column: label_for(column) for column in out.columns})
    return out


def _highlight_risk(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "kritisch":
        return "background-color: rgba(239, 68, 68, 0.20); font-weight: 600;"
    if text == "bald fällig":
        return "background-color: rgba(249, 115, 22, 0.18); font-weight: 600;"
    if text == "beobachten":
        return "background-color: rgba(245, 158, 11, 0.16); font-weight: 600;"
    if text == "unsicher":
        return "background-color: rgba(168, 85, 247, 0.16); font-weight: 600;"
    if text == "niedrig":
        return "background-color: rgba(34, 197, 94, 0.16); font-weight: 600;"
    return ""


def _highlight_status(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "ok":
        return "background-color: rgba(34, 197, 94, 0.14); font-weight: 600;"
    if "niedrige prognosesicherheit" in text:
        return "background-color: rgba(245, 158, 11, 0.16); font-weight: 600;"
    if "keine" in text or "kein" in text:
        return "background-color: rgba(168, 85, 247, 0.14); font-weight: 600;"
    return ""


def _highlight_confidence(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "hoch":
        return "background-color: rgba(34, 197, 94, 0.14); font-weight: 600;"
    if text == "mittel":
        return "background-color: rgba(245, 158, 11, 0.16); font-weight: 600;"
    if text == "niedrig":
        return "background-color: rgba(239, 68, 68, 0.16); font-weight: 600;"
    if text == "unbekannt":
        return "background-color: rgba(148, 163, 184, 0.16); font-weight: 600;"
    return ""


def _highlight_priority(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "hoch":
        return "background-color: rgba(239, 68, 68, 0.20); font-weight: 600;"
    if text == "mittel":
        return "background-color: rgba(245, 158, 11, 0.16); font-weight: 600;"
    if text == "niedrig":
        return "background-color: rgba(34, 197, 94, 0.14); font-weight: 600;"
    return ""


def _build_styler(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    styler = df.style
    styler = styler.set_properties(**{"white-space": "normal"})

    if "Risikostatus" in df.columns:
        styler = styler.applymap(_highlight_risk, subset=["Risikostatus"])
    if "Prognosestatus" in df.columns:
        styler = styler.applymap(_highlight_status, subset=["Prognosestatus"])
    if "Prognosegüte" in df.columns:
        styler = styler.applymap(_highlight_confidence, subset=["Prognosegüte"])
    if "Priorität" in df.columns:
        styler = styler.applymap(_highlight_priority, subset=["Priorität"])

    return styler


def render_table(df: pd.DataFrame, *, prepare: bool = True, height: int | str | None = None) -> None:
    if df.empty:
        st.info("Keine Daten vorhanden.")
        return

    formatted = format_table(df, prepare=prepare)

    dataframe_kwargs = {
        "width": "stretch",
        "hide_index": True,
    }

    if height is not None:
        dataframe_kwargs["height"] = height

    st.dataframe(_build_styler(formatted), **dataframe_kwargs)