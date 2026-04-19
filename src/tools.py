from __future__ import annotations

from typing import Any

import pandas as pd

from src.analytics import build_kpis, filter_critical_drums
from src.auth import mask_tenant_records
from src.bundling import build_bundle_candidates, bundle_details


JSON_COLUMNS = [
    "drum_id",
    "rack",
    "product",
    "part_number",
    "current_length_m",
    "days_left",
    "predicted_empty_date",
    "latest_safe_order_date",
    "estimated_order_value_eur",
    "forecast_confidence",
    "risk_label",
]


def _frame_preview(df: pd.DataFrame, columns: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if df.empty:
        return []

    cols = [c for c in (columns or df.columns.tolist()) if c in df.columns]
    preview = df[cols].head(limit).copy()
    preview = preview.where(pd.notnull(preview), None)
    return mask_tenant_records(preview.to_dict(orient="records"))


def get_general_summary(snapshot: pd.DataFrame) -> dict[str, Any]:
    kpis = build_kpis(snapshot)
    summary = (
        f"Im aktuellen Snapshot sind {kpis['drums']} Trommeln enthalten. "
        f"Davon sind {kpis['critical']} kritisch und {kpis['attention']} benötigen Aufmerksamkeit. "
        f"Die durchschnittliche Restreichweite beträgt {kpis['avg_days_left']} Tage."
    )
    return {
        "summary": summary,
        "kpis": kpis,
        "data_preview": _frame_preview(snapshot, JSON_COLUMNS),
    }


def get_drum_status(snapshot: pd.DataFrame, drum_id: int) -> dict[str, Any]:
    df = snapshot.loc[snapshot["drum_id"].astype("Int64") == drum_id].copy()
    if df.empty:
        return {
            "summary": f"Für Trommel {drum_id} wurde kein Datensatz gefunden.",
            "data_preview": [],
        }

    row = df.iloc[0]
    summary = (
        f"Trommel {drum_id} in {row.get('rack', 'unbekannt')} "
        f"hat aktuell {row.get('current_length_m', 'n/a')} m Bestand, "
        f"eine Restreichweite von {row.get('days_left', 'n/a')} Tagen "
        f"und den Risikostatus '{row.get('risk_label', 'unbekannt')}'."
    )

    return {
        "summary": summary,
        "drum": _frame_preview(df, JSON_COLUMNS, limit=1),
        "data_preview": _frame_preview(df, JSON_COLUMNS, limit=1),
    }


def find_critical_drums(snapshot: pd.DataFrame, horizon_days: int = 7) -> dict[str, Any]:
    critical = filter_critical_drums(snapshot, horizon_days=horizon_days)

    summary = (
        f"{len(critical)} Trommeln benötigen im Horizont von {horizon_days} Tagen Aufmerksamkeit."
    )

    return {
        "summary": summary,
        "horizon_days": horizon_days,
        "count": len(critical),
        "data_preview": _frame_preview(critical, JSON_COLUMNS),
    }


def get_bundle_candidates(snapshot: pd.DataFrame, horizon_days: int = 14) -> dict[str, Any]:
    bundles = build_bundle_candidates(snapshot, horizon_days=horizon_days)

    columns = [
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

    if bundles.empty:
        return {
            "summary": f"Es wurden keine Bündel-Kandidaten für die nächsten {horizon_days} Tage gefunden.",
            "horizon_days": horizon_days,
            "count": 0,
            "data_preview": [],
        }

    best = bundles.iloc[0]
    summary = (
        f"Es wurden {len(bundles)} Bündel-Kandidaten gefunden. "
        f"Der erste Kandidat spart voraussichtlich {best['savings_eur']:.2f} € "
        f"bei einem Bundle-Wert von {best['bundle_value_eur']:.2f} €."
    )

    return {
        "summary": summary,
        "horizon_days": horizon_days,
        "count": len(bundles),
        "data_preview": _frame_preview(bundles, columns),
    }


def get_bundle_details(snapshot: pd.DataFrame, bundles: pd.DataFrame, bundle_id: str) -> dict[str, Any]:
    details = bundle_details(snapshot, bundle_id, bundles)

    return {
        "summary": f"Bundle {bundle_id} enthält {len(details)} Trommeln.",
        "count": len(details),
        "data_preview": _frame_preview(details, JSON_COLUMNS),
    }