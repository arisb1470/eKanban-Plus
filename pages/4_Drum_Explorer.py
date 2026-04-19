from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analytics import enrich_latest_snapshot, get_data_freshness
from src.auth import render_sidebar_auth, require_login, scope_bundle_to_customer
from src.db import register_bundle
from src.load_data import load_data, merge_racks


def _best_history_for_drum(bundle, all_racks: pd.DataFrame, drum_id: int) -> tuple[pd.DataFrame, str]:
    rack_history = (
        all_racks.loc[all_racks["drum_id"].astype("Int64") == drum_id].copy().sort_values("date")
        if not all_racks.empty
        else pd.DataFrame()
    )

    single_candidates = []
    for name, df in bundle.single_drums.items():
        if "drum_id" not in df.columns:
            continue
        match = df.loc[df["drum_id"].astype("Int64") == drum_id].copy()
        if not match.empty:
            single_candidates.append((name, match.sort_values("date")))

    if not single_candidates:
        return rack_history, "Rack-Export"

    best_name, best_history = max(single_candidates, key=lambda item: len(item[1]))
    if len(best_history) >= len(rack_history):
        return best_history, f"Einzeltrommel-Export ({best_name})"

    return rack_history, "Rack-Export"


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
snapshot = enrich_latest_snapshot(
    all_racks.sort_values(["drum_id", "date"]).groupby("drum_id", as_index=False).tail(1),
    scoped_bundle.pricing,
)
freshness = get_data_freshness(snapshot)

st.caption(f"Datenstand: {freshness['as_of_date'].date()} · Alter der Daten: {freshness['age_days']} Tage")
if freshness["is_stale"]:
    st.warning(
        "Die angezeigten Bestands- und Prognosewerte beziehen sich auf den letzten erfassten Messpunkt im Datensatz."
    )

available_drums = sorted(snapshot["drum_id"].dropna().astype(int).unique().tolist())
selected_drum = st.selectbox("Trommel wählen", available_drums)

latest = snapshot.loc[snapshot["drum_id"].astype(int) == selected_drum].iloc[0]
history, history_source = _best_history_for_drum(scoped_bundle, all_racks, selected_drum)

metric_cols = st.columns(5)
current_length = latest.get("current_length_m")
metric_cols[0].metric(
    "Bestand am Snapshot",
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
metric_cols[4].metric("Review", latest.get("review_reason", "—"))
st.caption(
    f"Snapshot vom {str(latest.get('date')).split(' ')[0]} · Prognosegüte: {latest.get('forecast_confidence', '—')} · Quelle Verlauf: {history_source}"
)

st.subheader("Zeitverlauf")
chart_df = history[["date", "daily_avg_cable_length_m", "linear_forecast_m"]].dropna(subset=["date"]).set_index("date")
st.line_chart(chart_df)

st.subheader("Drum-Metadaten")
st.json(
    {
        "drum_id": int(latest["drum_id"]),
        "rack": latest.get("rack"),
        "product": latest.get("product"),
        "part_number": latest.get("part_number"),
        "predicted_empty_date": str(latest.get("predicted_empty_date")).split(" ")[0]
        if str(latest.get("predicted_empty_date")) != "NaT"
        else None,
        "latest_safe_order_date": str(latest.get("latest_safe_order_date")).split(" ")[0]
        if str(latest.get("latest_safe_order_date")) != "NaT"
        else None,
        "material_order_value_eur": float(latest.get("material_order_value_eur", 0.0)),
        "cutting_cost_eur": float(latest.get("cutting_cost_eur", 0.0)),
        "estimated_order_value_eur": float(latest.get("estimated_order_value_eur", 0.0)),
        "forecast_status": latest.get("forecast_status"),
        "forecast_confidence": latest.get("forecast_confidence"),
        "review_reason": latest.get("review_reason"),
        "risk_label": latest.get("risk_label"),
    }
)