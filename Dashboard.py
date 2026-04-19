from __future__ import annotations

import streamlit as st

from src.analytics import (
    build_kpis,
    display_snapshot,
    enrich_latest_snapshot,
    filter_critical_drums,
    filter_review_drums,
    get_data_freshness,
)
from src.auth import render_sidebar_auth, require_login, scope_bundle_to_customer, without_tenant
from src.db import get_latest_snapshot, register_bundle
from src.load_data import load_data

st.set_page_config(
    page_title="LAPP eKanban Plus",
    page_icon="📦",
    layout="wide",
)

bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

st.title("LAPP eKanban Plus")

if scoped_bundle.has_core_data:
    con = register_bundle(scoped_bundle)
    snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
    critical = filter_critical_drums(snapshot, horizon_days=30)
    review = filter_review_drums(snapshot)
    kpis = build_kpis(snapshot, attention_horizon_days=30)
    freshness = get_data_freshness(snapshot)

    st.caption(
        f"Datenstand: {freshness['as_of_date'].date()} · Alter der Daten: {freshness['age_days']} Tage"
    )
    if freshness["is_stale"]:
        st.warning(
            "Die Daten sind historisch und werden nicht als Live-Bestand interpretiert. "
            "Alle Bestell- und Risikoangaben beziehen sich auf den letzten Messzeitpunkt im Datensatz."
        )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Trommeln", kpis["drums"])
    col2.metric("Kritisch", kpis["critical"])
    col3.metric("Handlungsbedarf", kpis["attention"])
    col4.metric("Prüfbedarf", kpis["review"])
    col5.metric("Ø Restreichweite", f"{kpis['avg_days_left']} Tage")

    st.subheader("Was diese App macht")
    st.markdown(
        """
        - berechnet Restreichweiten und sichere Bestellzeitpunkte
        - identifiziert kritische Trommeln, Telemetrieprobleme und Forecast-Risiken
        - schlägt Bestell-Bündel vor, um Kosten zu senken
        - beantwortet Rückfragen im Chat auf Basis von Daten-Tools
        """
    )

    preview_cols = [
        "drum_id",
        "rack",
        "product",
        "current_length_m",
        "days_left",
        "predicted_empty_date",
        "latest_safe_order_date",
        "forecast_status",
        "review_reason",
        "estimated_order_value_eur",
        "risk_label",
    ]

    st.subheader("Trommeln mit Handlungsbedarf im 30-Tage-Horizont")
    st.dataframe(
        without_tenant(display_snapshot(critical[preview_cols])),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Trommeln mit Prüfbedarf")
    st.dataframe(
        without_tenant(
            display_snapshot(
                review[
                    [
                        "drum_id",
                        "rack",
                        "product",
                        "forecast_status",
                        "review_reason",
                        "sensor_readings_count",
                        "avg_battery_voltage",
                        "avg_signal_strength",
                    ]
                ]
            )
        ),
        width="stretch",
        hide_index=True,
    )
else:
    st.warning("Für dieses Kundenkonto wurden noch keine vollständigen Daten gefunden.")
    st.markdown(
        """
        Erwartete Struktur:
        ```
        data/raw/
        ├─ rack_kunde_a_regal_og.csv
        ├─ rack_kunde_b_kommissionierung.csv
        ├─ pricing_and_leadtimes.csv
        └─ einzeltrommeln/
           └─ *.csv
        ```
        """
    )

st.divider()
st.subheader("Navigation")
st.markdown(
    "Nutze die Seitenleiste für **Overview**, **Bundle Optimizer**, **Chat Assistant** und **Drum Explorer**."
)