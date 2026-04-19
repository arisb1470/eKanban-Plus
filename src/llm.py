from __future__ import annotations

from typing import Any

import streamlit as st

from src.config import DEFAULT_CHAT_MODEL
from src.prompts import build_answer_prompt

try:
    from google import genai
except Exception:  # pragma: no cover
    genai = None


class LLMUnavailableError(RuntimeError):
    pass


def _get_client():
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        raise LLMUnavailableError("Kein GEMINI_API_KEY in st.secrets hinterlegt.")
    if genai is None:
        raise LLMUnavailableError("Das Paket google-genai ist nicht installiert.")
    return genai.Client(api_key=api_key)


def llm_is_available() -> bool:
    try:
        _get_client()
        return True
    except Exception:
        return False


def ask_llm(question: str, tool_result: dict[str, Any], retrieval_context: list[dict[str, str]] | None = None) -> str:
    prompt = build_answer_prompt(question=question, tool_result=tool_result, retrieval_context=retrieval_context)
    try:
        client = _get_client()
        model = st.secrets.get("GEMINI_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if text:
            return text
    except Exception as exc:
        return fallback_answer(question, tool_result, retrieval_context, error=str(exc))
    return fallback_answer(question, tool_result, retrieval_context)


def fallback_answer(
    question: str,
    tool_result: dict[str, Any],
    retrieval_context: list[dict[str, str]] | None = None,
    error: str | None = None,
) -> str:
    lines = [f"**Frage:** {question}", "", "**Ergebnis:**"]
    summary = tool_result.get("summary")
    if summary:
        lines.append(f"- {summary}")
    if "data_preview" in tool_result:
        preview = tool_result["data_preview"]
        lines.append(f"- Datenpunkte im Preview: {len(preview)}")
    if retrieval_context:
        lines.append("")
        lines.append("**Relevante Regeln:**")
        for item in retrieval_context:
            lines.append(f"- {item.get('title')}: {item.get('text')}")
    if error:
        lines.append("")
        lines.append(f"_LLM-Fallback aktiv: {error}_")
    return "\n".join(lines)