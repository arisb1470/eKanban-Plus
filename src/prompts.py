from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """
Du bist ein Supply-Chain Analytics Assistant für einen eKanban-Prototypen.
Antworte nur auf Basis der gelieferten Tool-Ergebnisse und Business-Regeln.
Erfinde keine Zahlen und mache Unsicherheit explizit.
Formuliere knapp, geschäftsnah und nachvollziehbar auf Deutsch.
""".strip()


def build_answer_prompt(question: str, tool_result: dict[str, Any], retrieval_context: list[dict[str, str]] | None = None) -> str:
    context = retrieval_context or []
    return (
        f"Systemrolle:\n{SYSTEM_PROMPT}\n\n"
        f"Nutzerfrage:\n{question}\n\n"
        f"Tool-Ergebnis (JSON):\n{json.dumps(tool_result, ensure_ascii=False, default=str, indent=2)}\n\n"
        f"Relevante Regeln / Kontexte:\n{json.dumps(context, ensure_ascii=False, default=str, indent=2)}\n\n"
        "Antworte in 4 Teilen: 1) direkte Antwort, 2) wichtigste Zahlen, 3) kurze Begründung, 4) empfohlene nächste Aktion."
    )