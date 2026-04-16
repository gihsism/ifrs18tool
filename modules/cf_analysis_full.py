"""Step 5: Cash Flow Statement — Impact analysis + IFRS 18 statement.

Tabs: IFRS 18 Changes | Reclassification Analysis | IFRS 18 Cash Flow Statement
"""

import streamlit as st
import pandas as pd
import io
from modules.ifrs18_categories import IFRS18Category

_NON_AMOUNT = {"Account", "Category", "Statement"}


def _cols(df):
    return [c for c in df.columns if c not in _NON_AMOUNT]


def render_cf_analysis_full():
    st.header("Step 5: Cash Flow Statement")

    entity_type = st.session_state.get("entity_type", "General (non-financial)")
    has_cf = "classified_cf" in st.session_state
    has_pnl = "classified_pnl" in st.session_state

    tab_changes, tab_reclass, tab_stmt = st.tabs([
        "IFRS 18 Changes",
        "Reclassification Analysis",
        "IFRS 18 Cash Flow Statement",
    ])

    with tab_changes:
        _render_changes(entity_type)

    with tab_reclass:
        if has_cf:
            _render_reclassification(
                st.session_state["classified_cf"], entity_type, has_pnl
            )
        else:
            st.info("Upload a Cash Flow Statement in Step 1 to see reclassification analysis.")

    with tab_stmt:
        _render_cf_statement(has_cf, has_pnl, entity_type)


# ===================================================================
# Tab 1: IFRS 18 Changes Overview
# ===================================================================

def _render_changes(entity_type):
    st.subheader("IFRS 18 Changes to the Cash Flow Statement")

    changes = [
        {
            "Area": "Starting point (indirect method)",
            "IAS 7 / IAS 1": "Profit before tax",
            "IFRS 18": "Operating profit",
            "Impact": "Additional adjustments needed for investing/financing P&L items",
        },
        {
            "Area": "Interest paid",
            "IAS 7 / IAS 1": "Choice: Operating or Financing",
            "IFRS 18": "Financing (mandatory)",
            "Impact": "May increase operating cash flows",
        },
        {
            "Area": "Dividends paid",
            "IAS 7 / IAS 1": "Choice: Operating or Financing",
            "IFRS 18": "Financing (mandatory)",
            "Impact": "May increase operating cash flows",
        },
        {
            "Area": "Interest received",
            "IAS 7 / IAS 1": "Choice: Operating or Investing",
            "IFRS 18": "Investing (mandatory)",
            "Impact": "May decrease operating cash flows",
        },
        {
            "Area": "Dividends received",
            "IAS 7 / IAS 1": "Choice: Operating or Investing",
            "IFRS 18": "Investing (mandatory)",
            "Impact": "May decrease operating cash flows",
        },
    ]

    if entity_type != "General (non-financial)":
        changes.append({
            "Area": f"Override ({entity_type})",
            "IAS 7 / IAS 1": "Same choice rules",
            "IFRS 18": "Follow P&L classification",
            "Impact": "Interest/dividends that are Operating in P&L remain Operating in CF",
        })

    st.dataframe(pd.DataFrame(changes), use_container_width=True, hide_index=True)

    st.markdown("""
#### Starting Point — Detailed Explanation

Under IAS 7, the indirect method reconciles **Profit Before Tax** to operating cash flows.
Under IFRS 18, it must start from **Operating Profit**, which means:

- Investing income/expenses (dividends received, interest income, share of associates)
  are **no longer** part of the starting figure
- Financing costs (interest expense, lease interest) are **no longer** part of the starting figure
- The operating section needs fewer adjustments for non-operating items
- Non-operating P&L items must appear as **separate cash flow items** in their
  respective sections (Investing/Financing)

#### Lease Payments

Under IFRS 18:
- **Lease interest** (unwinding of discount on lease liabilities) → **Financing** (as interest paid)
- **Lease principal repayment** → **Financing** (as repayment of lease liabilities)
- This is consistent with IAS 7 but now mandatory (was previously a choice for the interest portion)
    """)


# ===================================================================
# Tab 2: Reclassification Analysis
# ===================================================================

