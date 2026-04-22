from __future__ import annotations

import re
from typing import Any

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
    get_bundle_details,
    get_drum_status,
    get_general_summary,
)
from src.ui import apply_app_styles, render_page_header, render_table

apply_app_styles()


FOLLOW_UP_TERMS = (
    "davon",
    "diese",
    "dieser",
    "dieses",
    "die erste",
    "das erste",
    "den ersten",
    "die zweite",
    "das zweite",
    "den zweiten",
    "welche davon",
    "welcher davon",
    "welches davon",
    "die",
    "der",
    "das",
)

ORDINALS = {
    "erste": 0,
    "ersten": 0,
    "erstes": 0,
    "erster": 0,
    "1.": 0,
    "1": 0,
    "zweite": 1,
    "zweiten": 1,
    "zweites": 1,
    "zweiter": 1,
    "2.": 1,
    "2": 1,
    "dritte": 2,
    "dritten": 2,
    "drittes": 2,
    "dritter": 2,
    "3.": 2,
    "3": 2,
}


bundle = load_data()
customer = require_login(bundle)
render_sidebar_auth()
scoped_bundle = scope_bundle_to_customer(bundle, customer)

render_page_header(
    "Chat-Assistent",
    "Stelle Fragen zu kritischen Trommeln, Bündeln und Einzelstatus. Fakten kommen direkt aus den geladenen Daten.",
    badge=f"Kundenkonto: {customer}",
)

if not scoped_bundle.has_core_data:
    st.info("Für dieses Kundenkonto wurden noch keine CSV-Dateien gefunden.")
    st.stop()

con = register_bundle(scoped_bundle)
snapshot = enrich_latest_snapshot(get_latest_snapshot(con), scoped_bundle.pricing)
all_bundles = build_bundle_candidates(snapshot)
rules = load_demo_business_rules()

if llm_is_available():
    st.success("Chatbot verfügbar")
else:
    st.warning("Kein API-Schlüssel gefunden — der Chat läuft im Ersatzmodus.")


def _default_context() -> dict[str, Any]:
    return {
        "last_drum_id": None,
        "last_bundle_id": None,
        "last_result_type": None,
        "last_result": None,
        "last_bundles": None,
        "last_question": None,
    }


if st.session_state.get("chat_customer") != customer:
    st.session_state.chat_customer = customer
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Frag mich zum Beispiel: "
                "'Welche Trommeln sind kritisch?', "
                "'Welche Bestellungen lassen sich bündeln?' "
                "oder 'Wie ist der Status von Trommel 1574?'. "
                "Folgefragen wie 'Welche davon sind im Regal OG?' oder "
                "'Wie viel spart das erste Bündel?' werden jetzt ebenfalls unterstützt."
            ),
        }
    ]
    st.session_state.chat_context = _default_context()
elif "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Frag mich zum Beispiel: "
                "'Welche Trommeln sind kritisch?', "
                "'Welche Bestellungen lassen sich bündeln?' "
                "oder 'Wie ist der Status von Trommel 1574?'. "
                "Folgefragen wie 'Welche davon sind im Regal OG?' oder "
                "'Wie viel spart das erste Bündel?' werden jetzt ebenfalls unterstützt."
            ),
        }
    ]
    st.session_state.chat_context = _default_context()
elif "chat_context" not in st.session_state:
    st.session_state.chat_context = _default_context()


def _recent_history(messages: list[dict[str, Any]], limit: int = 6) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for message in messages[-limit:]:
        role = str(message.get("role", "assistant"))
        content = str(message.get("content", "")).strip()
        if content:
            history.append({"role": role, "content": content})
    return history


def _looks_like_follow_up(question: str) -> bool:
    q = question.strip().lower()
    if not q:
        return False
    if any(term in q for term in FOLLOW_UP_TERMS):
        return True
    return q.startswith(("und ", "nur ", "welche ", "wann ", "wie viel ", "wie hoch "))


