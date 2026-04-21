from __future__ import annotations

import streamlit as st

from src.analytics import (
    build_kpis,
    enrich_latest_snapshot,
    filter_critical_drums,
    filter_review_drums,
    get_data_freshness,
)
from src.auth import render_sidebar_auth, require_login, scope_bundle_to_customer
from src.db import get_latest_snapshot, register_bundle
from src.load_data import load_data
from src.ui import apply_app_styles, render_table

apply_app_styles()

bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

st.title("Überblick")

if not scoped_bundle.has_core_data:
    st.info("Für dieses Kundenkonto wurden noch keine CSV-Dateien gefunden.")
    st.stop()

con = register_bundle(scoped_bundle)
snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
kpis = build_kpis(snapshot, attention_horizon_days=30)
critical = filter_critical_drums(snapshot, horizon_days=30)
review = filter_review_drums(snapshot)
freshness = get_data_freshness(snapshot)

st.caption(f"Datenstand: {freshness['as_of_date'].date()} · Alter der Daten: {freshness['age_days']} Tage")

metric_cols = st.columns(6)
metric_cols[0].metric("Trommeln", kpis["drums"])
metric_cols[1].metric("Kritisch", kpis["critical"])
metric_cols[2].metric("Handlungsbedarf", kpis["attention"])
metric_cols[3].metric("Prüfbedarf", kpis["review"])
metric_cols[4].metric("Ø Restreichweite", f"{kpis['avg_days_left']} Tage")
metric_cols[5].metric("Hohe Prognosegüte", f"{kpis['high_confidence_share']} %")

left, right = st.columns([1.3, 1])
with left:
    st.subheader("Trommeln mit Handlungsbedarf")
    render_table(
        critical[
            [
                "drum_id",
                "rack",
                "product",
                "current_length_m",
                "days_left",
                "predicted_empty_date",
                "latest_safe_order_date",
                "forecast_status",
                "forecast_confidence",
                "review_reason",
                "risk_label",
            ]
        ]
    )

with right:
    st.subheader("Verteilung nach Risiko")
    risk_counts = snapshot["risk_label"].value_counts().rename_axis("risk_label").reset_index(name="count")
    st.bar_chart(risk_counts.set_index("risk_label"))

st.subheader("Trommeln mit Prüfbedarf")
render_table(
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
            "risk_label",
        ]
    ]
)

with st.expander("Vollständigen Daten-Snapshot anzeigen"):
    render_table(snapshot)