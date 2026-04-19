from __future__ import annotations

import streamlit as st

from src.analytics import build_kpis, enrich_latest_snapshot, filter_critical_drums
from src.db import get_latest_snapshot, register_bundle
from src.load_data import load_data

st.set_page_config(
    page_title="LAPP eKanban Plus",
    page_icon="📦",
    layout="wide",
)

st.title("LAPP eKanban Plus")

bundle = load_data()
if bundle.has_core_data:
    con = register_bundle(bundle)
    snapshot = enrich_latest_snapshot(get_latest_snapshot(con), bundle.pricing)
    kpis = build_kpis(snapshot)
    critical = filter_critical_drums(snapshot, horizon_days=7)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trommeln", kpis["drums"])
    col2.metric("Kritisch", kpis["critical"])
    col3.metric("Handlungsbedarf", kpis["attention"])
    col4.metric("Ø Restreichweite", f"{kpis['avg_days_left']} Tage")

    st.subheader("Was diese App macht")
    st.markdown(
        """
        - berechnet Restreichweiten und sichere Bestellzeitpunkte
        - identifiziert kritische Trommeln und Forecast-Risiken
        - schlägt Bestell-Bündel vor, um Kosten zu senken
        - beantwortet Rückfragen im Chat auf Basis von Daten-Tools
        """
    )

    st.subheader("Kritische Trommeln im 7-Tage-Horizont")
    preview_cols = [
        "drum_id", "tenant", "rack", "product", "current_length_m", "days_left",
        "predicted_empty_date", "latest_safe_order_date", "estimated_order_value_eur", "risk_label",
    ]
    st.dataframe(critical[preview_cols], width='stretch', hide_index=True)
else:
    st.warning("Noch keine vollständigen Daten gefunden. Lege bitte die Challenge-CSVs unter data/raw ab.")
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