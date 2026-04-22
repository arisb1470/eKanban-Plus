from __future__ import annotations

import hashlib

import pandas as pd

from src.analytics import compare_individual_vs_bundle, get_snapshot_as_of
from src.config import DEFAULT_BUNDLE_HORIZON_DAYS, DEFAULT_BUNDLE_WINDOW_DAYS


def _bundle_id(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]


def _priority_label(group: pd.DataFrame) -> str:
    labels = group["risk_label"].astype("string").str.lower()
    if labels.eq("kritisch").any():
        return "hoch"
    if labels.isin(["hoch", "mittel", "bald fällig", "beobachten"]).any():
        return "mittel"
    return "niedrig"


def _cluster_group(group: pd.DataFrame, window_days: int) -> list[pd.DataFrame]:
    """
    Sortiert Trommeln nach latest_safe_order_date und bildet Cluster,
    in denen der Abstand zwischen erstem und letztem Datum <= window_days bleibt.
    """
    if group.empty:
        return []

    group = group.sort_values(["latest_safe_order_date", "days_left"], na_position="last").copy()
    clusters: list[pd.DataFrame] = []

    current_rows = []
    current_start = None

    for _, row in group.iterrows():
        row_date = pd.Timestamp(row["latest_safe_order_date"]).normalize()

        if current_start is None:
            current_start = row_date
            current_rows = [row]
            continue

        if (row_date - current_start).days <= window_days:
            current_rows.append(row)
        else:
            clusters.append(pd.DataFrame(current_rows))
            current_start = row_date
            current_rows = [row]

    if current_rows:
        clusters.append(pd.DataFrame(current_rows))

    return clusters


def build_bundle_candidates(
    latest_snapshot: pd.DataFrame,
    horizon_days: int = DEFAULT_BUNDLE_HORIZON_DAYS,
    window_days: int = DEFAULT_BUNDLE_WINDOW_DAYS,
) -> pd.DataFrame:
    if latest_snapshot.empty:
        return pd.DataFrame()

    df = latest_snapshot.copy()
    reference_date = get_snapshot_as_of(df)

    df = df[df["latest_safe_order_date"].notna()].copy()
    df = df[df["latest_safe_order_date"].dt.normalize() <= reference_date + pd.Timedelta(days=horizon_days)]

    if df.empty:
        return pd.DataFrame()

    all_bundle_rows: list[dict[str, object]] = []

    for (tenant, rack), sub in df.groupby(["tenant", "rack"], dropna=False):
        for cluster in _cluster_group(sub, window_days=window_days):
            if cluster.empty:
                continue

            cost_compare = compare_individual_vs_bundle(cluster)
            recommended_order_date = cluster["latest_safe_order_date"].min()
            latest_due_date = cluster["latest_safe_order_date"].max()

            seed = f"{tenant}|{rack}|{recommended_order_date}|{latest_due_date}|{','.join(cluster['drum_id'].astype(int).astype(str))}"

            all_bundle_rows.append(
                {
                    "bundle_id": _bundle_id(seed),
                    "tenant": tenant,
                    "rack": rack,
                    "recommended_order_date": recommended_order_date,
                    "latest_due_date": latest_due_date,
                    "drum_count": int(cluster["drum_id"].nunique()),
                    "drum_ids": ", ".join(cluster["drum_id"].astype(int).astype(str).tolist()),
                    "bundle_value_eur": cost_compare["bundle_value_eur"],
                    "bundle_cutting_eur": cost_compare["bundle_cutting_eur"],
                    "individual_total_eur": cost_compare["individual_total_eur"],
                    "bundle_total_eur": cost_compare["bundle_total_eur"],
                    "savings_eur": cost_compare["savings_eur"],
                    "bundle_shipping_eur": cost_compare["bundle_shipping_eur"],
                    "bundle_surcharge_eur": cost_compare["bundle_surcharge_eur"],
                    "priority": _priority_label(cluster),
                }
            )

    bundles = pd.DataFrame(all_bundle_rows)
    if bundles.empty:
        return bundles

    return bundles.sort_values(
        ["recommended_order_date", "priority", "savings_eur"],
        ascending=[True, True, False],
        na_position="last",
    ).reset_index(drop=True)


def bundle_details(latest_snapshot: pd.DataFrame, bundle_id: str, bundles: pd.DataFrame) -> pd.DataFrame:
    if latest_snapshot.empty or bundles.empty:
        return pd.DataFrame()

    selected = bundles.loc[bundles["bundle_id"] == bundle_id]
    if selected.empty:
        return pd.DataFrame()

    row = selected.iloc[0]
    drum_ids = {int(x.strip()) for x in str(row["drum_ids"]).split(",") if x.strip()}
    details = latest_snapshot[latest_snapshot["drum_id"].astype("Int64").isin(drum_ids)].copy()

    return details.sort_values(["latest_safe_order_date", "days_left"], na_position="last")