from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from src.config import DEFAULT_DEMO_PASSWORD
from src.load_data import DataBundle

SESSION_AUTHENTICATED = "authenticated_customer"
DEFAULT_CUSTOMERS = ("Kunde A", "Kunde B")


def _secrets_customer_passwords() -> dict[str, str]:
    try:
        configured = st.secrets.get("CUSTOMER_PASSWORDS", {})
    except Exception:
        configured = {}

    if isinstance(configured, Mapping) and len(configured) > 0:
        return {str(key): str(value) for key, value in configured.items()}

    return {}


def _available_customers(bundle: DataBundle | None = None) -> list[str]:
    customers: list[str] = []

    if bundle is not None:
        for df in bundle.racks.values():
            if "tenant" not in df.columns:
                continue

            values = (
                df["tenant"]
                .dropna()
                .astype("string")
                .str.strip()
                .dropna()
                .unique()
                .tolist()
            )
            customers.extend([str(value) for value in values if str(value)])

    if customers:
        return sorted(set(customers))

    configured = _secrets_customer_passwords()
    if configured:
        return sorted(configured.keys())

    return list(DEFAULT_CUSTOMERS)


def _customer_passwords(customers: list[str]) -> dict[str, str]:
    configured = _secrets_customer_passwords()
    if configured:
        return configured

    return {customer: DEFAULT_DEMO_PASSWORD for customer in customers}


def get_current_customer() -> str | None:
    customer = st.session_state.get(SESSION_AUTHENTICATED)
    return str(customer) if customer else None


def is_authenticated() -> bool:
    return get_current_customer() is not None


def logout() -> None:
    st.session_state.pop(SESSION_AUTHENTICATED, None)
    st.session_state.pop("messages", None)
    st.session_state.pop("chat_customer", None)


def _show_login_form(customers: list[str], passwords: dict[str, str]) -> None:
    from src.ui import render_page_header

    render_page_header(
        "LAPP eKanban Plus",
        "Bitte mit dem eigenen Kundenkonto anmelden.",
    )

    configured = _secrets_customer_passwords()
    using_demo_passwords = len(configured) == 0
    if using_demo_passwords:
        st.info(
            f"Demo-Anmeldungen aktiv. Standardpasswort für alle Konten: `{DEFAULT_DEMO_PASSWORD}`. Bitte die Passwörter in `.streamlit/secrets.toml` unter `CUSTOMER_PASSWORDS` ersetzen."
        )

    with st.form("login_form", clear_on_submit=False):
        customer = st.selectbox("Konto", options=customers)
        password = st.text_input("Passwort", type="password")
        submitted = st.form_submit_button("Anmelden", use_container_width=True)

    if not submitted:
        return

    expected_password = passwords.get(customer)
    if expected_password is not None and password == expected_password:
        st.session_state[SESSION_AUTHENTICATED] = customer
        st.session_state.pop("messages", None)
        st.session_state.pop("chat_customer", None)
        st.rerun()

    st.error("Login fehlgeschlagen. Bitte Konto und Passwort prüfen.")


def require_login(bundle: DataBundle | None = None) -> str:
    if is_authenticated():
        return get_current_customer() or ""

    customers = _available_customers(bundle)
    passwords = _customer_passwords(customers)

    left, center, right = st.columns([1, 1.2, 1])
    with center:
        _show_login_form(customers, passwords)
    st.stop()


def render_sidebar_auth() -> str:
    customer = get_current_customer()
    if not customer:
        return ""

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-account-card">
                <div class="sidebar-account-card__label">Kundenkonto</div>
                <div class="sidebar-account-card__value">{customer}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Abmelden", use_container_width=True):
            logout()
            st.rerun()
    return customer


def filter_df_for_customer(df: pd.DataFrame, customer: str | None) -> pd.DataFrame:
    if df.empty or not customer or "tenant" not in df.columns:
        return df.copy()

    tenant_values = df["tenant"].astype("string").str.strip()
    return df.loc[tenant_values == str(customer)].copy()


def scope_bundle_to_customer(bundle: DataBundle, customer: str | None) -> DataBundle:
    if not customer:
        return bundle

    racks = {name: filter_df_for_customer(df, customer) for name, df in bundle.racks.items()}
    racks = {name: df for name, df in racks.items() if not df.empty}

    single_drums = {name: filter_df_for_customer(df, customer) for name, df in bundle.single_drums.items()}
    single_drums = {name: df for name, df in single_drums.items() if not df.empty}

    return DataBundle(
        racks=racks,
        pricing=bundle.pricing.copy(),
        single_drums=single_drums,
        source_files=bundle.source_files.copy(),
    )


def without_tenant(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "tenant" not in df.columns:
        return df.copy()
    return df.drop(columns=["tenant"])


def mask_tenant_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        clean = {key: value for key, value in record.items() if key != "tenant"}
        out.append(clean)
    return out