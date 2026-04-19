from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.config import RAW_DATA_DIR


@dataclass
class DataBundle:
    racks: dict[str, pd.DataFrame]
    pricing: pd.DataFrame
    single_drums: dict[str, pd.DataFrame]
    source_files: dict[str, str]

    @property
    def has_core_data(self) -> bool:
        return bool(self.racks) and not self.pricing.empty

    @property
    def all_rack_rows(self) -> int:
        return sum(len(df) for df in self.racks.values())

    @property
    def all_drum_count(self) -> int:
        if not self.racks:
            return 0
        frames = [df[["drum_id"]].drop_duplicates() for df in self.racks.values() if "drum_id" in df.columns]
        if not frames:
            return 0
        return pd.concat(frames, ignore_index=True)["drum_id"].nunique()


EXPECTED_NUMERIC_COLUMNS = [
    "drum_id",
    "days_elapsed",
    "daily_min_cable_length_m",
    "daily_max_cable_length_m",
    "daily_avg_cable_length_m",
    "linear_forecast_m",
    "forecast_error_m",
    "sensor_readings_count",
    "avg_battery_voltage",
    "avg_signal_strength",
    "initial_cable_length_m",
    "order_threshold_m",
    "depletion_rate_m_per_day",
    "r_squared",
    "price_per_meter_eur",
    "delivery_time_days",
    "packaging_unit_m",
]

DATE_COLUMNS = ["date"]


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    clean.columns = [c.strip() for c in clean.columns]
    for col in DATE_COLUMNS:
        if col in clean.columns:
            clean[col] = pd.to_datetime(clean[col], errors="coerce")
    for col in EXPECTED_NUMERIC_COLUMNS:
        if col in clean.columns:
            clean[col] = pd.to_numeric(clean[col], errors="coerce")
    for col in ["tenant", "rack", "product", "part_number", "product_name"]:
        if col in clean.columns:
            clean[col] = clean[col].astype("string")
    return clean


def _load_csv(path: Path) -> pd.DataFrame:
    return _standardize_columns(pd.read_csv(path))


def _discover_rack_files(raw_dir: Path) -> dict[str, Path]:
    rack_files: dict[str, Path] = {}
    for path in sorted(raw_dir.glob("*.csv")):
        name = path.stem.lower()
        if "pricing" in name or "leadtimes" in name:
            continue
        rack_files[path.stem] = path
    return rack_files


def _discover_pricing_file(raw_dir: Path) -> Path | None:
    candidates = sorted(raw_dir.glob("*pricing*.csv")) + sorted(raw_dir.glob("*leadtimes*.csv"))
    return candidates[0] if candidates else None


def _discover_single_drums(raw_dir: Path) -> dict[str, Path]:
    single_dir = raw_dir / "einzeltrommeln"
    if not single_dir.exists():
        return {}
    return {path.stem: path for path in sorted(single_dir.glob("*.csv"))}


@st.cache_data(show_spinner=False)
def load_data(raw_data_dir: str | Path = RAW_DATA_DIR) -> DataBundle:
    raw_dir = Path(raw_data_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    rack_paths = _discover_rack_files(raw_dir)
    pricing_path = _discover_pricing_file(raw_dir)
    single_drum_paths = _discover_single_drums(raw_dir)

    racks = {name: _load_csv(path) for name, path in rack_paths.items()}
    pricing = _load_csv(pricing_path) if pricing_path else pd.DataFrame()
    single_drums = {name: _load_csv(path) for name, path in single_drum_paths.items()}

    source_files: dict[str, str] = {
        **{f"rack::{name}": str(path.relative_to(raw_dir.parent)) for name, path in rack_paths.items()},
        **{f"single::{name}": str(path.relative_to(raw_dir.parent)) for name, path in single_drum_paths.items()},
    }
    if pricing_path:
        source_files["pricing"] = str(pricing_path.relative_to(raw_dir.parent))

    return DataBundle(racks=racks, pricing=pricing, single_drums=single_drums, source_files=source_files)


def merge_racks(bundle: DataBundle) -> pd.DataFrame:
    if not bundle.racks:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for rack_name, df in bundle.racks.items():
        copy = df.copy()
        if "source_rack_file" not in copy.columns:
            copy["source_rack_file"] = rack_name
        frames.append(copy)
    return pd.concat(frames, ignore_index=True)


def load_demo_business_rules() -> list[dict[str, Any]]:
    return [
        {
            "title": "Versandkostenfreigrenze",
            "text": "Ab 500 EUR Bestellwert fällt keine Versandkostenpauschale an.",
        },
        {
            "title": "Versandkosten",
            "text": "Unterhalb von 500 EUR Bestellwert werden 25 EUR Versandkosten berechnet.",
        },
        {
            "title": "Mindestbestellwert",
            "text": "Unter 150 EUR netto wird zusätzlich ein Zuschlag von 20 EUR berechnet.",
        },
        {
            "title": "Sicherheitspuffer",
            "text": "Bei der Bestellzeitpunkt-Berechnung wird 1 zusätzlicher Werktag als Puffer berücksichtigt.",
        },
    ]