def _render_reclassification(cf, entity_type, has_pnl):
    cols = _cols(cf)
    if not cols:
        st.warning("No amount columns.")
        return
    col = cols[0]

    st.subheader("Reclassification Analysis")

    is_financial = entity_type != "General (non-financial)"

    if is_financial:
        st.info(
            f"**{entity_type}**: Interest and dividend items related to your main business "
            f"should be classified as **Operating** in the cash flow statement, consistent "
            f"with their P&L classification under IFRS 18."
        )

    # Rules: for general entities, mandatory reclassification.
    # For financial entities, interest/dividends stay as Operating (main business override).
    rules = [
        (["interest paid", "lease interest paid"],
         "CF - Financing" if not is_financial else "CF - Operating",
         "Interest paid"),
        (["dividend paid", "dividends paid"],
         "CF - Financing" if not is_financial else "CF - Operating",
         "Dividends paid"),
        (["interest received"],
         "CF - Investing" if not is_financial else "CF - Operating",
         "Interest received"),
        (["dividend received", "dividends received"],
         "CF - Investing" if not is_financial else "CF - Operating",
         "Dividends received"),
    ]

    findings = []
    for keywords, required_cat, label in rules:
        for _, row in cf.iterrows():
            acct = row["Account"].lower()
            if any(kw in acct for kw in keywords):
                current = row["Category"]
                needs_change = current != required_cat
                findings.append({
                    "Item": row["Account"],
                    "Amount": row[col],
                    "Current Classification": current,
                    "IFRS 18 Required": required_cat,
                    "Action": "Reclassify" if needs_change else "No change",
                })

    if findings:
        st.dataframe(pd.DataFrame(findings), use_container_width=True, hide_index=True)
        n_reclass = sum(1 for f in findings if f["Action"] == "Reclassify")
        if n_reclass > 0:
            st.warning(f"**{n_reclass} item(s)** need reclassification under IFRS 18.")
        else:
            st.success("All interest/dividend items are correctly classified for IFRS 18.")
    else:
        st.info("No interest/dividend payment/receipt items found in the cash flow data.")

    # Starting point analysis
    st.markdown("---")
    st.markdown("#### Starting Point Analysis")

    first_items = cf.head(5)["Account"].str.lower().tolist()
    from_pbt = any("profit before tax" in x or "profit before income" in x for x in first_items)
    from_op = any("operating profit" in x or "operating loss" in x for x in first_items)

    if from_pbt:
        st.warning("Your CF starts from **Profit Before Tax** → must change to **Operating Profit**.")
        if has_pnl:
            pnl = st.session_state["classified_pnl"]
            pnl_cols = _cols(pnl)
            if pnl_cols:
                pc = pnl_cols[0]
                op = pnl[pnl["Category"] == "Operating"][pc].sum()
                inv = pnl[pnl["Category"] == "Investing"][pc].sum()
                fin = pnl[pnl["Category"] == "Financing"][pc].sum()
                st.markdown(f"""
| | Amount |
|---|---:|
| **Operating Profit** (new start) | **{op:,.0f}** |
| Investing items (excluded) | {inv:,.0f} |
| Financing items (excluded) | {fin:,.0f} |
| Profit Before Tax (old start) | {op + inv + fin:,.0f} |
                """)
    elif from_op:
        st.success("CF already starts from **Operating Profit**.")
    else:
        st.info("Could not determine starting point. IFRS 18 requires **Operating Profit**.")

    # Summary impact
    st.markdown("---")
    st.markdown("#### Impact Summary — Current vs IFRS 18")

    summary = cf.groupby("Category")[col].sum()
    cur_op = summary.get("CF - Operating", 0)
    cur_inv = summary.get("CF - Investing", 0)
    cur_fin = summary.get("CF - Financing", 0)

    if is_financial:
        # Financial entities: no reclassification needed for interest/dividends
        st.info(
            f"As a {entity_type}, interest and dividend items remain in Operating. "
            f"No reclassification impact on cash flow totals."
        )
        new_op, new_inv, new_fin = cur_op, cur_inv, cur_fin
    else:
        # General entities: calculate reclassification impact
        reclass_to_fin = 0  # items moving from Operating to Financing
        reclass_to_inv = 0  # items moving from Operating to Investing
        movements = []
        for _, row in cf.iterrows():
            acct = row["Account"].lower()
            if row["Category"] == "CF - Operating":
                if any(kw in acct for kw in ["interest paid", "lease interest paid",
                                              "dividends paid", "dividend paid"]):
                    reclass_to_fin += row[col]
                    movements.append(f"- {row['Account']} ({row[col]:,.0f}): Operating → Financing")
                elif any(kw in acct for kw in ["interest received",
                                                "dividends received", "dividend received"]):
                    reclass_to_inv += row[col]
                    movements.append(f"- {row['Account']} ({row[col]:,.0f}): Operating → Investing")

        new_op = cur_op - reclass_to_fin - reclass_to_inv
        new_inv = cur_inv + reclass_to_inv
        new_fin = cur_fin + reclass_to_fin

        if movements:
            st.markdown("**Reclassification movements:**")
            for m in movements:
                st.markdown(m)

    st.dataframe(pd.DataFrame({
        "Activity": ["Operating", "Investing", "Financing", "Net Change in Cash"],
        "Current (IAS 7)": [cur_op, cur_inv, cur_fin, cur_op + cur_inv + cur_fin],
        "IFRS 18": [new_op, new_inv, new_fin, new_op + new_inv + new_fin],
        "Difference": [new_op - cur_op, new_inv - cur_inv, new_fin - cur_fin, 0],
    }), use_container_width=True, hide_index=True)

    # Validation: net change must be the same
    net_current = cur_op + cur_inv + cur_fin
    net_ifrs18 = new_op + new_inv + new_fin
    if abs(net_current - net_ifrs18) > 0.01:
        st.error("Net change in cash differs between presentations. Check reclassification logic.")
    else:
        st.success("Net change in cash is the same under both presentations (reclassification only).")


