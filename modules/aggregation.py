"""Aggregation & Disaggregation Analysis — IFRS 18 requirements for P&L and BS.

IFRS 18 introduces enhanced guidance on how to aggregate/disaggregate items:
- Items with shared characteristics -> aggregate
- Items with dissimilar characteristics -> disaggregate
- Must not obscure material information
- Primary statements: structured summary; Notes: disaggregated detail
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from modules.ifrs18_categories import IFRS18Category, BSCategory


def _amount_cols(df):
    return [c for c in df.columns if c not in ("Account", "Category", "Statement")]


def render_aggregation():
    st.header("Aggregation & Disaggregation Analysis")

    st.markdown("""
IFRS 18 significantly strengthens the requirements around **aggregation and
disaggregation** of line items in both the income statement and balance sheet.

**Key principles:**
- Items sharing characteristics (nature, function, measurement basis) should be **aggregated**
- Items with dissimilar characteristics should be **disaggregated**
- Aggregation must not **obscure material information**
- Primary statements provide a structured summary; **notes** provide disaggregated detail
- If expenses are presented by **function**, disaggregation by **nature** must be disclosed in notes
    """)

    has_pnl = "classified_pnl" in st.session_state
    has_bs = "classified_bs" in st.session_state

    if not has_pnl and not has_bs:
        st.warning("Please complete Steps 1-2 first.")
        return

    if has_pnl:
        _render_pnl_aggregation()

    if has_bs:
        _render_bs_aggregation()


# ---------------------------------------------------------------------------
# P&L Aggregation Analysis
# ---------------------------------------------------------------------------

def _render_pnl_aggregation():
    st.subheader("Income Statement — Aggregation Analysis")

    df = st.session_state["classified_pnl"]
    cols = _amount_cols(df)
    if not cols:
        return
    col = cols[0]

    # --- Materiality threshold ---
    total_revenue = df[df[col] > 0][col].sum()
    total_expenses = df[df[col] < 0][col].abs().sum()
    materiality_base = max(total_revenue, total_expenses)

    st.markdown("#### Materiality Threshold")
    threshold_pct = st.slider(
        "Materiality threshold (% of revenue/total expenses)",
        min_value=1, max_value=20, value=5, step=1,
        key="pnl_materiality",
    )
    threshold = materiality_base * threshold_pct / 100
    st.caption(
        f"Base: {materiality_base:,.0f} | Threshold ({threshold_pct}%): {threshold:,.0f}"
    )

    # --- Classify items as material / immaterial ---
    df_analysis = df[["Account", "Category", col]].copy()
    df_analysis["Absolute"] = df_analysis[col].abs()
    df_analysis["Material"] = df_analysis["Absolute"] >= threshold
    df_analysis["% of Base"] = (df_analysis["Absolute"] / materiality_base * 100).round(1)

    # --- Items that should be shown separately (material) ---
    st.markdown("#### Material Items — Present Separately on Face of P&L")
    material = df_analysis[df_analysis["Material"]].sort_values("Absolute", ascending=False)
    if len(material) > 0:
        st.dataframe(
            material[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No individually material items found at this threshold.")

    # --- Items that could be aggregated (immaterial individually) ---
    st.markdown("#### Candidates for Aggregation — Below Materiality")
    immaterial = df_analysis[~df_analysis["Material"]].sort_values("Absolute", ascending=False)
    if len(immaterial) > 0:
        st.dataframe(
            immaterial[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

        # Suggest aggregation groups
        st.markdown("**Suggested Aggregation Groups** (items sharing same IFRS 18 category):")
        for cat in [c.value for c in IFRS18Category]:
            cat_immaterial = immaterial[immaterial["Category"] == cat]
            if len(cat_immaterial) > 1:
                items = ", ".join(cat_immaterial["Account"].tolist())
                total = cat_immaterial[col].sum()
                st.markdown(
                    f"- **{cat}**: {items} → could be aggregated as "
                    f"\"Other {cat.lower()} items\" ({total:,.0f})"
                )
    else:
        st.success("All items are individually material — no aggregation needed.")

    # --- Function vs Nature analysis ---
    st.markdown("---")
    st.markdown("#### Expense Presentation: Function vs Nature")
    st.markdown(
        "IFRS 18 requires that if expenses are presented by **function** "
        "(e.g. Cost of Sales, Admin, Distribution), a **nature** disaggregation "
        "must be disclosed in the notes."
    )

    # Detect if current presentation is by function or nature
    function_keywords = ["cost of sales", "selling", "distribution", "administrative", "admin"]
    nature_keywords = ["depreciation", "amortisation", "employee", "staff", "wages", "raw material"]

    accounts_lower = df["Account"].str.lower()
    function_count = sum(1 for a in accounts_lower if any(kw in a for kw in function_keywords))
    nature_count = sum(1 for a in accounts_lower if any(kw in a for kw in nature_keywords))

    if function_count > nature_count:
        presentation = "By Function"
        st.warning(
            f"Your P&L appears to present expenses **by function** "
            f"({function_count} function items vs {nature_count} nature items). "
            f"Under IFRS 18, you must disclose a **nature disaggregation in the notes** "
            f"covering at least: depreciation, amortisation, employee benefits, and "
            f"write-downs of inventories."
        )
    elif nature_count > function_count:
        presentation = "By Nature"
        st.success(
            f"Your P&L presents expenses **by nature** ({nature_count} nature items). "
            f"No additional nature disclosure is required in the notes."
        )
    else:
        presentation = "Mixed"
        st.info(
            "Your P&L uses a **mixed** presentation. Review whether additional "
            "nature disaggregation is needed in the notes."
        )

    st.session_state["expense_presentation"] = presentation

    # --- Aggregated P&L preview ---
    st.markdown("---")
    st.markdown("#### Preview: Aggregated IFRS 18 P&L")
    st.markdown(
        "Below shows what the P&L would look like with immaterial items aggregated "
        "within each category."
    )

    preview_rows = []
    for cat in [c.value for c in IFRS18Category]:
        cat_items = df_analysis[df_analysis["Category"] == cat]
        if cat_items.empty:
            continue

        cat_material = cat_items[cat_items["Material"]]
        cat_immaterial = cat_items[~cat_items["Material"]]

        for _, row in cat_material.iterrows():
            preview_rows.append({
                "Line Item": row["Account"],
                "Category": cat,
                col: row[col],
                "Status": "Presented separately",
            })

        if len(cat_immaterial) > 0:
            agg_total = cat_immaterial[col].sum()
            n = len(cat_immaterial)
            preview_rows.append({
                "Line Item": f"Other {cat.lower()} items ({n} items)",
                "Category": cat,
                col: agg_total,
                "Status": f"Aggregated ({n} items)",
            })

    preview_df = pd.DataFrame(preview_rows)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    original_lines = len(df)
    aggregated_lines = len(preview_df)
    st.caption(
        f"Reduced from {original_lines} line items to {aggregated_lines} "
        f"(aggregated {original_lines - aggregated_lines} immaterial items)"
    )


# ---------------------------------------------------------------------------
# BS Aggregation Analysis
# ---------------------------------------------------------------------------

def _render_bs_aggregation():
    st.markdown("---")
    st.subheader("Balance Sheet — Aggregation Analysis")

    df = st.session_state["classified_bs"]
    cols = _amount_cols(df)
    if not cols:
        return
    col = cols[0]

    # Materiality
    total_assets = df[df[col] > 0][col].sum()
    total_liabilities = df[df[col] < 0][col].abs().sum()
    materiality_base = max(total_assets, total_liabilities)

    st.markdown("#### Materiality Threshold")
    threshold_pct = st.slider(
        "Materiality threshold (% of total assets/liabilities)",
        min_value=1, max_value=20, value=5, step=1,
        key="bs_materiality",
    )
    threshold = materiality_base * threshold_pct / 100
    st.caption(f"Base: {materiality_base:,.0f} | Threshold ({threshold_pct}%): {threshold:,.0f}")

    df_analysis = df[["Account", "Category", col]].copy()
    df_analysis["Absolute"] = df_analysis[col].abs()
    df_analysis["Material"] = df_analysis["Absolute"] >= threshold
    df_analysis["% of Base"] = (df_analysis["Absolute"] / materiality_base * 100).round(1)

    # Material items
    st.markdown("#### Material Items — Present Separately")
    material = df_analysis[df_analysis["Material"]].sort_values("Absolute", ascending=False)
    if len(material) > 0:
        st.dataframe(
            material[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

    # Aggregation candidates
    st.markdown("#### Candidates for Aggregation")
    immaterial = df_analysis[~df_analysis["Material"]].sort_values("Absolute", ascending=False)
    if len(immaterial) > 0:
        st.dataframe(
            immaterial[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

        # Suggest groups
        st.markdown("**Suggested Aggregation Groups:**")
        for cat in [c.value for c in BSCategory]:
            cat_items = immaterial[immaterial["Category"] == cat]
            if len(cat_items) > 1:
                items = ", ".join(cat_items["Account"].tolist())
                total = cat_items[col].sum()
                st.markdown(
                    f"- **{cat}**: {items} → aggregate as "
                    f"\"Other {cat.lower()}\" ({total:,.0f})"
                )
    else:
        st.success("All BS items are individually material.")

    # IFRS 18 BS minimum line items check
    st.markdown("---")
    st.markdown("#### IFRS 18 / IAS 1 Minimum Line Items Check")
    st.markdown(
        "IFRS 18 retains the minimum line items required by IAS 1 on the face of the BS. "
        "Check whether your BS includes at least these items:"
    )

    min_items = {
        "Property, plant and equipment": ["property plant", "ppe"],
        "Investment property": ["investment property"],
        "Intangible assets": ["intangible"],
        "Financial assets": ["financial asset", "equity investment", "investment in"],
        "Investments (equity method)": ["associate", "joint venture", "equity method"],
        "Biological assets": ["biological"],
        "Inventories": ["inventor"],
        "Trade and other receivables": ["receivable"],
        "Cash and cash equivalents": ["cash"],
        "Trade and other payables": ["payable"],
        "Provisions": ["provision"],
        "Financial liabilities": ["borrowing", "loan", "bond", "debenture"],
        "Tax assets/liabilities": ["tax asset", "tax liabilit", "deferred tax", "tax payable", "tax receivable"],
        "Issued capital and reserves": ["share capital", "capital", "reserve", "retained"],
    }

    accounts_lower = set(df["Account"].str.lower())
    for label, keywords in min_items.items():
        found = any(
            any(kw in acct for kw in keywords)
            for acct in accounts_lower
        )
        icon = "+" if found else "-"
        st.checkbox(label, value=found, disabled=True, key=f"bs_min_{label}")
