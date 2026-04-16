"""Step 4: Balance Sheet — Aggregation/disaggregation analysis.

IFRS 18 retains IAS 1 BS presentation but adds enhanced aggregation/disaggregation
guidance. This module analyses materiality, aggregation criteria, minimum line items,
and balance equation integrity.
"""

import streamlit as st
import pandas as pd
from modules.ifrs18_categories import BSCategory

_BS_CATS = [c.value for c in BSCategory]
_NON_AMOUNT = {"Account", "Category", "Statement"}

_ASSET_CATS = {"Non-current Assets", "Current Assets"}
_LIABILITY_CATS = {"Non-current Liabilities", "Current Liabilities"}
_EQUITY_CATS = {"Equity"}


def _cols(df):
    return [c for c in df.columns if c not in _NON_AMOUNT]


def render_bs_analysis():
    st.header("Step 4: Balance Sheet")

    if "classified_bs" not in st.session_state:
        st.info("No balance sheet data loaded. Upload a BS in Step 1 or skip this step.")
        return

    df = st.session_state["classified_bs"]
    cols = _cols(df)
    if not cols:
        st.error("No amount columns found.")
        return

    tab_agg, tab_stmt, tab_check = st.tabs([
        "Aggregation & Disaggregation",
        "IFRS 18 Balance Sheet",
        "Minimum Line Items Check",
    ])

    with tab_agg:
        _render_aggregation(df, cols)
    with tab_stmt:
        _render_statement(df, cols)
    with tab_check:
        _render_minimum_check(df)


