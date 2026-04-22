from __future__ import annotations

import altair as alt
import pandas as pd
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
from src.ui import apply_app_styles, render_page_header, render_table

apply_app_styles()

bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

render_page_header(
    "Überblick",
    "Die wichtigsten Kennzahlen, kritischen Trommeln und Prüfhinweise auf einen Blick.",
    badge=f"Kundenkonto: {customer}",
)

if not scoped_bundle.has_core_data:
    st.info("Für dieses Kundenkonto wurden noch keine CSV-Dateien gefunden.")
    st.stop()

con = register_bundle(scoped_bundle)
snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
kpis = build_kpis(snapshot, attention_horizon_days=30)
critical = filter_critical_drums(snapshot, horizon_days=30)
review = filter_review_drums(snapshot)
freshness = get_data_freshness(snapshot)

metric_cols = st.columns(6)
metric_cols[0].metric("Trommeln", kpis["drums"])
metric_cols[1].metric("Kritisch", kpis["critical"])
metric_cols[2].metric("Handlungsbedarf", kpis["attention"])
metric_cols[3].metric("Prüfbedarf", kpis["review"])
metric_cols[4].metric("Ø Restreichweite", f"{kpis['avg_days_left']} Tage")
metric_cols[5].metric("Hohe Prognosegüte", f"{kpis['high_confidence_share']} %")

left, right = st.columns([1.35, 0.95])
with left:
    st.subheader("Trommeln mit Handlungsbedarf")
    render_table(
        critical[
            [
                "drum_id",
                "rack",
                "product",
                "risk_label",
                "current_length_m",
                "days_left",
                "latest_safe_order_date",
                "predicted_empty_date",
            ]
        ]
    )

with right:
    st.subheader("Verteilung nach Risiko")

    risk_order = ["gut", "mittel", "hoch", "kritisch", "unsicher"]
    risk_colors = ["#16a34a", "#f59e0b", "#f97316", "#dc2626", "#7c3aed"]

    risk_counts = (
        snapshot["risk_label"]
        .astype("string")
        .str.lower()
        .value_counts()
        .rename_axis("risk_label")
        .reset_index(name="count")
    )

    if risk_counts.empty:
        st.info("Keine Risikodaten vorhanden.")
    else:
        risk_counts["risk_label"] = pd.Categorical(
            risk_counts["risk_label"],
            categories=risk_order,
            ordered=True,
        )
        risk_counts = risk_counts.sort_values("risk_label").dropna(subset=["risk_label"])

        chart = alt.Chart(risk_counts).mark_bar(cornerRadiusEnd=5).encode(
            y=alt.Y("risk_label:N", sort=risk_order, title=None, axis=alt.Axis(labelLimit=160)),
            x=alt.X("count:Q", title="Anzahl"),
            color=alt.Color(
                "risk_label:N",
                scale=alt.Scale(domain=risk_order, range=risk_colors),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("risk_label:N", title="Risikostatus"),
                alt.Tooltip("count:Q", title="Anzahl"),
            ],
        ).properties(height=260)

        labels = chart.mark_text(
            align="left",
            baseline="middle",
            dx=6,
            color="#334155",
        ).encode(text="count:Q")

        st.altair_chart(chart + labels, use_container_width=True)

st.subheader("Trommeln mit Prüfbedarf")
render_table(
    review[
        [
            "drum_id",
            "rack",
            "product",
            "review_reason",
            "sensor_readings_count",
            "avg_battery_voltage",
            "avg_signal_strength",
        ]
    ]
)

with st.expander("Alle Daten aufzeigen"):
    render_table(snapshot)