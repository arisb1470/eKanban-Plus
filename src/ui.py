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
    "current_length_m": "Bestand",
    "cutting_cost_eur": "Schnittkosten",
    "data_age_days": "Datenalter",
    "date": "Messdatum",
    "delivery_time_days": "Lieferzeit",
    "drum_count": "Anzahl Trommeln",
    "drum_id": "Trommel",
    "drum_ids": "Trommeln im Bündel",
    "days_left": "Reichweite",
    "estimated_order_value_eur": "Bestellwert",
    "forecast_confidence": "Prognosegüte",
    "forecast_status": "Prognosestatus",
    "has_low_sensor_coverage": "Geringe Sensordichte",
    "has_weak_battery": "Batterie schwach",
    "has_weak_signal": "Signal schwach",
    "individual_total_eur": "Kosten einzeln",
    "initial_cable_length_m": "Anfangsbestand",
    "is_stale_data": "Historische Daten",
    "latest_due_date": "Späteste Fälligkeit",
    "latest_safe_order_date": "Bestellen bis",
    "material_order_value_eur": "Materialwert",
    "order_threshold_m": "Meldebestand",
    "packaging_unit_m": "Verpackungseinheit",
    "part_number": "Artikelnummer",
    "predicted_empty_date": "Leer am",
    "predicted_threshold_date": "Meldebestand erreicht am",
    "price_per_meter_eur": "Preis pro Meter",
    "priority": "Priorität",
    "product": "Produkt",
    "product_name": "Produktname",
    "rack": "Bereich",
    "recommended_order_date": "Empfohlener Bestelltermin",
    "reorder_qty_m": "Menge",
    "review_reason": "Prüfgrund",
    "risk_label": "Risikostatus",
    "r_squared": "R²",
    "savings_eur": "Einsparung",
    "sensor_readings_count": "Messwerte",
    "snapshot_as_of_date": "Datenstand",
    "avg_battery_voltage": "Batterie",
    "avg_signal_strength": "Signal",
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

STATUS_COLUMNS_AFTER_PRODUCT = [
    "risk_label",
    "forecast_status",
    "forecast_confidence",
    "review_reason",
    "priority",
]

DISPLAY_STATUS_COLUMNS = ["Risikostatus", "Prognosestatus"]

LONG_TEXT_COLUMNS = ["Produkt", "Prüfgrund", "Trommeln im Bündel"]

