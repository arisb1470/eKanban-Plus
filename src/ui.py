from __future__ import annotations

from typing import Any
import html

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
    "attention_reason": "Grund für Handlungsbedarf",
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
        :root {
            --app-bg: #f4f7fb;
            --app-surface: #ffffff;
            --app-surface-soft: #f8fbff;
            --app-surface-strong: #eaf2ff;
            --app-border: #d7e2f0;
            --app-text: #0f172a;
            --app-muted: #475569;
            --app-primary: #2563eb;
            --app-primary-dark: #1d4ed8;
            --app-primary-soft: #dbeafe;
            --app-success-bg: #dcfce7;
            --app-success-text: #166534;
            --app-warning-bg: #fef3c7;
            --app-warning-text: #92400e;
            --app-danger-bg: #fee2e2;
            --app-danger-text: #991b1b;
            --app-info-bg: #e0f2fe;
            --app-info-text: #0f4c81;
            --shadow-soft: 0 14px 40px rgba(15, 23, 42, 0.08);
        }

        html, body, [class*="css"] {
            color: var(--app-text);
        }

        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background:
                radial-gradient(circle at top right, rgba(37, 99, 235, 0.10), transparent 24%),
                radial-gradient(circle at top left, rgba(14, 165, 233, 0.08), transparent 26%),
                linear-gradient(180deg, #f9fbff 0%, var(--app-bg) 100%);
            color: var(--app-text);
        }

        .block-container {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 2.5rem;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
            border-right: 1px solid var(--app-border);
        }

        [data-testid="stSidebar"] * {
            color: var(--app-text);
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--app-text);
            letter-spacing: -0.02em;
        }

        p, li, label, .stCaption, .stMarkdown, .stText, small {
            color: var(--app-muted);
        }

        .app-hero {
            background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(239,246,255,0.98) 100%);
            border: 1px solid rgba(37, 99, 235, 0.16);
            border-radius: 26px;
            padding: 1.4rem 1.6rem;
            margin: 0 0 1.15rem 0;
            box-shadow: var(--shadow-soft);
        }

        .app-hero__top {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: center;
            margin-bottom: 0.65rem;
            flex-wrap: wrap;
        }

        .app-hero h1 {
            margin: 0;
            color: var(--app-text);
            font-size: clamp(1.7rem, 2.3vw, 2.45rem);
            line-height: 1.1;
        }

        .app-hero p {
            margin: 0.55rem 0 0 0;
            color: var(--app-muted);
            font-size: 1rem;
            line-height: 1.55;
            max-width: 62rem;
        }

        .app-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.36rem 0.72rem;
            border-radius: 999px;
            background: var(--app-primary-soft);
            color: #1e3a8a;
            font-size: 0.84rem;
            font-weight: 700;
            border: 1px solid rgba(37, 99, 235, 0.14);
        }

        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            border: 1px solid var(--app-border);
            border-radius: 22px;
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--app-muted) !important;
            font-weight: 600;
        }

        div[data-testid="stMetricValue"] {
            color: var(--app-text) !important;
            font-weight: 750;
        }

        div[data-testid="stMetricDelta"] {
            color: var(--app-primary-dark) !important;
            font-weight: 650;
        }

        .stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            border: none;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--app-primary) 0%, var(--app-primary-dark) 100%);
            color: #ffffff;
            font-weight: 700;
            box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
        }

        .stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
            color: #ffffff;
        }

        .stButton > button:focus,
        div[data-testid="stFormSubmitButton"] > button:focus,
        .stButton > button:focus-visible,
        div[data-testid="stFormSubmitButton"] > button:focus-visible {
            outline: 3px solid rgba(37, 99, 235, 0.22);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
        }

        div[data-baseweb="select"] > div,
        .stTextInput > div > div > input,
        .stNumberInput input,
        .stDateInput input,
        textarea,
        .stSlider [data-baseweb="slider"] {
            background: rgba(255, 255, 255, 0.96) !important;
            color: var(--app-text) !important;
            border-color: var(--app-border) !important;
        }

        div[data-baseweb="select"] * ,
        .stTextInput input,
        textarea,
        .stNumberInput input,
        .stDateInput input {
            color: var(--app-text) !important;
        }

        .stTabs [role="tablist"] {
            gap: 0.4rem;
        }

        .stTabs [role="tab"] {
            border-radius: 999px;
            padding: 0.45rem 0.9rem;
            border: 1px solid var(--app-border);
            background: rgba(255,255,255,0.8);
            color: var(--app-muted);
        }

        .stTabs [aria-selected="true"] {
            background: var(--app-primary-soft) !important;
            color: #1e3a8a !important;
            border-color: rgba(37, 99, 235, 0.24) !important;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid var(--app-border);
            border-radius: 18px;
            overflow: hidden;
            background: rgba(255,255,255,0.95);
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
        }

        div[data-testid="stDataFrame"] thead tr th {
            background: #eff6ff !important;
            color: #1e3a8a !important;
            font-weight: 700 !important;
            border-bottom: 1px solid rgba(37, 99, 235, 0.14);
        }

        div[data-testid="stDataFrame"] tbody tr:nth-child(even) {
            background: rgba(248, 250, 252, 0.85);
        }

        div[data-testid="stDataFrame"] tbody tr:hover {
            background: rgba(219, 234, 254, 0.65) !important;
        }

        div[data-testid="stDataFrame"] tbody td {
            color: var(--app-text) !important;
        }

        [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] p {
            margin-bottom: 0;
        }

        [data-testid="stAlertContainer"] {
            border-radius: 18px;
        }

        [data-baseweb="notification"] {
            border-radius: 18px !important;
            border: 1px solid var(--app-border) !important;
            background: rgba(255, 255, 255, 0.94) !important;
        }

        .stSuccess [data-baseweb="notification"] {
            background: linear-gradient(180deg, #f3fff7 0%, #ebfff2 100%) !important;
        }

        .stInfo [data-baseweb="notification"] {
            background: linear-gradient(180deg, #f2fbff 0%, #eaf7ff 100%) !important;
        }

        .stWarning [data-baseweb="notification"] {
            background: linear-gradient(180deg, #fffaf0 0%, #fff5dd 100%) !important;
        }

        .stError [data-baseweb="notification"] {
            background: linear-gradient(180deg, #fff5f5 0%, #ffeded 100%) !important;
        }

        details {
            background: rgba(255,255,255,0.9);
            border: 1px solid var(--app-border);
            border-radius: 18px;
            padding: 0.3rem 0.8rem;
        }

        details summary {
            color: var(--app-text);
            font-weight: 700;
        }

        [data-testid="stChatMessage"] {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(215, 226, 240, 0.9);
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
        }

        hr {
            border-color: rgba(148, 163, 184, 0.22);
        }

        a {
            color: var(--app-primary-dark);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, badge: str | None = None) -> None:
    badge_html = ""
    if badge:
        badge_html = f'<span class="app-badge">{html.escape(badge)}</span>'

    st.markdown(
        f"""
        <section class="app-hero">
            <div class="app-hero__top">{badge_html}</div>
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
        </section>
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
        return "background-color: #fee2e2; color: #991b1b; font-weight: 700;"
    if text == "bald fällig":
        return "background-color: #ffedd5; color: #9a3412; font-weight: 700;"
    if text == "beobachten":
        return "background-color: #fef3c7; color: #92400e; font-weight: 700;"
    if text == "unsicher":
        return "background-color: #f3e8ff; color: #6b21a8; font-weight: 700;"
    if text == "niedrig":
        return "background-color: #dcfce7; color: #166534; font-weight: 700;"
    return ""


def _highlight_status(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "ok":
        return "background-color: #dcfce7; color: #166534; font-weight: 700;"
    if "niedrige prognosesicherheit" in text:
        return "background-color: #fef3c7; color: #92400e; font-weight: 700;"
    if "keine" in text or "kein" in text:
        return "background-color: #f3e8ff; color: #6b21a8; font-weight: 700;"
    return ""


def _highlight_confidence(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "hoch":
        return "background-color: #dcfce7; color: #166534; font-weight: 700;"
    if text == "mittel":
        return "background-color: #fef3c7; color: #92400e; font-weight: 700;"
    if text == "niedrig":
        return "background-color: #fee2e2; color: #991b1b; font-weight: 700;"
    if text == "unbekannt":
        return "background-color: #e2e8f0; color: #334155; font-weight: 700;"
    return ""


def _highlight_priority(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "hoch":
        return "background-color: #fee2e2; color: #991b1b; font-weight: 700;"
    if text == "mittel":
        return "background-color: #fef3c7; color: #92400e; font-weight: 700;"
    if text == "niedrig":
        return "background-color: #dcfce7; color: #166534; font-weight: 700;"
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