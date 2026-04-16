"""Step 2: IFRS 18 Classification — review and adjust auto-detected classifications."""

import streamlit as st
import pandas as pd
import plotly.express as px
from modules.ifrs18_categories import IFRS18Category, BSCategory


_PNL_CATS = [c.value for c in IFRS18Category]
_BS_CATS = [c.value for c in BSCategory]
_CF_CATS = ["CF - Operating", "CF - Investing", "CF - Financing"]


def render_classification():
    st.header("Step 2: IFRS 18 Classification")

    loaded = st.session_state.get("loaded_statements", set())
    if not loaded:
        st.warning("Please load data in Step 1 first.")
        return

    entity_type = st.session_state.get("entity_type", "General (non-financial)")
    if entity_type != "General (non-financial)":
        st.info(
            f"**Entity type: {entity_type}** — Items related to main business activity "
            f"have been reclassified to Operating per IFRS 18."
        )

    # --- P&L ---
    if "classified_pnl" in st.session_state:
        _render_pnl_section(st.session_state["classified_pnl"])

    # --- BS ---
    if "classified_bs" in st.session_state:
        _render_bs_section(st.session_state["classified_bs"])

    # --- CF ---
    if "classified_cf" in st.session_state:
        _render_cf_section(st.session_state["classified_cf"])

    # --- Save ---
    if st.button("Confirm All Classifications", type="primary"):
        # Re-read from editors (keyed via data_editor)
        if "classified_pnl" in st.session_state:
            st.session_state["classified_pnl"] = st.session_state.get(
                "_edited_pnl", st.session_state["classified_pnl"]
            )
        if "classified_bs" in st.session_state:
            st.session_state["classified_bs"] = st.session_state.get(
                "_edited_bs", st.session_state["classified_bs"]
            )
        if "classified_cf" in st.session_state:
            st.session_state["classified_cf"] = st.session_state.get(
                "_edited_cf", st.session_state["classified_cf"]
            )
        st.session_state["classifications_confirmed"] = True
        from modules.persistence import auto_save
        auto_save()
        st.success("Classifications saved! Proceed to Step 3.")


def _amount_cols(df):
    return [c for c in df.columns if c not in ("Account", "Category", "Statement")]


def _render_pnl_section(df):
    st.subheader("Income Statement (P&L) — IFRS 18 Categories")
    st.markdown(
        "Every P&L item is classified into one of the **five IFRS 18 categories**. "
        "Adjust as needed."
    )

    with st.expander("IFRS 18 P&L Classification Rules"):
        st.markdown("""
**Operating** (residual/default): All income and expenses not classified elsewhere.

**Investing**: Returns from assets that generate returns individually and largely
independently — dividend/interest income, rental income, FV gains/losses on
investments, share of profit of associates/JVs.

**Financing**: Cost of raising finance — interest on loans/bonds, lease interest,
unwinding of discount, FX on borrowings.

**Income Tax**: Current and deferred tax per IAS 12.

**Discontinued Operations**: Per IFRS 5.
        """)

    edited = st.data_editor(
        df,
        column_config={
            "Account": st.column_config.TextColumn("Account", disabled=True),
            "Statement": st.column_config.TextColumn("Statement", disabled=True),
            "Category": st.column_config.SelectboxColumn(
                "IFRS 18 Category", options=_PNL_CATS, required=True, width="medium",
            ),
        },
        use_container_width=True, hide_index=True, key="pnl_editor",
    )
    st.session_state["_edited_pnl"] = edited

    # Summary
    cols = _amount_cols(edited)
    if cols:
        summary = edited.groupby("Category")[cols[0]].sum().reindex(_PNL_CATS).fillna(0)
        c1, c2 = st.columns(2)
        with c1:
            st.dataframe(
                summary.reset_index().rename(columns={"Category": "IFRS 18 Category", cols[0]: "Total"}),
                use_container_width=True, hide_index=True,
            )
        with c2:
            non_zero = summary[summary != 0]
            if len(non_zero) > 0:
                fig = px.pie(
                    values=non_zero.abs().values, names=non_zero.index,
                    title="P&L by IFRS 18 Category",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                st.plotly_chart(fig, use_container_width=True)


def _render_bs_section(df):
    st.markdown("---")
    st.subheader("Balance Sheet — Classification")
    st.markdown(
        "Balance sheet items are grouped into standard categories. "
        "IFRS 18 has minimal changes to BS presentation but introduces new "
        "**aggregation and disaggregation** guidance (see Step 3)."
    )

    edited = st.data_editor(
        df,
        column_config={
            "Account": st.column_config.TextColumn("Account", disabled=True),
            "Statement": st.column_config.TextColumn("Statement", disabled=True),
            "Category": st.column_config.SelectboxColumn(
                "BS Category", options=_BS_CATS, required=True, width="medium",
            ),
        },
        use_container_width=True, hide_index=True, key="bs_editor",
    )
    st.session_state["_edited_bs"] = edited

    cols = _amount_cols(edited)
    if cols:
        summary = edited.groupby("Category")[cols[0]].sum().reindex(_BS_CATS).fillna(0)
        st.dataframe(
            summary.reset_index().rename(columns={"Category": "BS Category", cols[0]: "Total"}),
            use_container_width=True, hide_index=True,
        )


def _render_cf_section(df):
    st.markdown("---")
    st.subheader("Cash Flow Statement — Classification")
    st.markdown(
        "Cash flow items classified by activity type. "
        "IFRS 18 introduces specific changes to the cash flow statement (see Step 5)."
    )

    edited = st.data_editor(
        df,
        column_config={
            "Account": st.column_config.TextColumn("Account", disabled=True),
            "Statement": st.column_config.TextColumn("Statement", disabled=True),
            "Category": st.column_config.SelectboxColumn(
                "CF Activity", options=_CF_CATS, required=True, width="medium",
            ),
        },
        use_container_width=True, hide_index=True, key="cf_editor",
    )
    st.session_state["_edited_cf"] = edited

    cols = _amount_cols(edited)
    if cols:
        summary = edited.groupby("Category")[cols[0]].sum().reindex(_CF_CATS).fillna(0)
        st.dataframe(
            summary.reset_index().rename(columns={"Category": "Activity", cols[0]: "Total"}),
            use_container_width=True, hide_index=True,
        )
