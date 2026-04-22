from __future__ import annotations

from typing import Any

import pandas as pd

from src.analytics import build_kpis, display_snapshot, filter_critical_drums
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
    "forecast_status",
    "forecast_confidence",
    "risk_label",
    "attention_reason",
]


def _frame_preview(df: pd.DataFrame, columns: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if df.empty:
        return []

    cols = [c for c in (columns or df.columns.tolist()) if c in df.columns]
    preview = display_snapshot(df[cols].head(limit).copy())
    preview = preview.where(pd.notnull(preview), None)
    return mask_tenant_records(preview.to_dict(orient="records"))


def _reference_date(snapshot: pd.DataFrame) -> pd.Timestamp:
    for column in ["snapshot_as_of_date", "date"]:
        if column in snapshot.columns and snapshot[column].notna().any():
            return pd.to_datetime(snapshot[column], errors="coerce").dropna().max().normalize()
    return pd.Timestamp.today().normalize()


def get_general_summary(snapshot: pd.DataFrame) -> dict[str, Any]:
    kpis = build_kpis(snapshot)
    summary = (
        f"Im aktuellen Datenstand sind {kpis['drums']} Trommeln enthalten. "
        f"Davon haben {kpis['attention']} Trommeln Handlungsbedarf, "
        f"{kpis['critical']} sind kritisch und {kpis['review']} haben Prüfbedarf. "
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
    forecast_status = row.get("forecast_status", "ok")

    if pd.notna(row.get("days_left")):
        range_text = f"eine Restreichweite von {row.get('days_left')} Tagen"
    elif forecast_status == "kein aktueller Verbrauch":
        range_text = "aktuell keinen erkennbaren Verbrauch"
    elif forecast_status == "keine Verbrauchsdaten":
        range_text = "keine ausreichenden Verbrauchsdaten für eine Prognose"
    else:
        range_text = "eine unsichere Restreichweiten-Prognose"

    summary = (
        f"Trommel {drum_id} in {row.get('rack', 'unbekannt')} "
        f"hat aktuell {row.get('current_length_m', 'n/a')} m Bestand, "
        f"{range_text}, den Prognosestatus '{forecast_status}' "
        f"und den Risikostatus '{row.get('risk_label', 'unbekannt')}'."
    )

    return {
        "summary": summary,
        "drum": _frame_preview(df, JSON_COLUMNS, limit=1),
        "data_preview": _frame_preview(df, JSON_COLUMNS, limit=1),
    }


def find_critical_drums(snapshot: pd.DataFrame, horizon_days: int = 30) -> dict[str, Any]:
    critical = filter_critical_drums(snapshot, horizon_days=horizon_days).copy()

    if critical.empty:
        return {
            "summary": f"Es gibt aktuell keine Trommeln mit Handlungsbedarf im Horizont von {horizon_days} Tagen.",
            "horizon_days": horizon_days,
            "count": 0,
            "definition": (
                "Handlungsbedarf bedeutet: Risikostatus kritisch/hoch/mittel "
                "oder Restreichweite innerhalb des Horizonts oder spätester sicherer Bestelltermin innerhalb des Horizonts."
            ),
            "data_preview": [],
        }

    as_of_date = _reference_date(snapshot)
    horizon_date = as_of_date + pd.Timedelta(days=horizon_days)

    risk_label_series = critical.get("risk_label", pd.Series(index=critical.index, dtype="object"))
    risk_reason = risk_label_series.astype("string").str.lower().isin(["kritisch", "hoch", "mittel", "bald fällig", "beobachten"])

    days_left_series = pd.to_numeric(critical.get("days_left"), errors="coerce")
    days_left_reason = days_left_series <= horizon_days

    safe_order_series = pd.to_datetime(critical.get("latest_safe_order_date"), errors="coerce")
    safe_order_reason = safe_order_series.notna() & (safe_order_series <= horizon_date)

    critical["attention_reason"] = ""

    reasons: list[str] = []
    for idx in critical.index:
        row_reasons: list[str] = []

        if bool(risk_reason.loc[idx]):
            row_reasons.append(f"Risikostatus: {critical.loc[idx, 'risk_label']}")

        if pd.notna(days_left_series.loc[idx]) and bool(days_left_reason.loc[idx]):
            row_reasons.append(f"Restreichweite ≤ {horizon_days} Tage")

        if pd.notna(safe_order_series.loc[idx]) and bool(safe_order_reason.loc[idx]):
            row_reasons.append("spätester Bestelltermin liegt im Horizont")

        if not row_reasons:
            row_reasons.append("durch kombinierte Handlungslogik markiert")

        reason_text = "; ".join(row_reasons)
        critical.loc[idx, "attention_reason"] = reason_text
        reasons.append(reason_text)

    risk_count = int(risk_reason.fillna(False).sum())
    days_left_count = int(days_left_reason.fillna(False).sum())
    safe_order_count = int(safe_order_reason.fillna(False).sum())

    summary = (
        f"{len(critical)} Trommeln haben Handlungsbedarf im Horizont von {horizon_days} Tagen. "
        f"Definition: Handlungsbedarf bedeutet mindestens eines der folgenden Kriterien: "
        f"Risikostatus kritisch/hoch/mittel, Restreichweite ≤ {horizon_days} Tage "
        f"oder spätester sicherer Bestelltermin bis {horizon_date.strftime('%d.%m.%Y')}. "
        f"Gründe im aktuellen Ergebnis (Mehrfachnennungen möglich): "
        f"{risk_count} wegen Risikostatus, "
        f"{days_left_count} wegen Restreichweite im Horizont, "
        f"{safe_order_count} wegen Bestelltermin im Horizont."
    )

    preview_columns = [
        "drum_id",
        "rack",
        "product",
        "current_length_m",
        "days_left",
        "latest_safe_order_date",
        "risk_label",
        "forecast_status",
        "attention_reason",
    ]

    return {
        "summary": summary,
        "horizon_days": horizon_days,
        "count": len(critical),
        "definition": (
            "Handlungsbedarf ist eine Aktionslogik, keine reine Reichweitenlogik. "
            "Er entsteht durch Risikostatus, Restreichweite im Horizont oder sicheren Bestelltermin im Horizont."
        ),
        "reason_breakdown": {
            "risk_status_count": risk_count,
            "days_left_within_horizon_count": days_left_count,
            "safe_order_date_within_horizon_count": safe_order_count,
            "reference_date": as_of_date.strftime("%d.%m.%Y"),
            "horizon_date": horizon_date.strftime("%d.%m.%Y"),
        },
        "data_preview": _frame_preview(critical, preview_columns),
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
        f"bei einem Bündelwert von {best['bundle_value_eur']:.2f} €."
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
        "summary": f"Bündel {bundle_id} enthält {len(details)} Trommeln.",
        "count": len(details),
        "data_preview": _frame_preview(details, JSON_COLUMNS),
    }