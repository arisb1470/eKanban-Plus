from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RouteDecision:
    tool_name: str
    drum_id: int | None = None
    horizon_days: int | None = None


def _extract_drum_id(question: str) -> int | None:
    match = re.search(r"(?:trommel|drum|id)\s*[:#]?\s*(\d+)", question.lower())
    if match:
        return int(match.group(1))
    return None


def _extract_horizon_days(question: str) -> int | None:
    q = question.lower()

    patterns = [
        r"nächsten\s+(\d+)\s+tage",
        r"naechsten\s+(\d+)\s+tage",
        r"in\s+(\d+)\s+tagen",
        r"innerhalb\s+von\s+(\d+)\s+tagen",
        r"(\d+)\s*-\s*tage",
        r"(\d+)\s*tage",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass

    return None


def route_question(question: str) -> RouteDecision:
    q = question.strip().lower()
    drum_id = _extract_drum_id(q)
    horizon_days = _extract_horizon_days(q)

    handlungsbedarf_terms = [
        "handlungsbedarf",
        "aktionsbedarf",
        "aufmerksam",
        "aufmerksamkeit",
        "kritisch",
        "kritische trommeln",
        "kritische drums",
        "engpass",
        "engpässe",
        "engpaesse",
        "stockout",
        "leer",
        "leer laufen",
        "bald leer",
        "bestellen",
        "bestelltermin",
        "spätester bestelltermin",
        "spaetester bestelltermin",
        "risiko",
        "risiken",
    ]

    bundle_terms = [
        "bündel",
        "buendel",
        "bündeln",
        "buendeln",
        "gebündelt",
        "gebuendelt",
        "sammelbestellung",
        "gemeinsam bestellen",
        "einsparung",
        "einsparen",
        "sparen",
    ]

    status_terms = [
        "status",
        "wie ist",
        "wie steht",
        "restreichweite",
        "wann muss",
        "wann bestellen",
        "wann nachbestellen",
        "wann ist leer",
    ]

    if drum_id is not None and (any(term in q for term in status_terms) or "trommel" in q):
        return RouteDecision(tool_name="get_drum_status", drum_id=drum_id)

    if any(term in q for term in handlungsbedarf_terms):
        return RouteDecision(
            tool_name="find_critical_drums",
            horizon_days=horizon_days or 30,
        )

    if any(term in q for term in bundle_terms):
        return RouteDecision(
            tool_name="build_bundle_candidates",
            horizon_days=horizon_days or 14,
        )

    return RouteDecision(tool_name="get_general_summary")