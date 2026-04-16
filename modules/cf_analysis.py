"""Cash Flow Statement — IFRS 18 Impact Analysis.

IFRS 18 makes the following specific changes to cash flow presentation:

1. STARTING POINT: Indirect method must start from Operating Profit
   (not Profit Before Tax as under IAS 1 / IAS 7)

2. INTEREST PAID: Must be classified as Financing (was a choice under IAS 7)

3. DIVIDENDS PAID: Must be classified as Financing (was a choice under IAS 7)

4. INTEREST RECEIVED: Must be classified as Investing (was a choice under IAS 7)

5. DIVIDENDS RECEIVED: Must be classified as Investing (was a choice under IAS 7)

6. MAIN BUSINESS ACTIVITY: For banks/insurers/investment entities, interest/dividends
   follow P&L classification (i.e. if classified as Operating in P&L, then Operating in CF)

7. OPERATING PROFIT RECONCILIATION: The indirect method reconciles from Operating Profit
   to cash from operations, requiring additional adjustments for investing/financing
   items that were previously part of PBT.
"""

import streamlit as st
import pandas as pd


def _amount_cols(df):
    return [c for c in df.columns if c not in ("Account", "Category", "Statement")]


def render_cf_analysis():
    st.header("Cash Flow Statement — IFRS 18 Impact Analysis")

    entity_type = st.session_state.get("entity_type", "General (non-financial)")
    has_cf = "classified_cf" in st.session_state
    has_pnl = "classified_pnl" in st.session_state

    # --- Changes summary (always shown) ---
    st.subheader("Key IFRS 18 Changes to the Cash Flow Statement")

    changes = [
        {
            "Change": "Starting point for indirect method",
            "IAS 7 / IAS 1": "Profit before tax",
            "IFRS 18": "**Operating profit**",
            "Impact": "Requires additional adjustments for investing/financing P&L items",
        },
        {
            "Change": "Interest paid classification",
            "IAS 7 / IAS 1": "Choice: Operating or Financing",
            "IFRS 18": "**Financing** (mandatory)",
            "Impact": "May increase cash from operations if previously in Operating",
        },
        {
            "Change": "Dividends paid classification",
            "IAS 7 / IAS 1": "Choice: Operating or Financing",
            "IFRS 18": "**Financing** (mandatory)",
            "Impact": "May increase cash from operations if previously in Operating",
        },
        {
            "Change": "Interest received classification",
            "IAS 7 / IAS 1": "Choice: Operating or Investing",
            "IFRS 18": "**Investing** (mandatory)",
            "Impact": "May decrease cash from operations if previously in Operating",
        },
        {
            "Change": "Dividends received classification",
            "IAS 7 / IAS 1": "Choice: Operating or Investing",
            "IFRS 18": "**Investing** (mandatory)",
            "Impact": "May decrease cash from operations if previously in Operating",
        },
    ]

    if entity_type != "General (non-financial)":
        changes.append({
            "Change": f"Main business override ({entity_type})",
            "IAS 7 / IAS 1": "Same choice rules",
            "IFRS 18": "**Follow P&L classification**",
            "Impact": "Interest/dividends that are Operating in P&L stay Operating in CF",
        })

    st.dataframe(pd.DataFrame(changes), use_container_width=True, hide_index=True)

    # --- Analyze existing CF data if available ---
    if has_cf:
        st.markdown("---")
        st.subheader("Analysis of Your Cash Flow Statement")

        cf = st.session_state["classified_cf"]
        cols = _amount_cols(cf)
        if not cols:
            st.warning("No amount columns in CF data.")
            return
        col = cols[0]

        _analyze_reclassifications(cf, col, entity_type)
        _analyze_starting_point(cf, col, has_pnl)
        _build_ifrs18_cf(cf, col, has_pnl, entity_type)
    else:
        st.info(
            "Upload a Cash Flow Statement in Step 1 to see a detailed impact analysis "
            "with specific reclassification recommendations."
        )

    # --- Additional guidance ---
    st.markdown("---")
    st.subheader("Transition Considerations for Cash Flow")
    st.markdown("""
**On first-time application of IFRS 18:**
- The comparative cash flow statement must be restated
- The indirect method reconciliation must start from Operating Profit for both periods
- Interest/dividend classification changes must be applied retrospectively
- No quantitative IAS 8 disclosure is required for the transition adjustments

**Practical steps:**
1. Identify interest paid/received and dividends paid/received in your current CF
2. Reclassify to the mandatory categories (see table above)
3. Change the starting point from PBT to Operating Profit
4. Add adjustments for investing/financing income/expenses that were part of PBT
5. Restate the comparative period
    """)


