from __future__ import annotations

import streamlit as st

from src.analytics import enrich_latest_snapshot
from src.db import register_bundle
from src.load_data import load_data, merge_racks

st.title("Drum Explorer")

bundle = load_data()
if not bundle.has_core_data:
    st.info("Bitte zuerst die CSV-Dateien in data/raw ablegen.")
    st.stop()

_ = register_bundle(bundle)
all_racks = merge_racks(bundle)
snapshot = enrich_latest_snapshot(all_racks.sort_values(["drum_id", "date"]).groupby("drum_id", as_index=False).tail(1), bundle.pricing)

available_drums = sorted(snapshot["drum_id"].dropna().astype(int).unique().tolist())
selected_drum = st.selectbox("Trommel wählen", available_drums)

latest = snapshot.loc[snapshot["drum_id"].astype(int) == selected_drum].iloc[0]
history = all_racks.loc[all_racks["drum_id"].astype("Int64") == selected_drum].copy().sort_values("date")

metric_cols = st.columns(4)
metric_cols[0].metric("Aktueller Bestand", f"{latest['current_length_m']:.1f} m")
metric_cols[1].metric("Restreichweite", f"{latest['days_left']:.1f} Tage")
metric_cols[2].metric("Sicher bestellen bis", str(latest["latest_safe_order_date"]).split(" ")[0])
metric_cols[3].metric("Forecast Confidence", latest["forecast_confidence"])

st.subheader("Zeitverlauf")
chart_df = history[["date", "daily_avg_cable_length_m", "linear_forecast_m"]].dropna(subset=["date"]).set_index("date")
st.line_chart(chart_df)

st.subheader("Drum-Metadaten")
st.json({
    "drum_id": int(latest["drum_id"]),
    "tenant": latest.get("tenant"),
    "rack": latest.get("rack"),
    "product": latest.get("product"),
    "part_number": latest.get("part_number"),
    "predicted_empty_date": str(latest.get("predicted_empty_date")),
    "estimated_order_value_eur": float(latest.get("estimated_order_value_eur", 0.0)),
    "risk_label": latest.get("risk_label"),
})