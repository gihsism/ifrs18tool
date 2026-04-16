"""Step 6: Transition & Export — IAS 1 to IFRS 18 reconciliation.

Focus: show how items move between IAS 1 and IFRS 18 presentation,
validate totals, and generate export package.
"""

import streamlit as st
import pandas as pd
import io
from modules.ifrs18_categories import IFRS18Category

_NON_AMOUNT = {"Account", "Category", "Statement"}


def _cols(df):
    return [c for c in df.columns if c not in _NON_AMOUNT]


def render_transition():
    st.header("Step 6: Transition & Export")

    st.markdown("""
**IFRS 18 transition requires:**
- **Retrospective application** per IAS 8
- **Comparative period** must be restated under IFRS 18 presentation
- **Reconciliation** between previously reported (IAS 1) and restated (IFRS 18) amounts
- Quantitative IAS 8 disclosures (per-line EPS impact) are **not** required
- **No recognition or measurement changes** — only presentation and classification
    """)

    has_pnl = "classified_pnl" in st.session_state
    has_cf = "classified_cf" in st.session_state

    if not has_pnl:
        st.warning("Please complete Steps 1-2 first (at minimum load P&L data).")
        return

    tab_pnl, tab_cf, tab_notes, tab_export = st.tabs([
        "P&L Reconciliation",
        "Cash Flow Reconciliation",
        "Transition Disclosures",
        "Export Package",
    ])

    with tab_pnl:
        _render_pnl_reconciliation()
    with tab_cf:
        _render_cf_reconciliation(has_cf)
    with tab_notes:
        _render_transition_notes()
    with tab_export:
        _render_export(has_pnl, has_cf)


def _render_pnl_reconciliation():
    st.subheader("Income Statement — Transition Reconciliation")

    df = st.session_state["classified_pnl"]
    cols = _cols(df)
    if not cols:
        st.error("No amount columns.")
        return

    st.markdown(
        "This reconciliation shows how each P&L line item maps from an "
        "unstructured IAS 1 presentation to the five IFRS 18 categories."
    )

    for col in cols:
        if len(cols) > 1:
            st.markdown(f"---\n#### Period: {col}")

        # IFRS 18 category totals
        cat_totals = {}
        for cat in IFRS18Category:
            cat_totals[cat.value] = df[df["Category"] == cat.value][col].sum()

        operating = cat_totals["Operating"]
        investing = cat_totals["Investing"]
        financing = cat_totals["Financing"]
        tax = cat_totals["Income Tax"]
        discontinued = cat_totals["Discontinued Operations"]
        total_pl = df[col].sum()

        # Validation
        cat_sum = sum(cat_totals.values())
        if abs(total_pl - cat_sum) > 0.01:
            st.error(
                f"Total P&L ({total_pl:,.0f}) does not equal sum of categories ({cat_sum:,.0f}). "
                f"Check classifications."
            )
        else:
            st.success(
                f"Total P&L reconciles: {total_pl:,.0f} "
                f"(presentation change only — no recognition impact)"
            )

        # Mapping table — show where each item lands under IFRS 18
        mapping_rows = []
        for _, row in df.iterrows():
            ifrs18_cat = row["Category"]
            mapping_rows.append({
                "Account": row["Account"],
                "IFRS 18 Category": ifrs18_cat,
                col: row[col],
                "New Subtotal": _subtotal_for_category(ifrs18_cat),
            })

        mapping_df = pd.DataFrame(mapping_rows)

        st.markdown("#### Line-by-Line Mapping")
        st.dataframe(mapping_df, use_container_width=True, hide_index=True)

        # Summary — IFRS 18 structure
        st.markdown("#### IFRS 18 P&L Summary")
        summary_rows = [
            {"Line": "Operating Profit / (Loss)", col: operating, "Type": "Mandatory subtotal"},
            {"Line": "Investing", col: investing, "Type": "Category total"},
            {"Line": "Profit Before Financing & Tax", col: operating + investing, "Type": "Mandatory subtotal"},
            {"Line": "Financing", col: financing, "Type": "Category total"},
            {"Line": "Income Tax", col: tax, "Type": "Category total"},
            {"Line": "Discontinued Operations", col: discontinued, "Type": "Category total"},
            {"Line": "Profit / (Loss) for the Period", col: total_pl, "Type": "Mandatory subtotal"},
        ]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        # Reclassification summary
        st.markdown("#### Reclassification Summary by Category")
        for cat in IFRS18Category:
            if cat == IFRS18Category.OPERATING:
                continue
            cat_items = df[df["Category"] == cat.value]
            if cat_items.empty:
                continue
            n = len(cat_items)
            total = cat_items[col].sum()
            items = ", ".join(cat_items["Account"].tolist())
            st.markdown(
                f"- **{cat.value}** ({n} items, {total:,.0f}): {items}"
            )


def _subtotal_for_category(cat: str) -> str:
    """Which mandatory subtotal does this category contribute to?"""
    if cat == "Operating":
        return "Operating Profit"
    elif cat == "Investing":
        return "Profit Before Financing & Tax"
    elif cat in ("Financing", "Income Tax", "Discontinued Operations"):
        return "Profit / (Loss)"
    return "Profit / (Loss)"