def _extract_explicit_drum_id(question: str) -> int | None:
    match = re.search(r"(?:trommel|drum|id)\s*[:#]?\s*(\d+)", question.lower())
    if match:
        return int(match.group(1))
    return None


def _resolve_drum_reference(question: str, context: dict[str, Any]) -> int | None:
    explicit = _extract_explicit_drum_id(question)
    if explicit is not None:
        return explicit

    q = question.lower()
    if any(token in q for token in ["diese trommel", "die trommel", "sie", "deren", "wann muss die", "wann muss sie"]):
        last_drum_id = context.get("last_drum_id")
        if last_drum_id is not None:
            return int(last_drum_id)
    return None


def _extract_bundle_id(question: str) -> str | None:
    match = re.search(r"bündel\s*([a-f0-9]{8})", question.lower())
    if match:
        return match.group(1)
    return None


def _resolve_bundle_reference(question: str, bundles_df: pd.DataFrame | None, context: dict[str, Any]) -> str | None:
    explicit = _extract_bundle_id(question)
    if explicit:
        return explicit

    q = question.lower()
    if bundles_df is not None and not bundles_df.empty:
        for term, idx in ORDINALS.items():
            if term in q and "bündel" in q:
                if 0 <= idx < len(bundles_df):
                    return str(bundles_df.iloc[idx]["bundle_id"])

    if any(token in q for token in ["dieses bündel", "das bündel", "diesem bündel", "dafür"]):
        last_bundle_id = context.get("last_bundle_id")
        if last_bundle_id:
            return str(last_bundle_id)
    return None


def _extract_rack_phrase(question: str) -> str | None:
    q = question.lower()
    match = re.search(r"(?:im|in|aus)\s+(?:regal|rack|bereich)\s+([a-z0-9äöüß\\-_/ ]+)", q)
    if match:
        return match.group(1).strip(" .,!?")
    return None


def _filter_last_result(question: str, context: dict[str, Any]) -> dict[str, Any] | None:
    last_result = context.get("last_result")
    last_result_type = context.get("last_result_type")
    if not isinstance(last_result, pd.DataFrame) or last_result.empty:
        return None

    q = question.lower()
    filtered = last_result.copy()
    explanation: list[str] = []

    rack_phrase = _extract_rack_phrase(question)
    if rack_phrase and "rack" in filtered.columns:
        filtered = filtered[filtered["rack"].astype("string").str.lower().str.contains(rack_phrase, na=False)]
        explanation.append(f"gefiltert nach Regal/Bereich '{rack_phrase}'")

    if any(term in q for term in ["schwache batterie", "batterie schwach"]):
        if "review_reason" in filtered.columns:
            filtered = filtered[filtered["review_reason"].astype("string").str.lower().str.contains("batterie schwach", na=False)]
            explanation.append("nur Trommeln mit schwacher Batterie")

    if any(term in q for term in ["schwaches signal", "signal schwach", "schlechtes signal"]):
        if "review_reason" in filtered.columns:
            filtered = filtered[filtered["review_reason"].astype("string").str.lower().str.contains("funksignal schwach", na=False)]
            explanation.append("nur Trommeln mit schwachem Signal")

    if any(term in q for term in ["niedrige prognosegüte", "niedrige prognosesicherheit", "unsichere"]):
        if "forecast_confidence" in filtered.columns:
            conf = filtered["forecast_confidence"].astype("string").str.lower()
            filtered = filtered[conf.isin(["low", "niedrig", "unknown", "unbekannt"])]
        elif "forecast_status" in filtered.columns:
            filtered = filtered[
                filtered["forecast_status"].astype("string").str.lower().str.contains("niedrig|keine", na=False)
            ]
        explanation.append("nur Trommeln mit niedriger Prognosegüte oder unsicherem Status")

    if any(term in q for term in ["kritisch", "hoch", "mittel", "unsicher", "gut", "bald fällig", "beobachten", "niedrig"]):
        if "risk_label" in filtered.columns:
            for risk in ["kritisch", "hoch", "mittel", "unsicher", "gut", "bald fällig", "beobachten", "niedrig"]:
                if risk in q:
                    filtered = filtered[filtered["risk_label"].astype("string").str.lower() == risk]
                    explanation.append(f"nur Risikostatus '{risk}'")
                    break

    if filtered.empty:
        return {
            "summary": "Zur Folgefrage wurden im letzten Ergebnis keine passenden Datensätze gefunden.",
            "data_preview": [],
            "count": 0,
        }

    if "days_left" in filtered.columns and any(term in q for term in ["höchste priorität", "am kritischsten", "am dringendsten"]):
        ordered = filtered.copy()
        ordered["_days_left_num"] = pd.to_numeric(ordered["days_left"], errors="coerce")
        ordered = ordered.sort_values(["_days_left_num"], na_position="last")
        filtered = ordered.drop(columns=["_days_left_num"]).head(1)
        explanation.append("am dringendsten nach geringster Restreichweite")

    label = "Ergebnis zur Folgefrage"
    if last_result_type == "critical_drums":
        label = "Gefilterte kritische Trommeln"
    elif last_result_type == "bundle_details":
        label = "Gefilterte Bündel-Details"

    summary = f"{label}: {len(filtered)} Datensätze"
    if explanation:
        summary += " (" + ", ".join(explanation) + ")"

    return {
        "summary": summary,
        "count": len(filtered),
        "data_preview": filtered.head(10).where(pd.notnull(filtered.head(10)), None).to_dict(orient="records"),
        "_result_df": filtered,
        "_result_type": last_result_type,
    }