def _analyze_reclassifications(cf: pd.DataFrame, col: str, entity_type: str):
    """Identify items that need to be reclassified under IFRS 18."""
    st.markdown("#### Reclassification Requirements")

    # Items to check
    reclassification_rules = [
        {
            "keywords": ["interest paid"],
            "current_likely": "CF - Operating",
            "ifrs18_required": "CF - Financing",
            "description": "Interest paid",
        },
        {
            "keywords": ["dividend paid", "dividends paid"],
            "current_likely": "CF - Operating",
            "ifrs18_required": "CF - Financing",
            "description": "Dividends paid",
        },
        {
            "keywords": ["interest received"],
            "current_likely": "CF - Operating",
            "ifrs18_required": "CF - Investing",
            "description": "Interest received",
        },
        {
            "keywords": ["dividend received", "dividends received"],
            "current_likely": "CF - Operating",
            "ifrs18_required": "CF - Investing",
            "description": "Dividends received",
        },
    ]

    # For financial entities, override applies
    if entity_type != "General (non-financial)":
        st.info(
            f"As a **{entity_type}**, interest and dividend items related to your "
            f"main business activity should follow their P&L classification "
            f"(likely Operating) rather than the default rules."
        )

    findings = []
    for rule in reclassification_rules:
        for _, row in cf.iterrows():
            acct_lower = row["Account"].lower()
            if any(kw in acct_lower for kw in rule["keywords"]):
                current_cat = row["Category"]
                required = rule["ifrs18_required"]
                if entity_type != "General (non-financial)":
                    required = "CF - Operating (main business)"

                needs_change = current_cat != required
                findings.append({
                    "Item": row["Account"],
                    "Amount": row[col],
                    "Current Classification": current_cat,
                    "IFRS 18 Required": required,
                    "Action Needed": "Reclassify" if needs_change else "No change",
                })

    if findings:
        findings_df = pd.DataFrame(findings)
        st.dataframe(findings_df, use_container_width=True, hide_index=True)

        n_reclass = sum(1 for f in findings if f["Action Needed"] == "Reclassify")
        if n_reclass > 0:
            st.warning(f"**{n_reclass} item(s) need reclassification** under IFRS 18.")
        else:
            st.success("All interest/dividend items are already correctly classified.")
    else:
        st.info("No interest/dividend payment/receipt items found in the cash flow data.")


