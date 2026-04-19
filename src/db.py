from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from src.load_data import DataBundle, merge_racks


@st.cache_resource(show_spinner=False)
def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(database=":memory:")


def register_bundle(bundle: DataBundle) -> duckdb.DuckDBPyConnection:
    con = get_connection()
    all_racks = merge_racks(bundle)
    if not all_racks.empty:
        con.register("rack_daily", all_racks)
    if not bundle.pricing.empty:
        con.register("pricing", bundle.pricing)
    for name, df in bundle.single_drums.items():
        con.register(f"single_{name}", df)
    return con


def latest_snapshot_sql() -> str:
    return """
    SELECT *
    FROM rack_daily
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY drum_id
        ORDER BY date DESC NULLS LAST, days_elapsed DESC NULLS LAST
    ) = 1
    """


def get_latest_snapshot(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    try:
        df = con.sql(latest_snapshot_sql()).df()
    except duckdb.CatalogException:
        return pd.DataFrame()
    return df