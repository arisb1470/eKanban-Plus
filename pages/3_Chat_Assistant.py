from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analytics import enrich_latest_snapshot
from src.auth import render_sidebar_auth, require_login, scope_bundle_to_customer
from src.bundling import build_bundle_candidates
from src.db import get_latest_snapshot, register_bundle
from src.llm import ask_llm, llm_is_available
from src.load_data import load_data, load_demo_business_rules
from src.retrieval import rank_texts
from src.router import route_question
from src.tools import (
    find_critical_drums,
    get_bundle_candidates,
    get_drum_status,
    get_general_summary,
)
from src.ui import apply_app_styles, render_table

apply_app_styles()

bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

st.title("Chat-Assistent")

if not scoped_bundle.has_core_data:
    st.info("Für dieses Kundenkonto wurden noch keine CSV-Dateien gefunden.")
    st.stop()

con = register_bundle(scoped_bundle)
snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
_ = build_bundle_candidates(snapshot)
rules = load_demo_business_rules()

st.caption("Der Chat nutzt Daten-Tools für Fakten und ein Cloud-Modell nur für die Formulierung.")
if llm_is_available():
    st.success("Chatbot verfügbar")
else:
    st.warning("Kein API-Schlüssel gefunden — der Chat läuft im Ersatzmodus.")

if st.session_state.get("chat_customer") != customer:
    st.session_state.chat_customer = customer
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Frag mich zum Beispiel: "
                "'Welche Trommeln sind kritisch?', "
                "'Welche Bestellungen lassen sich bündeln?' "
                "oder 'Wie ist der Status von Trommel 1574?'"
            ),
        }
    ]
elif "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Frag mich zum Beispiel: "
                "'Welche Trommeln sind kritisch?', "
                "'Welche Bestellungen lassen sich bündeln?' "
                "oder 'Wie ist der Status von Trommel 1574?'"
            ),
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("preview"):
            render_table(pd.DataFrame(message["preview"]), prepare=False)

prompt = st.chat_input("Frage zu Risiko, Trommeln, Bestellzeitpunkt oder Bündelung ...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    decision = route_question(prompt)

    if decision.tool_name == "get_drum_status" and decision.drum_id is not None:
        result = get_drum_status(snapshot, decision.drum_id)
    elif decision.tool_name == "find_critical_drums":
        result = find_critical_drums(snapshot, decision.horizon_days or 7)
    elif decision.tool_name == "build_bundle_candidates":
        result = get_bundle_candidates(snapshot, decision.horizon_days or 14)
    else:
        result = get_general_summary(snapshot)

    retrieved = rank_texts(prompt, rules, top_k=3)
    answer = ask_llm(prompt, result, retrieved)

    preview = result.get("data_preview", [])
    assistant_message = {"role": "assistant", "content": answer}
    if preview:
        assistant_message["preview"] = preview

    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        st.markdown(answer)
        if preview:
            render_table(pd.DataFrame(preview), prepare=False)