from __future__ import annotations

import streamlit as st

from src.analytics import build_kpis, enrich_latest_snapshot, filter_critical_drums
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
st.caption(f"Aktive Kundensicht: {customer}")

if scoped_bundle.has_core_data:
    con = register_bundle(scoped_bundle)
    snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
    critical = filter_critical_drums(snapshot, horizon_days=7)
    kpis = build_kpis(snapshot)

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
        "drum_id", "rack", "product", "current_length_m", "days_left",
        "predicted_empty_date", "latest_safe_order_date", "estimated_order_value_eur", "risk_label",
    ]
    st.dataframe(without_tenant(critical[preview_cols]), width='stretch', hide_index=True)
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