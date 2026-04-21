from __future__ import annotations

import streamlit as st

from src.analytics import enrich_latest_snapshot, get_data_freshness
from src.auth import render_sidebar_auth, require_login, scope_bundle_to_customer
from src.bundling import build_bundle_candidates, bundle_details
from src.db import get_latest_snapshot, register_bundle
from src.load_data import load_data
from src.ui import apply_app_styles, render_page_header, render_table

apply_app_styles()

bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

render_page_header(
    "Bündeloptimierung",
    "Finde sinnvolle Sammelbestellungen innerhalb eines Planungshorizonts und vergleiche direkte Kosteneffekte.",
    badge=f"Kundenkonto: {customer}",
)

if not scoped_bundle.has_core_data:
    st.info("Für dieses Kundenkonto wurden noch keine CSV-Dateien gefunden.")
    st.stop()

con = register_bundle(scoped_bundle)
snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
freshness = get_data_freshness(snapshot)

st.caption(f"Datenstand: {freshness['as_of_date'].date()} · Alter der Daten: {freshness['age_days']} Tage")

control_left, control_right = st.columns(2)
with control_left:
    horizon = st.slider("Planungshorizont (Tage)", min_value=3, max_value=30, value=14)
with control_right:
    window = st.slider("Bündelungsfenster (Tage)", min_value=2, max_value=10, value=5)

bundles = build_bundle_candidates(snapshot, horizon_days=horizon, window_days=window)
if bundles.empty:
    st.warning("Aktuell keine Bündel-Kandidaten im gewählten Horizont gefunden.")
    st.stop()

st.subheader("Empfohlene Bündel")
render_table(bundles)

selected_bundle = st.selectbox("Bündel auswählen", options=bundles["bundle_id"].tolist())
details = bundle_details(snapshot, selected_bundle, bundles)
selected_row = bundles.loc[bundles["bundle_id"] == selected_bundle].iloc[0]

metric_cols = st.columns(5)
metric_cols[0].metric("Materialwert", f"{selected_row['bundle_value_eur']:.2f} €")
metric_cols[1].metric("Schnittkosten", f"{selected_row['bundle_cutting_eur']:.2f} €")
metric_cols[2].metric("Kosten einzeln", f"{selected_row['individual_total_eur']:.2f} €")
metric_cols[3].metric("Kosten gebündelt", f"{selected_row['bundle_total_eur']:.2f} €")
metric_cols[4].metric("Einsparung", f"{selected_row['savings_eur']:.2f} €")

st.subheader("Details zum ausgewählten Bündel")
render_table(
    details[
        [
            "drum_id",
            "rack",
            "product",
            "latest_safe_order_date",
            "reorder_qty_m",
            "material_order_value_eur",
            "cutting_cost_eur",
            "estimated_order_value_eur",
            "risk_label",
        ]
    ]
)