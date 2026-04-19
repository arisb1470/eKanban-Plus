from __future__ import annotations

import streamlit as st

from src.analytics import enrich_latest_snapshot
from src.auth import render_sidebar_auth, require_login, scope_bundle_to_customer
from src.db import register_bundle
from src.load_data import load_data, merge_racks

bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

st.title("Drum Explorer")

if not scoped_bundle.has_core_data:
    st.info("Für dieses Kundenkonto wurden noch keine CSV-Dateien gefunden.")
    st.stop()

_ = register_bundle(scoped_bundle)
all_racks = merge_racks(scoped_bundle)
snapshot = enrich_latest_snapshot(all_racks.sort_values(["drum_id", "date"]).groupby("drum_id", as_index=False).tail(1), scoped_bundle.pricing)

available_drums = sorted(snapshot["drum_id"].dropna().astype(int).unique().tolist())
selected_drum = st.selectbox("Trommel wählen", available_drums)

latest = snapshot.loc[snapshot["drum_id"].astype(int) == selected_drum].iloc[0]
history = all_racks.loc[all_racks["drum_id"].astype("Int64") == selected_drum].copy().sort_values("date")

metric_cols = st.columns(4)
current_length = latest.get("current_length_m")
metric_cols[0].metric(
    "Aktueller Bestand",
    f"{float(current_length):.1f} m" if current_length is not None and str(current_length) != "nan" else "—",
)

if latest.get("days_left") is not None and str(latest.get("days_left")) != "nan":
    days_left_label = f"{float(latest['days_left']):.1f} Tage"
else:
    status = latest.get("forecast_status", "")
    if status == "kein aktueller Verbrauch":
        days_left_label = "kein aktueller Verbrauch"
    elif status == "keine Verbrauchsdaten":
        days_left_label = "keine Daten"
    else:
        days_left_label = "—"
metric_cols[1].metric("Restreichweite", days_left_label)

safe_order_date = latest.get("latest_safe_order_date")
metric_cols[2].metric(
    "Sicher bestellen bis",
    "—" if safe_order_date is None or str(safe_order_date) == "NaT" else str(safe_order_date).split(" ")[0],
)
metric_cols[3].metric("Prognosestatus", latest.get("forecast_status", "—"))
st.caption(f"Prognosegüte: {latest.get('forecast_confidence', '—')}")

st.subheader("Zeitverlauf")
chart_df = history[["date", "daily_avg_cable_length_m", "linear_forecast_m"]].dropna(subset=["date"]).set_index("date")
st.line_chart(chart_df)

st.subheader("Drum-Metadaten")
st.json({
    "drum_id": int(latest["drum_id"]),
    "rack": latest.get("rack"),
    "product": latest.get("product"),
    "part_number": latest.get("part_number"),
    "predicted_empty_date": str(latest.get("predicted_empty_date")).split(" ")[0] if str(latest.get("predicted_empty_date")) != "NaT" else None,
    "estimated_order_value_eur": float(latest.get("estimated_order_value_eur", 0.0)),
    "forecast_status": latest.get("forecast_status"),
    "forecast_confidence": latest.get("forecast_confidence"),
    "risk_label": latest.get("risk_label"),
})