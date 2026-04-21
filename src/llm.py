from __future__ import annotations

from typing import Any

import streamlit as st
from openai import OpenAI

from src.config import DEFAULT_CHAT_MODEL
from src.prompts import build_answer_prompt


class LLMUnavailableError(RuntimeError):
    pass


def _get_client() -> OpenAI:
    api_key = st.secrets.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise LLMUnavailableError("Kein OPENROUTER_API_KEY in st.secrets hinterlegt.")

    base_url = st.secrets.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()

    headers: dict[str, str] = {}
    http_referer = st.secrets.get("OPENROUTER_HTTP_REFERER", "").strip()
    app_title = st.secrets.get("OPENROUTER_APP_TITLE", "").strip()

    if http_referer:
        headers["HTTP-Referer"] = http_referer
    if app_title:
        headers["X-OpenRouter-Title"] = app_title

    kwargs: dict[str, Any] = {
        "base_url": base_url,
        "api_key": api_key,
    }
    if headers:
        kwargs["default_headers"] = headers

    return OpenAI(**kwargs)


def llm_is_available() -> bool:
    try:
        _get_client()
        return True
    except Exception:
        return False


def _extract_text(response: Any) -> str | None:
    try:
        message = response.choices[0].message
    except Exception:
        return None

    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if text:
                    parts.append(text)
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts)

    return None


def ask_llm(
    question: str,
    tool_result: dict[str, Any],
    retrieval_context: list[dict[str, str]] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    prompt = build_answer_prompt(
        question=question,
        tool_result=tool_result,
        retrieval_context=retrieval_context,
        conversation_history=conversation_history,
    )
    try:
        client = _get_client()
        model = st.secrets.get("OPENROUTER_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        text = _extract_text(response)
        if text:
            return text
    except Exception as exc:
        return fallback_answer(question, tool_result, retrieval_context, conversation_history, error=str(exc))
    return fallback_answer(question, tool_result, retrieval_context, conversation_history)


def fallback_answer(
    question: str,
    tool_result: dict[str, Any],
    retrieval_context: list[dict[str, str]] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    error: str | None = None,
) -> str:
    lines = [f"**Frage:** {question}", "", "**Ergebnis:**"]
    summary = tool_result.get("summary")
    if summary:
        lines.append(f"- {summary}")
    if "count" in tool_result:
        lines.append(f"- Anzahl: {tool_result['count']}")
    if "data_preview" in tool_result:
        preview = tool_result["data_preview"]
        lines.append(f"- Datenpunkte im Preview: {len(preview)}")
    if conversation_history:
        lines.append("")
        lines.append("**Gesprächskontext:**")
        for item in conversation_history[-3:]:
            lines.append(f"- {item.get('role', 'user')}: {item.get('content', '')}")
    if retrieval_context:
        lines.append("")
        lines.append("**Relevante Regeln:**")
        for item in retrieval_context:
            lines.append(f"- {item.get('title')}: {item.get('text')}")
    if error:
        lines.append("")
        lines.append(f"_LLM-Fallback aktiv: {error}_")
    return "\n".join(lines)