def _bundle_result_from_reference(question: str, bundles_df: pd.DataFrame, context: dict[str, Any]) -> dict[str, Any] | None:
    if bundles_df.empty:
        return None

    bundle_id = _resolve_bundle_reference(question, bundles_df, context)
    if not bundle_id:
        return None

    selected = bundles_df.loc[bundles_df["bundle_id"].astype("string") == bundle_id]
    if selected.empty:
        return {
            "summary": f"Das referenzierte Bündel '{bundle_id}' wurde nicht gefunden.",
            "data_preview": [],
            "count": 0,
        }

    row = selected.iloc[0]
    details_result = get_bundle_details(snapshot, bundles_df, bundle_id)
    summary = (
        f"Bündel {bundle_id}: {int(row.get('drum_count', 0))} Trommeln, "
        f"Kosten gebündelt {float(row.get('bundle_total_eur', 0.0)):.2f} €, "
        f"Kosten einzeln {float(row.get('individual_total_eur', 0.0)):.2f} €, "
        f"Einsparung {float(row.get('savings_eur', 0.0)):.2f} €."
    )

    preview_row = (
        selected[
            [
                "bundle_id",
                "rack",
                "recommended_order_date",
                "latest_due_date",
                "drum_count",
                "bundle_value_eur",
                "bundle_total_eur",
                "individual_total_eur",
                "savings_eur",
                "priority",
            ]
        ]
        .head(1)
        .where(pd.notnull(selected.head(1)), None)
        .to_dict(orient="records")
    )

    return {
        "summary": summary,
        "bundle_preview": preview_row,
        "data_preview": details_result.get("data_preview", []),
        "count": details_result.get("count", 0),
        "_result_df": pd.DataFrame(details_result.get("data_preview", [])),
        "_result_type": "bundle_details",
        "_bundle_id": bundle_id,
    }


