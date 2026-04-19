from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RouteDecision:
    tool_name: str
    drum_id: int | None = None
    horizon_days: int | None = None


def _extract_horizon_days(question: str) -> int | None:
    q = question.lower()

    if "heute" in q:
        return 0
    if "morgen" in q:
        return 1
    if "diese woche" in q:
        return 7
    if "nächste woche" in q:
        return 7
    if "diesen monat" in q or "nächsten monat" in q:
        return 30

    match = re.search(r"(\d+)\s*(tage|tag|days|day)", q)
    if match:
        return int(match.group(1))

    return None


def _extract_drum_id(question: str) -> int | None:
    q = question.lower()
    match = re.search(r"(?:trommel|drum|id)\s*[:#]?\s*(\d+)", q)
    if match:
        return int(match.group(1))
    return None


def route_question(question: str) -> RouteDecision:
    q = question.lower()
    drum_id = _extract_drum_id(question)
    horizon_days = _extract_horizon_days(question)

    if drum_id is not None:
        return RouteDecision(tool_name="get_drum_status", drum_id=drum_id)

    if any(term in q for term in ["bündel", "bundle", "bündeln", "versand", "freigrenze", "bestellwert", "kosten sparen"]):
        return RouteDecision(tool_name="build_bundle_candidates", horizon_days=horizon_days or 14)

    if any(term in q for term in ["kritisch", "knapp", "stockout", "leer", "risiko", "engpass", "kritische trommeln"]):
        return RouteDecision(tool_name="find_critical_drums", horizon_days=horizon_days or 7)

    if any(term in q for term in ["bestellen", "bestelltag", "reorder", "nachbestellen", "wann ordern"]):
        return RouteDecision(tool_name="find_critical_drums", horizon_days=horizon_days or 7)

    if any(term in q for term in ["übersicht", "summary", "zusammenfassung", "gesamtbild", "status"]):
        return RouteDecision(tool_name="general_summary", horizon_days=horizon_days)

    return RouteDecision(tool_name="general_summary", horizon_days=horizon_days)