def _render_cf_reconciliation(has_cf):
    st.subheader("Cash Flow Statement — Transition Reconciliation")

    if not has_cf:
        st.info("Upload CF data in Step 1 to see cash flow reconciliation.")
        st.markdown("""
**Key CF changes requiring restatement of comparatives:**

1. Starting point changes from Profit Before Tax to Operating Profit
2. Interest paid reclassified to Financing (if previously in Operating)
3. Dividends paid reclassified to Financing (if previously in Operating)
4. Interest received reclassified to Investing (if previously in Operating)
5. Dividends received reclassified to Investing (if previously in Operating)

Each of these changes affects the comparative period and must be restated.
        """)
        return

    cf = st.session_state["classified_cf"]
    cols = _cols(cf)
    if not cols:
        return
    col = cols[0]

    entity_type = st.session_state.get("entity_type", "General (non-financial)")
    is_financial = entity_type != "General (non-financial)"

    st.markdown(
        "The table below shows each CF item and its classification under IFRS 18."
    )

    st.dataframe(
        cf[["Account", "Category", col]],
        use_container_width=True, hide_index=True,
    )

    # Summary by activity
    summary = cf.groupby("Category")[col].sum()
    st.markdown("#### Activity Totals")
    for activity in ["CF - Operating", "CF - Investing", "CF - Financing"]:
        val = summary.get(activity, 0)
        st.markdown(f"- **{activity.replace('CF - ', '')}**: {val:,.0f}")


def _render_transition_notes():
    st.subheader("Transition Disclosure Notes")

    st.markdown("""
**Required disclosures on first-time application (IFRS 18.C1-C6):**

1. The fact that IFRS 18 has been applied for the first time
2. The date of initial application
3. Reconciliation of amounts previously reported under IAS 1 to IFRS 18
   for each comparative period
4. Description of any accounting policy elections made at transition
    """)

    st.markdown("#### Policy Elections at Transition")
    st.markdown(
        "IFRS 18 permits certain elections at transition. Indicate which apply:"
    )

    elections = [
        (
            "Change measurement of investments in associates/JVs from equity method to FVTPL",
            "Available under IAS 28 — entity may elect at transition",
        ),
        (
            "Early adoption of IFRS 18 (before 1 January 2027)",
            "Permitted — must disclose the fact of early adoption",
        ),
    ]
    for label, help_text in elections:
        st.checkbox(label, value=False, help=help_text, key=f"election_{label[:20]}")

    st.markdown("#### Transition Note Text")
    notes = st.text_area(
        "Edit the transition disclosure note",
        value=(
            "The entity has applied IFRS 18 'Presentation and Disclosure in Financial "
            "Statements' for the first time for the reporting period beginning [date]. "
            "The comparative period has been restated to reflect the new presentation "
            "requirements.\n\n"
            "The adoption of IFRS 18 has no impact on recognised amounts or measurements. "
            "It affects only the presentation and classification of items in the statement "
            "of profit or loss and the statement of cash flows.\n\n"
            "The three new mandatory subtotals introduced are: Operating Profit, Profit "
            "Before Financing and Income Taxes, and Profit for the Period.\n\n"
            "Interest paid and dividends paid are now classified as financing activities "
            "in the cash flow statement. Interest received and dividends received are "
            "classified as investing activities. The indirect method cash flow reconciliation "
            "now starts from Operating Profit instead of Profit Before Tax."
        ),
        height=250,
        key="transition_notes",
    )

    st.session_state["_transition_notes"] = notes


def _render_export(has_pnl, has_cf):
    st.subheader("Export Transition Package")

    st.markdown(
        "Download a complete transition package with reconciliation tables, "
        "mapping, and disclosure notes."
    )

    contents = []
    if has_pnl:
        contents.append("P&L reclassification mapping")
        contents.append("IFRS 18 P&L summary")
    if has_cf:
        contents.append("CF classification")
    contents.append("Transition disclosure notes")

    st.markdown("**Package contents:**")
    for c in contents:
        st.markdown(f"- {c}")

    if st.button("Generate Transition Package", type="primary"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            if has_pnl:
                pnl = st.session_state["classified_pnl"]
                cols = _cols(pnl)

                # Mapping sheet
                mapping = pnl[["Account", "Category"] + cols].copy()
                mapping["IFRS 18 Subtotal"] = mapping["Category"].apply(_subtotal_for_category)
                mapping.to_excel(writer, sheet_name="P&L Mapping", index=False)

                # IFRS 18 summary
                if cols:
                    col = cols[0]
                    summary_rows = []
                    for cat in IFRS18Category:
                        total = pnl[pnl["Category"] == cat.value][col].sum()
                        summary_rows.append({"Category": cat.value, col: total})
                    summary_rows.append({"Category": "TOTAL", col: pnl[col].sum()})
                    pd.DataFrame(summary_rows).to_excel(
                        writer, sheet_name="IFRS 18 Summary", index=False,
                    )

            if has_cf:
                cf = st.session_state["classified_cf"]
                cf_cols = _cols(cf)
                cf[["Account", "Category"] + cf_cols].to_excel(
                    writer, sheet_name="CF Mapping", index=False,
                )

            # Notes
            notes = st.session_state.get("_transition_notes", "")
            pd.DataFrame([{"Transition Disclosure Note": notes}]).to_excel(
                writer, sheet_name="Transition Notes", index=False,
            )

            # Format
            for name in writer.sheets:
                ws = writer.sheets[name]
                ws.set_column(0, 0, 50)
                ws.set_column(1, 5, 20)

        st.download_button(
            "Download Transition Package (Excel)",
            data=buffer.getvalue(),
            file_name="ifrs18_transition_package.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.success("Transition package generated.")