def _analyze_starting_point(cf: pd.DataFrame, col: str, has_pnl: bool):
    """Analyze the starting point change from PBT to Operating Profit."""
    st.markdown("---")
    st.markdown("#### Starting Point Change")

    # Check if current CF starts from PBT
    first_items = cf.head(5)["Account"].str.lower().tolist()
    starts_from_pbt = any(
        "profit before tax" in item or "profit before income" in item
        for item in first_items
    )
    starts_from_op = any(
        "operating profit" in item or "operating loss" in item
        for item in first_items
    )

    if starts_from_pbt:
        st.warning(
            "Your CF currently starts from **Profit Before Tax**. "
            "Under IFRS 18, it must start from **Operating Profit**."
        )

        if has_pnl:
            pnl = st.session_state["classified_pnl"]
            pnl_cols = _amount_cols(pnl)
            if pnl_cols:
                pnl_col = pnl_cols[0]
                from modules.ifrs18_categories import IFRS18Category
                op = pnl[pnl["Category"] == IFRS18Category.OPERATING.value][pnl_col].sum()
                inv = pnl[pnl["Category"] == IFRS18Category.INVESTING.value][pnl_col].sum()
                fin = pnl[pnl["Category"] == IFRS18Category.FINANCING.value][pnl_col].sum()
                tax = pnl[pnl["Category"] == IFRS18Category.INCOME_TAX.value][pnl_col].sum()
                pbt = op + inv + fin

                st.markdown(f"""
**Required adjustments to switch starting point:**

| | Amount |
|---|---:|
| Operating Profit (new starting point) | {op:,.0f} |
| Less: Investing income/expense (now excluded from starting point) | {inv:,.0f} |
| Less: Financing income/expense (now excluded from starting point) | {fin:,.0f} |
| = Profit Before Tax (old starting point) | {pbt:,.0f} |

The investing ({inv:,.0f}) and financing ({fin:,.0f}) items that were part of PBT
must now be shown as separate adjustments in the Operating section, or moved to
their respective CF sections.
                """)
    elif starts_from_op:
        st.success("Your CF already starts from **Operating Profit** — no change needed.")
    else:
        st.info(
            "Could not determine the starting point of your CF. "
            "Under IFRS 18, the indirect method must start from **Operating Profit**."
        )


def _build_ifrs18_cf(cf: pd.DataFrame, col: str, has_pnl: bool, entity_type: str):
    """Show a side-by-side of current vs IFRS 18 CF classification."""
    st.markdown("---")
    st.markdown("#### Current vs IFRS 18 Cash Flow Structure")

    # Summarize by activity
    current_summary = cf.groupby("Category")[col].sum()

    current_op = current_summary.get("CF - Operating", 0)
    current_inv = current_summary.get("CF - Investing", 0)
    current_fin = current_summary.get("CF - Financing", 0)

    # Calculate reclassification impacts
    interest_paid = 0
    dividends_paid = 0
    interest_received = 0
    dividends_received = 0

    for _, row in cf.iterrows():
        acct_lower = row["Account"].lower()
        if row["Category"] == "CF - Operating":
            if "interest paid" in acct_lower:
                interest_paid = row[col]
            elif "dividend" in acct_lower and "paid" in acct_lower:
                dividends_paid = row[col]
            elif "interest received" in acct_lower:
                interest_received = row[col]
            elif "dividend" in acct_lower and "received" in acct_lower:
                dividends_received = row[col]

    # IFRS 18 adjusted
    reclass_to_fin = interest_paid + dividends_paid  # these are negative numbers
    reclass_to_inv = interest_received + dividends_received  # these are positive numbers

    ifrs18_op = current_op - reclass_to_fin - reclass_to_inv
    ifrs18_inv = current_inv + reclass_to_inv
    ifrs18_fin = current_fin + reclass_to_fin

    comparison = pd.DataFrame({
        "Activity": ["Operating", "Investing", "Financing", "Net Change in Cash"],
        "Current (IAS 7)": [current_op, current_inv, current_fin, current_op + current_inv + current_fin],
        "IFRS 18": [ifrs18_op, ifrs18_inv, ifrs18_fin, ifrs18_op + ifrs18_inv + ifrs18_fin],
        "Difference": [
            ifrs18_op - current_op,
            ifrs18_inv - current_inv,
            ifrs18_fin - current_fin,
            0,
        ],
    })

    st.dataframe(comparison, use_container_width=True, hide_index=True)

    if reclass_to_fin != 0 or reclass_to_inv != 0:
        st.markdown("**Reclassification movements:**")
        if interest_paid != 0:
            st.markdown(f"- Interest paid ({interest_paid:,.0f}): Operating → Financing")
        if dividends_paid != 0:
            st.markdown(f"- Dividends paid ({dividends_paid:,.0f}): Operating → Financing")
        if interest_received != 0:
            st.markdown(f"- Interest received ({interest_received:,.0f}): Operating → Investing")
        if dividends_received != 0:
            st.markdown(f"- Dividends received ({dividends_received:,.0f}): Operating → Investing")
    else:
        st.info(
            "No reclassification impact detected. Interest/dividend items may already be "
            "correctly classified or not present in the Operating section."
        )
