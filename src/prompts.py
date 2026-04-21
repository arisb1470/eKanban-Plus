from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """
Du bist ein Supply-Chain Analytics Assistant für einen eKanban-Prototypen.
Antworte nur auf Basis der gelieferten Tool-Ergebnisse und Business-Regeln.
Erfinde keine Zahlen und mache Unsicherheit explizit.
Formuliere knapp, geschäftsnah und nachvollziehbar auf Deutsch.

Wichtige Begriffe:
- Handlungsbedarf = Aktionslogik. Eine Trommel hat Handlungsbedarf, wenn mindestens eines der Kriterien aus dem Tool-Ergebnis erfüllt ist.
- Prüfbedarf = unsichere Datenlage, Telemetrieproblem oder Prognoseproblem.
- Restreichweite = nur ein einzelner Prognosewert, nicht automatisch gleichbedeutend mit Handlungsbedarf.

Für Fragen nach Handlungsbedarf:
- Nenne zuerst die betroffenen Trommeln.
- Erkläre danach die Kriterien oder den Grund für Handlungsbedarf.
- Nutze bevorzugt 'attention_reason', 'definition' und 'reason_breakdown'.
- Erkläre Handlungsbedarf NICHT primär mit einer Spannweite von Restreichweiten.
- Trenne Handlungsbedarf sauber von Prüfbedarf.
- Wenn Reichweiten stark variieren, erkläre ausdrücklich, dass Handlungsbedarf auch durch Risikostatus oder Bestelltermin ausgelöst werden kann.

Wenn die aktuelle Frage eine Folgefrage ist, nutze den Gesprächskontext nur zur Auflösung von Bezügen wie 'davon', 'die erste', 'diese Trommel' oder 'dieses Bündel'.
""".strip()


def build_answer_prompt(
    question: str,
    tool_result: dict[str, Any],
    retrieval_context: list[dict[str, str]] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    context = retrieval_context or []
    history = conversation_history or []

    return (
        f"Systemrolle:\n{SYSTEM_PROMPT}\n\n"
        f"Gesprächskontext:\n{json.dumps(history, ensure_ascii=False, default=str, indent=2)}\n\n"
        f"Nutzerfrage:\n{question}\n\n"
        f"Tool-Ergebnis (JSON):\n{json.dumps(tool_result, ensure_ascii=False, default=str, indent=2)}\n\n"
        f"Relevante Regeln / Kontexte:\n{json.dumps(context, ensure_ascii=False, default=str, indent=2)}\n\n"
        "Antworte in 4 Teilen:\n"
        "1) direkte Antwort,\n"
        "2) wichtigste Zahlen,\n"
        "3) kurze Begründung,\n"
        "4) empfohlene nächste Aktion.\n"
        "Wenn nach Handlungsbedarf gefragt wird, nenne zusätzlich die Definition in einem Satz."
    )