# ===================================================================
# Tab 3: IFRS 18 Cash Flow Statement
# ===================================================================

def _render_cf_statement(has_cf, has_pnl, entity_type):
    st.subheader("IFRS 18 Cash Flow Statement")

    if not has_cf:
        st.info("Upload CF data in Step 1 or enter amounts below.")

    # Get operating profit from P&L
    op_profit = 0
    if has_pnl:
        pnl = st.session_state["classified_pnl"]
        pnl_cols = _cols(pnl)
        if pnl_cols:
            op_profit = pnl[pnl["Category"] == "Operating"][pnl_cols[0]].sum()

    st.markdown("#### Starting Point")
    op_profit = st.number_input("Operating Profit", value=float(op_profit), format="%.0f")

    # CF items editor
    st.markdown("#### Cash Flow Items")
    if "cf_items" not in st.session_state:
        defaults = [
            ("Depreciation and amortisation", 0, "Operating"),
            ("Impairment losses", 0, "Operating"),
            ("Share-based payment expense", 0, "Operating"),
            ("Changes in trade receivables", 0, "Operating"),
            ("Changes in inventories", 0, "Operating"),
            ("Changes in trade payables", 0, "Operating"),
            ("Income tax paid", 0, "Operating"),
            ("Interest received", 0, "Investing"),
            ("Dividends received", 0, "Investing"),
            ("Purchase of PPE", 0, "Investing"),
            ("Proceeds from disposal of assets", 0, "Investing"),
            ("Purchase of investments", 0, "Investing"),
            ("Interest paid", 0, "Financing"),
            ("Dividends paid", 0, "Financing"),
            ("Proceeds from borrowings", 0, "Financing"),
            ("Repayment of borrowings", 0, "Financing"),
            ("Payment of lease liabilities", 0, "Financing"),
        ]

        # Pre-fill from CF data if available
        if has_cf:
            cf = st.session_state["classified_cf"]
            cf_cols = _cols(cf)
            if cf_cols:
                defaults = []
                for _, row in cf.iterrows():
                    cat_map = {
                        "CF - Operating": "Operating",
                        "CF - Investing": "Investing",
                        "CF - Financing": "Financing",
                    }
                    defaults.append((
                        row["Account"],
                        row[cf_cols[0]],
                        cat_map.get(row["Category"], "Operating"),
                    ))

        st.session_state["cf_items"] = pd.DataFrame(
            defaults, columns=["Description", "Amount", "Activity"]
        )

    edited = st.data_editor(
        st.session_state["cf_items"],
        column_config={
            "Activity": st.column_config.SelectboxColumn(
                options=["Operating", "Investing", "Financing"], required=True,
            ),
        },
        num_rows="dynamic", use_container_width=True, hide_index=True, key="cf_stmt_editor",
    )

    if st.button("Generate Statement", type="primary"):
        st.session_state["cf_items"] = edited
        rows = []

        for activity in ["Operating", "Investing", "Financing"]:
            rows.append({"Line": f"CASH FLOWS FROM {activity.upper()} ACTIVITIES", "Amount": ""})
            if activity == "Operating":
                rows.append({"Line": "Operating profit", "Amount": f"{op_profit:,.0f}"})
                rows.append({"Line": "Adjustments for:", "Amount": ""})

            items = edited[edited["Activity"] == activity]
            total = op_profit if activity == "Operating" else 0
            for _, item in items.iterrows():
                amt = item["Amount"] or 0
                rows.append({"Line": f"  {item['Description']}", "Amount": f"{amt:,.0f}"})
                total += amt

            rows.append({"Line": f"Net cash from {activity.lower()} activities", "Amount": f"{total:,.0f}"})
            rows.append({"Line": "", "Amount": ""})

        # Net
        op_total = op_profit + edited[edited["Activity"] == "Operating"]["Amount"].sum()
        inv_total = edited[edited["Activity"] == "Investing"]["Amount"].sum()
        fin_total = edited[edited["Activity"] == "Financing"]["Amount"].sum()
        net = op_total + inv_total + fin_total
        rows.append({"Line": "NET CHANGE IN CASH", "Amount": f"{net:,.0f}"})

        cf_stmt = pd.DataFrame(rows)
        st.dataframe(cf_stmt, use_container_width=True, hide_index=True, height=600)

        # Export
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
            cf_stmt.to_excel(w, sheet_name="IFRS 18 Cash Flow", index=False)
            ws = w.sheets["IFRS 18 Cash Flow"]
            ws.set_column(0, 0, 50)
            ws.set_column(1, 1, 18)
        st.download_button("Download Excel", buf.getvalue(),
                           "ifrs18_cash_flow.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