NARROW_TEXT_COLUMNS = [
    "Trommel",
    "Bereich",
    "Risikostatus",
    "Prognosestatus",
    "Prognosegüte",
    "Priorität",
    "Bestand",
    "Reichweite",
    "Bestellen bis",
    "Leer am",
    "Messwerte",
    "Batterie",
    "Signal",
    "Menge",
    "Bestellwert",
]


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
            background: linear-gradient(135deg, rgba(255,255,255,0.97) 0%, rgba(239,246,255,0.98) 100%);
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

        div[data-baseweb="select"] *,
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
            border: 1px solid rgba(215, 226, 240, 0.95);
            border-radius: 16px;
            overflow: hidden;
            background: rgba(255,255,255,0.98);
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.035);
        }

        div[data-testid="stDataFrame"] table {
            font-size: 0.92rem !important;
        }

        div[data-testid="stDataFrame"] thead tr th {
            background: #f8fbff !important;
            color: #1e3a8a !important;
            font-weight: 700 !important;
            border-bottom: 1px solid rgba(37, 99, 235, 0.10);
            padding: 0.55rem 0.65rem !important;
            white-space: nowrap !important;
        }

        div[data-testid="stDataFrame"] tbody tr:nth-child(even) {
            background: rgba(248, 250, 252, 0.55);
        }

        div[data-testid="stDataFrame"] tbody tr:hover {
            background: rgba(241, 245, 249, 0.85) !important;
        }

        div[data-testid="stDataFrame"] tbody td {
            color: var(--app-text) !important;
            border-bottom: 1px solid rgba(226, 232, 240, 0.65);
            padding: 0.48rem 0.65rem !important;
            line-height: 1.25 !important;
        }

        div[data-testid="stDataFrame"] tbody td p {
            margin: 0 !important;
        }

        [data-baseweb="notification"] {
            border-radius: 18px !important;
            border: 1px solid var(--app-border) !important;
            background: rgba(255, 255, 255, 0.94) !important;
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


def _reorder_status_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    columns = list(df.columns)
    anchor = "product" if "product" in columns else "product_name" if "product_name" in columns else None
    if anchor is None:
        return df.copy()

    movable = [column for column in STATUS_COLUMNS_AFTER_PRODUCT if column in columns and column != anchor]
    if not movable:
        return df.copy()

    reordered: list[str] = []
    inserted = False
    for column in columns:
        if column in movable:
            continue
        reordered.append(column)
        if column == anchor:
            reordered.extend(movable)
            inserted = True

    if not inserted:
        reordered.extend(movable)

    return df.loc[:, reordered]


def format_table(df: pd.DataFrame, prepare: bool = True) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = display_snapshot(df.copy()) if prepare else df.copy()
    out = _reorder_status_columns(out)

    for column in out.columns:
        out[column] = out[column].apply(lambda value, c=column: format_value(c, value))

    out = out.rename(columns={column: label_for(column) for column in out.columns})
    return out


def _palette_for_risk(text: str) -> tuple[str, str] | None:
    text = text.strip().lower()
    if text == "kritisch":
        return "#fee2e2", "#991b1b"
    if text in {"hoch", "bald fällig"}:
        return "#ffedd5", "#9a3412"
    if text in {"mittel", "beobachten"}:
        return "#fef3c7", "#92400e"
    if text == "unsicher":
        return "#f3e8ff", "#6b21a8"
    if text in {"gut", "niedrig"}:
        return "#dcfce7", "#166534"
    return None


def _style_chip(palette: tuple[str, str] | None) -> str:
    if palette is None:
        return ""
    background, color = palette
    return f"background-color: {background}; color: {color}; font-weight: 700;"


def _highlight_risk(value: Any) -> str:
    return _style_chip(_palette_for_risk(str(value)))


def _palette_for_forecast_status(text: str) -> tuple[str, str] | None:
    text = text.strip().lower()
    if text == "ok":
        return "#dcfce7", "#166534"
    if "niedrige prognosesicherheit" in text:
        return "#fef3c7", "#92400e"
    if "keine prognosegüte" in text:
        return "#ede9fe", "#5b21b6"
    if "keine verbrauchsdaten" in text:
        return "#e2e8f0", "#334155"
    if "kein aktueller verbrauch" in text:
        return "#e0f2fe", "#0f4c81"
    return None


def _highlight_status(value: Any) -> str:
    return _style_chip(_palette_for_forecast_status(str(value)))


def _highlight_confidence(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "hoch":
        return _style_chip(("#dcfce7", "#166534"))
    if text == "mittel":
        return _style_chip(("#fef3c7", "#92400e"))
    if text == "niedrig":
        return _style_chip(("#fee2e2", "#991b1b"))
    if text == "unbekannt":
        return _style_chip(("#e2e8f0", "#334155"))
    return ""


def _highlight_priority(value: Any) -> str:
    text = str(value).strip().lower()
    if text == "hoch":
        return _style_chip(("#fee2e2", "#991b1b"))
    if text == "mittel":
        return _style_chip(("#fef3c7", "#92400e"))
    if text == "niedrig":
        return _style_chip(("#dcfce7", "#166534"))
    return ""


def _palette_for_review_reason(text: str) -> tuple[str, str] | None:
    value = text.strip().lower()

    if not value or value == "—":
        return None

    if "batterie schwach" in value:
        return "#f8fafc", "#334155"
    if "funksignal schwach" in value:
        return "#eff6ff", "#1d4ed8"
    if "wenige sensorwerte" in value:
        return "#f8fafc", "#475569"
    if "niedrige prognosesicherheit" in value:
        return "#f8fafc", "#475569"
    if "keine prognosegüte" in value:
        return "#f5f3ff", "#6d28d9"
    if "keine verbrauchsdaten" in value:
        return "#f1f5f9", "#334155"
    if "kein aktueller verbrauch" in value:
        return "#eef2ff", "#4338ca"

    return "#f8fafc", "#475569"


def _highlight_review_reason(value: Any) -> str:
    return _style_chip(_palette_for_review_reason(str(value)))


def _row_band_palette(row: pd.Series) -> tuple[str, str] | None:
    risk_palette = _palette_for_risk(str(row.get("Risikostatus", "")))
    if risk_palette is not None:
        return risk_palette

    forecast_palette = _palette_for_forecast_status(str(row.get("Prognosestatus", "")))
    if forecast_palette is not None:
        return forecast_palette

    return None


def _highlight_status_band(row: pd.Series) -> list[str]:
    styles = [""] * len(row)
    status_positions = [idx for idx, column in enumerate(row.index) if column in DISPLAY_STATUS_COLUMNS]
    if not status_positions:
        return styles

    palette = _row_band_palette(row)
    if palette is None:
        return styles

    background, color = palette
    band_style = f"background-color: {background}; color: {color};"
    for idx in range(max(status_positions) + 1):
        styles[idx] = band_style

    return styles


def _build_styler(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    styler = df.style
    styler = styler.set_table_styles(
        [
            {"selector": "th", "props": [("font-size", "0.92rem"), ("padding", "8px 10px"), ("white-space", "nowrap")]},
            {"selector": "td", "props": [("font-size", "0.91rem"), ("padding", "7px 10px"), ("line-height", "1.25")]},
        ],
        overwrite=False,
    )
    styler = styler.set_properties(**{"white-space": "normal", "vertical-align": "middle"})

    numeric_labels = {
        label_for(column)
        for column in (CURRENCY_COLUMNS | METER_COLUMNS | DECIMAL_COLUMNS | INTEGER_COLUMNS | MV_COLUMNS | DBM_COLUMNS)
    }
    numeric_columns = [column for column in df.columns if column in numeric_labels]
    if numeric_columns:
        styler = styler.set_properties(subset=numeric_columns, **{"text-align": "right", "white-space": "nowrap"})

    centered_columns = [column for column in ["Risikostatus", "Prognosestatus", "Prognosegüte", "Priorität"] if column in df.columns]
    if centered_columns:
        styler = styler.set_properties(subset=centered_columns, **{"text-align": "center", "white-space": "nowrap"})

    long_columns = [column for column in LONG_TEXT_COLUMNS if column in df.columns]
    if long_columns:
        styler = styler.set_properties(subset=long_columns, **{"min-width": "14rem", "max-width": "24rem"})

    narrow_columns = [column for column in NARROW_TEXT_COLUMNS if column in df.columns]
    if narrow_columns:
        styler = styler.set_properties(subset=narrow_columns, **{"white-space": "nowrap"})

    if "Produkt" in df.columns:
        styler = styler.set_properties(subset=["Produkt"], **{"font-weight": "600"})

    if any(column in df.columns for column in DISPLAY_STATUS_COLUMNS):
        styler = styler.apply(_highlight_status_band, axis=1)

    if "Risikostatus" in df.columns:
        styler = styler.applymap(_highlight_risk, subset=["Risikostatus"])
    if "Prognosestatus" in df.columns:
        styler = styler.applymap(_highlight_status, subset=["Prognosestatus"])
    if "Prognosegüte" in df.columns:
        styler = styler.applymap(_highlight_confidence, subset=["Prognosegüte"])
    if "Priorität" in df.columns:
        styler = styler.applymap(_highlight_priority, subset=["Priorität"])
    if "Prüfgrund" in df.columns:
        styler = styler.applymap(_highlight_review_reason, subset=["Prüfgrund"])

    return styler


def _build_column_config(df: pd.DataFrame) -> dict[str, Any]:
    width_map = {
        "Trommel": "small",
        "Bereich": "small",
        "Produkt": "large",
        "Risikostatus": "small",
        "Prognosestatus": "medium",
        "Prognosegüte": "small",
        "Priorität": "small",
        "Prüfgrund": "large",
        "Bestand": "small",
        "Reichweite": "small",
        "Bestellen bis": "small",
        "Leer am": "small",
        "Messwerte": "small",
        "Batterie": "small",
        "Signal": "small",
        "Menge": "small",
        "Bestellwert": "small",
        "Trommeln im Bündel": "medium",
    }

    config: dict[str, Any] = {}
    for column, width in width_map.items():
        if column in df.columns:
            config[column] = st.column_config.TextColumn(column, width=width)

    return config


def render_table(df: pd.DataFrame, *, prepare: bool = True, height: int | None = None) -> None:
    if df.empty:
        st.info("Keine Daten vorhanden.")
        return

    formatted = format_table(df, prepare=prepare)

    resolved_height = height
    if resolved_height is None:
        visible_rows = min(len(formatted), 12)
        header_height = 38
        row_height = 38
        resolved_height = min(680, max(110, header_height + visible_rows * row_height + 6))

    dataframe_kwargs: dict[str, Any] = {
        "use_container_width": True,
        "hide_index": True,
        "height": resolved_height,
        "column_config": _build_column_config(formatted),
    }

    st.dataframe(_build_styler(formatted), **dataframe_kwargs)