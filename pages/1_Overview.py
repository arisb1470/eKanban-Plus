from __future__ import annotations

import streamlit as st

from src.analytics import (
    build_kpis,
    display_snapshot,
    enrich_latest_snapshot,
    filter_critical_drums,
    filter_review_drums,
)
from src.auth import render_sidebar_auth, require_login, scope_bundle_to_customer, without_tenant
from src.db import get_latest_snapshot, register_bundle
from src.load_data import load_data

bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

st.title("Overview")

if not scoped_bundle.has_core_data:
    st.info("Für dieses Kundenkonto wurden noch keine CSV-Dateien gefunden.")
    st.stop()

con = register_bundle(scoped_bundle)
snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
kpis = build_kpis(snapshot, attention_horizon_days=30)
critical = filter_critical_drums(snapshot, horizon_days=30)
review = filter_review_drums(snapshot)

metric_cols = st.columns(6)
metric_cols[0].metric("Trommeln", kpis["drums"])
metric_cols[1].metric("Kritisch", kpis["critical"])
metric_cols[2].metric("Handlungsbedarf", kpis["attention"])
metric_cols[3].metric("Prüfbedarf", kpis["review"])
metric_cols[4].metric("Ø Restreichweite", f"{kpis['avg_days_left']} Tage")
metric_cols[5].metric("High-Confidence", f"{kpis['high_confidence_share']} %")

left, right = st.columns([1.3, 1])
with left:
    st.subheader("Trommeln mit Handlungsbedarf")
    st.dataframe(
        without_tenant(
            display_snapshot(
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
                        "risk_label",
                    ]
                ]
            )
        ),
        width="stretch",
        hide_index=True,
    )

with right:
    st.subheader("Verteilung nach Risiko")
    risk_counts = snapshot["risk_label"].value_counts().rename_axis("risk_label").reset_index(name="count")
    st.bar_chart(risk_counts.set_index("risk_label"))

st.subheader("Trommeln mit Prüfbedarf")
st.dataframe(
    without_tenant(
        display_snapshot(
            review[
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
                    "risk_label",
                ]
            ]
        )
    ),
    width="stretch",
    hide_index=True,
)

st.subheader("Latest Snapshot")
st.dataframe(without_tenant(snapshot), width="stretch", hide_index=True)