def _resolve_result(question: str, context: dict[str, Any]) -> dict[str, Any]:
    bundles_df = context.get("last_bundles")
    if not isinstance(bundles_df, pd.DataFrame):
        bundles_df = all_bundles

    drum_id = _resolve_drum_reference(question, context)

    if drum_id is not None:
        result = get_drum_status(snapshot, drum_id)
        result["_result_df"] = pd.DataFrame(result.get("data_preview", []))
        result["_result_type"] = "drum_status"
        result["_drum_id"] = drum_id
        return result

    bundle_ref_result = _bundle_result_from_reference(question, bundles_df, context)
    if bundle_ref_result is not None:
        return bundle_ref_result

    if _looks_like_follow_up(question):
        filtered = _filter_last_result(question, context)
        if filtered is not None:
            return filtered

    decision = route_question(question)

    if decision.tool_name == "get_drum_status" and decision.drum_id is not None:
        result = get_drum_status(snapshot, decision.drum_id)
        result["_result_df"] = pd.DataFrame(result.get("data_preview", []))
        result["_result_type"] = "drum_status"
        result["_drum_id"] = decision.drum_id
        return result

    if decision.tool_name == "find_critical_drums":
        result = find_critical_drums(snapshot, decision.horizon_days or 7)
        result_df = pd.DataFrame(result.get("data_preview", []))
        result["_result_df"] = result_df
        result["_result_type"] = "critical_drums"
        return result

    if decision.tool_name == "build_bundle_candidates":
        result = get_bundle_candidates(snapshot, decision.horizon_days or 14)
        result_df = pd.DataFrame(result.get("data_preview", []))
        result["_result_df"] = result_df
        result["_result_type"] = "bundles"
        result["_bundles_df"] = build_bundle_candidates(snapshot, horizon_days=decision.horizon_days or 14)
        return result

    result = get_general_summary(snapshot)
    result["_result_df"] = pd.DataFrame(result.get("data_preview", []))
    result["_result_type"] = "general_summary"
    return result


def _update_context_from_result(context: dict[str, Any], question: str, result: dict[str, Any]) -> None:
    context["last_question"] = question

    if result.get("_drum_id") is not None:
        context["last_drum_id"] = int(result["_drum_id"])

    if result.get("_bundle_id") is not None:
        context["last_bundle_id"] = str(result["_bundle_id"])

    result_df = result.get("_result_df")
    if isinstance(result_df, pd.DataFrame):
        context["last_result"] = result_df.copy()

        if result.get("_result_type") == "drum_status" and not result_df.empty and "drum_id" in result_df.columns:
            try:
                context["last_drum_id"] = int(pd.to_numeric(result_df.iloc[0]["drum_id"], errors="coerce"))
            except Exception:
                pass

    if result.get("_result_type"):
        context["last_result_type"] = result["_result_type"]

    bundles_df = result.get("_bundles_df")
    if isinstance(bundles_df, pd.DataFrame):
        context["last_bundles"] = bundles_df.copy()


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("preview"):
            render_table(pd.DataFrame(message["preview"]), prepare=False)
        if message.get("bundle_preview"):
            st.markdown("**Bündel-Kopfinfo**")
            render_table(pd.DataFrame(message["bundle_preview"]), prepare=False)

prompt = st.chat_input("Frage zu Risiko, Trommeln, Bestellzeitpunkt oder Bündelung ...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    chat_context = st.session_state.chat_context
    result = _resolve_result(prompt, chat_context)
    _update_context_from_result(chat_context, prompt, result)

    retrieved = rank_texts(prompt, rules, top_k=3)
    history = _recent_history(st.session_state.messages, limit=6)
    llm_result = {key: value for key, value in result.items() if not str(key).startswith("_")}
    answer = ask_llm(prompt, llm_result, retrieved, conversation_history=history)

    preview = result.get("data_preview", [])
    bundle_preview = result.get("bundle_preview", [])
    assistant_message = {"role": "assistant", "content": answer}
    if preview:
        assistant_message["preview"] = preview
    if bundle_preview:
        assistant_message["bundle_preview"] = bundle_preview

    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        st.markdown(answer)
        if bundle_preview:
            st.markdown("**Bündel-Kopfinfo**")
            render_table(pd.DataFrame(bundle_preview), prepare=False)
        if preview:
            render_table(pd.DataFrame(preview), prepare=False)