def _render_aggregation(df, cols):
    col = cols[0]

    st.subheader("Aggregation & Disaggregation Analysis")
    st.markdown("""
IFRS 18 enhances the aggregation/disaggregation guidance for the balance sheet:

**On the face:**
- Material items presented **separately**
- Items aggregated only if they share similar **characteristics**:
  - **Nature** (physical vs financial, tangible vs intangible)
  - **Liquidity** (current vs non-current)
  - **Function** (held for use vs held for sale)
  - **Measurement basis** (cost vs fair value)

**In the notes:**
- Further disaggregation where material
- Must not obscure material information through excessive aggregation
    """)

    # Materiality — use category-based totals, not sign-based
    total_assets = df[df["Category"].isin(_ASSET_CATS)][col].abs().sum()
    total_liab_eq = df[df["Category"].isin(_LIABILITY_CATS | _EQUITY_CATS)][col].abs().sum()
    base = max(total_assets, total_liab_eq)

    if base == 0:
        st.warning("Total assets/liabilities are zero. Check your data and classifications.")
        return

    base_label = "total assets" if total_assets >= total_liab_eq else "total equity & liabilities"

    threshold_pct = st.slider("Materiality threshold (%)", 1, 20, 5, key="bs_mat")
    threshold = base * threshold_pct / 100
    st.caption(f"Base ({base_label}): {base:,.0f} | Threshold ({threshold_pct}%): {threshold:,.0f}")

    analysis = df[["Account", "Category", col]].copy()
    analysis["Absolute"] = analysis[col].abs()
    analysis["Material"] = analysis["Absolute"] >= threshold
    analysis["% of Base"] = (analysis["Absolute"] / base * 100).round(1)

    # Material items
    st.markdown("#### Material Items — Present Separately")
    material = analysis[analysis["Material"]].sort_values("Absolute", ascending=False)
    if len(material) > 0:
        st.dataframe(
            material[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

    # Aggregation candidates
    immaterial = analysis[~analysis["Material"]]
    if len(immaterial) > 0:
        st.markdown("#### Aggregation Candidates")
        st.dataframe(
            immaterial[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

        st.markdown("**Aggregation Groups** (same BS category):")
        for cat in _BS_CATS:
            cat_imm = immaterial[immaterial["Category"] == cat]
            if len(cat_imm) == 0:
                continue
            group_total = cat_imm[col].sum()
            group_abs = abs(group_total)
            group_material = group_abs >= threshold
            items = ", ".join(cat_imm["Account"].tolist())
            if len(cat_imm) > 1:
                status = "**material in aggregate**" if group_material else "immaterial in aggregate"
                st.markdown(
                    f"- **{cat}** ({len(cat_imm)} items): {items}\n"
                    f"  Combined: {group_total:,.0f} ({group_abs/base*100:.1f}%) — {status}"
                )
                if group_material:
                    st.warning(
                        f"Items in {cat} are material when combined. "
                        f"Consider whether further disaggregation is needed in the notes."
                    )
            else:
                st.markdown(f"- **{cat}**: {items} ({group_total:,.0f})")
    else:
        st.success("All BS items are individually material — no aggregation needed.")


def _render_statement(df, cols):
    st.subheader("IFRS 18 Balance Sheet")

    col = cols[0]

    # Balance equation check
    total_assets = df[df["Category"].isin(_ASSET_CATS)][col].sum()
    total_equity = df[df["Category"].isin(_EQUITY_CATS)][col].sum()
    total_liabilities = df[df["Category"].isin(_LIABILITY_CATS)][col].sum()
    imbalance = total_assets + total_equity + total_liabilities  # should be ~0 if signed correctly

    if abs(imbalance) > 1:
        st.warning(
            f"**Balance equation check:** Assets ({total_assets:,.0f}) + Equity ({total_equity:,.0f}) "
            f"+ Liabilities ({total_liabilities:,.0f}) = {imbalance:,.0f}. "
            f"Expected ~0 (assets positive, equity/liabilities negative) or check sign convention."
        )

    # Build statement
    rows = []
    section_totals = {}

    for cat in BSCategory:
        items = df[df["Category"] == cat.value]
        if items.empty:
            continue

        row = {"Line Item": f"**{cat.value}**"}
        for c in cols:
            row[c] = ""
        rows.append(row)

        cat_tot = {c: 0 for c in cols}
        for _, item in items.iterrows():
            row = {"Line Item": f"    {item['Account']}"}
            for c in cols:
                val = item.get(c, 0)
                row[c] = f"{val:,.0f}"
                cat_tot[c] += val
            rows.append(row)

        section_totals[cat.value] = cat_tot

        row = {"Line Item": f"  **Total {cat.value}**"}
        for c in cols:
            row[c] = f"**{cat_tot[c]:,.0f}**"
        rows.append(row)
        rows.append({"Line Item": "", **{c: "" for c in cols}})

    # Summary totals
    rows.append({"Line Item": "", **{c: "" for c in cols}})

    # Total Assets
    row = {"Line Item": "**TOTAL ASSETS**"}
    for c in cols:
        val = sum(
            section_totals.get(cat, {}).get(c, 0)
            for cat in ["Non-current Assets", "Current Assets"]
        )
        row[c] = f"**{val:,.0f}**"
    rows.append(row)

    rows.append({"Line Item": "", **{c: "" for c in cols}})

    # Total Equity and Liabilities
    row = {"Line Item": "**TOTAL EQUITY AND LIABILITIES**"}
    for c in cols:
        val = sum(
            section_totals.get(cat, {}).get(c, 0)
            for cat in ["Equity", "Non-current Liabilities", "Current Liabilities"]
        )
        row[c] = f"**{val:,.0f}**"
    rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=600)


def _render_minimum_check(df):
    st.subheader("IAS 1 / IFRS 18 Minimum Line Items Check")
    st.markdown(
        "IFRS 18 retains the IAS 1 requirement for minimum line items on the face. "
        "Items below with zero balances should still appear if they are required by the standard."
    )

    # Minimum line items per IAS 1.54 (retained by IFRS 18)
    min_items = [
        ("Property, plant and equipment", ["property plant", "ppe", "land and building"]),
        ("Investment property", ["investment property"]),
        ("Intangible assets", ["intangible asset", "goodwill", "software"]),
        ("Financial assets (excl. equity method, receivables, cash)",
         ["financial asset", "equity investment", "debt investment"]),
        ("Investments accounted for using the equity method",
         ["investment in associate", "investment in joint venture", "equity method"]),
        ("Biological assets", ["biological asset"]),
        ("Inventories", ["inventor"]),
        ("Trade and other receivables", ["trade receivable", "accounts receivable", "other receivable"]),
        ("Cash and cash equivalents", ["cash and cash equivalent", "cash at bank", "bank balance"]),
        ("Assets held for sale (IFRS 5)", ["held for sale"]),
        ("Trade and other payables", ["trade payable", "accounts payable", "other payable"]),
        ("Provisions", ["provision"]),
        ("Financial liabilities (excl. payables, provisions)",
         ["borrowing", "loan payable", "bank loan", "bond payable", "debenture", "lease liabilit"]),
        ("Current tax assets and liabilities",
         ["tax receivable", "tax payable", "income tax payable", "tax refund"]),
        ("Deferred tax assets and liabilities", ["deferred tax"]),
        ("Liabilities in disposal groups (IFRS 5)", ["disposal group"]),
        ("Non-controlling interests (in equity)", ["non-controlling", "minority interest"]),
        ("Issued capital and reserves attributable to owners",
         ["share capital", "retained earning", "reserve", "share premium"]),
    ]

    accts = set(df["Account"].str.lower())
    found_count = 0
    total_count = len(min_items)

    for label, keywords in min_items:
        present = any(any(kw in a for kw in keywords) for a in accts)
        if present:
            found_count += 1
        st.checkbox(label, value=present, disabled=True, key=f"bs_min_{label}")

    st.markdown("---")
    if found_count == total_count:
        st.success(f"All {total_count} minimum line items are present.")
    elif found_count >= total_count * 0.7:
        st.info(
            f"{found_count}/{total_count} minimum line items found. "
            f"Missing items may not be applicable to your entity (e.g. biological assets, "
            f"disposal groups). Review whether they should be added."
        )
    else:
        st.warning(
            f"Only {found_count}/{total_count} minimum line items found. "
            f"Review whether missing items need to be added for IFRS 18 compliance."
        )
