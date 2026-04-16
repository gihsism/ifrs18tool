"""Step 3: Income Statement — All P&L analysis in one place.

Tabs: Impact Assessment | Aggregation & Disaggregation | IFRS 18 Statement | MPM Disclosures
"""

import streamlit as st
import pandas as pd
import io
import plotly.express as px
import plotly.graph_objects as go
from modules.ifrs18_categories import IFRS18Category

_NON_AMOUNT = {"Account", "Category", "Statement"}
_CATS = [c.value for c in IFRS18Category]


def _cols(df):
    return [c for c in df.columns if c not in _NON_AMOUNT]


def _cat_sum(df, cat_value, col):
    return df[df["Category"] == cat_value][col].sum()


def render_pnl_analysis():
    st.header("Step 3: Income Statement (P&L)")

    if "classified_pnl" not in st.session_state:
        st.warning("Please complete Steps 1-2 first.")
        return

    df = st.session_state["classified_pnl"]
    cols = _cols(df)
    if not cols:
        st.error("No amount columns found.")
        return

    tab_impact, tab_agg, tab_stmt, tab_mpm = st.tabs([
        "Impact Assessment",
        "Aggregation & Disaggregation",
        "IFRS 18 Statement",
        "MPM Disclosures",
    ])

    with tab_impact:
        _render_impact(df, cols)
    with tab_agg:
        _render_aggregation(df, cols)
    with tab_stmt:
        _render_statement(df, cols)
    with tab_mpm:
        _render_mpm(df, cols)


# ===================================================================
# Tab 1: Impact Assessment
# ===================================================================

def _render_impact(df, cols):
    # Allow user to select period if multiple
    if len(cols) > 1:
        col = st.selectbox("Select period for analysis", cols, key="impact_period")
    else:
        col = cols[0]

    st.subheader("IAS 1 vs IFRS 18 — Key Impacts")

    operating = _cat_sum(df, "Operating", col)
    investing = _cat_sum(df, "Investing", col)
    financing = _cat_sum(df, "Financing", col)
    tax = _cat_sum(df, "Income Tax", col)
    discontinued = _cat_sum(df, "Discontinued Operations", col)
    total_pl = df[col].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Operating Profit", f"{operating:,.0f}")
    c2.metric("Investing", f"{investing:,.0f}")
    c3.metric("Financing", f"{financing:,.0f}")
    c4.metric("Income Tax", f"{tax:,.0f}")
    c5.metric("Total P&L", f"{total_pl:,.0f}")

    # Mandatory subtotals
    st.markdown("#### Three Mandatory Subtotals (IFRS 18)")
    st.markdown(
        "Under IAS 1, none of these were required. IFRS 18 mandates all three "
        "on the face of the income statement."
    )
    st.dataframe(pd.DataFrame({
        "Subtotal": [
            "Operating Profit / (Loss)",
            "Profit / (Loss) Before Financing and Income Taxes",
            "Profit / (Loss) for the Period",
        ],
        col: [operating, operating + investing, total_pl],
        "Composition": [
            "Operating category only",
            "Operating + Investing categories",
            "All five categories",
        ],
    }), use_container_width=True, hide_index=True)

    # Reclassification analysis
    st.markdown("#### Reclassification Analysis")
    st.markdown(
        "Under IAS 1, there was no mandatory categorisation of income/expenses. "
        "Under IFRS 18, every item must be classified into one of five categories. "
        "Items below move **out of** what would typically be presented as a single "
        "undifferentiated list under IAS 1."
    )

    non_op = df[df["Category"] != "Operating"]
    st.markdown(f"**{len(non_op)}** of **{len(df)}** items classified outside Operating.")

    if len(non_op) > 0:
        reclass_df = non_op[["Account", "Category", col]].copy()
        reclass_df["Impact on Operating Profit"] = -reclass_df[col]
        st.dataframe(reclass_df.reset_index(drop=True), use_container_width=True, hide_index=True)

        st.markdown(
            f"**Net impact on Operating Profit**: Items totalling "
            f"**{non_op[col].sum():,.0f}** are now shown below Operating Profit "
            f"(in Investing/Financing/Tax/Discontinued)."
        )

    # Side-by-side
    st.markdown("#### Side-by-Side Comparison")
    left, right = st.columns(2)
    with left:
        st.markdown("**IAS 1 (flat list)**")
        ias1 = [{"Line Item": r["Account"], col: r[col]} for _, r in df.iterrows()]
        ias1.append({"Line Item": "Profit / (Loss)", col: total_pl})
        st.dataframe(pd.DataFrame(ias1), use_container_width=True, hide_index=True)
    with right:
        st.markdown("**IFRS 18 (categorised)**")
        ifrs18_rows = []
        cat_totals = {}
        for cat in IFRS18Category:
            items = df[df["Category"] == cat.value]
            t = items[col].sum()
            cat_totals[cat] = t
            if items.empty and cat not in (IFRS18Category.OPERATING, IFRS18Category.INCOME_TAX):
                continue
            ifrs18_rows.append({"Line Item": f"**{cat.value}**", col: ""})
            for _, r in items.iterrows():
                ifrs18_rows.append({"Line Item": f"  {r['Account']}", col: r[col]})
            if cat == IFRS18Category.OPERATING:
                ifrs18_rows.append({"Line Item": "**Operating Profit / (Loss)**", col: t})
            elif cat == IFRS18Category.INVESTING:
                ifrs18_rows.append({
                    "Line Item": "**Profit Before Fin. & Tax**",
                    col: cat_totals[IFRS18Category.OPERATING] + t,
                })
        ifrs18_rows.append({"Line Item": "**Profit / (Loss)**", col: total_pl})
        st.dataframe(pd.DataFrame(ifrs18_rows), use_container_width=True, hide_index=True)

    # P&L total validation
    if abs(total_pl - sum(cat_totals.values())) > 0.01:
        st.error("Category totals do not reconcile to total P&L. Check classifications.")
    else:
        st.success("P&L total reconciles across both presentations (no recognition impact).")

    # Waterfall — use total_pl for the "total" bar text, 0 for waterfall measure
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "relative", "total"],
        x=["Operating", "Investing", "Financing", "Income Tax", "Discontinued", "Total P&L"],
        y=[operating, investing, financing, tax, discontinued, 0],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#2ecc71"}},
        decreasing={"marker": {"color": "#e74c3c"}},
        totals={"marker": {"color": "#3498db"}},
        text=[f"{v:,.0f}" for v in [operating, investing, financing, tax, discontinued, total_pl]],
        textposition="outside",
    ))
    fig.update_layout(showlegend=False, height=420, title="P&L Waterfall by IFRS 18 Category")
    st.plotly_chart(fig, use_container_width=True)

    # Key notes
    st.markdown("#### Key IFRS 18 Classification Notes")
    st.markdown("""
- **Impairment losses** are classified as **Operating** (regardless of the asset impaired)
- **Restructuring costs** are **Operating**
- **FX gains/losses** follow the category of the underlying item
  (e.g. FX on borrowings → Financing; FX on trade receivables → Operating)
- **Share of profit of associates/JVs** → **Investing** (unless main business)
- **Interest on lease liabilities** → **Financing**
    """)


# ===================================================================
# Tab 2: Aggregation & Disaggregation
# ===================================================================

def _render_aggregation(df, cols):
    col = cols[0]

    st.subheader("Aggregation & Disaggregation Analysis")
    st.markdown("""
IFRS 18 provides enhanced guidance on aggregation/disaggregation:

**On the face of the P&L:**
- Material items must be **presented separately**
- Immaterial items may be **aggregated** with items of **similar nature** within the same IFRS 18 category

**In the notes:**
- Further disaggregation of aggregated line items
- If expenses presented by **function** → nature disaggregation required in notes
  (at minimum: depreciation, amortisation, employee benefits, inventory write-downs)

**Aggregation criteria** (items must share):
- Nature of the income/expense
- Function within business activities
- Measurement basis
    """)

    # Materiality
    revenue = df[df[col] > 0][col].sum()
    expenses = df[df[col] < 0][col].abs().sum()

    base_choice = st.radio(
        "Materiality base",
        ["Revenue", "Total expenses", "Higher of revenue/expenses"],
        index=2, horizontal=True, key="mat_base_pnl",
    )
    if base_choice == "Revenue":
        base = revenue
    elif base_choice == "Total expenses":
        base = expenses
    else:
        base = max(revenue, expenses)

    threshold_pct = st.slider("Materiality threshold (%)", 1, 20, 5, key="pnl_mat")
    threshold = base * threshold_pct / 100
    st.caption(f"Base ({base_choice}): {base:,.0f} | Threshold ({threshold_pct}%): {threshold:,.0f}")

    analysis = df[["Account", "Category", col]].copy()
    analysis["Absolute"] = analysis[col].abs()
    analysis["Material"] = analysis["Absolute"] >= threshold
    analysis["% of Base"] = (analysis["Absolute"] / base * 100).round(1)

    # Material items
    st.markdown("#### Material Items — Present Separately on Face")
    material = analysis[analysis["Material"]].sort_values("Absolute", ascending=False)
    if len(material) > 0:
        st.dataframe(
            material[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No individually material items at this threshold.")

    # Aggregation candidates
    immaterial = analysis[~analysis["Material"]].sort_values("Absolute", ascending=False)
    if len(immaterial) > 0:
        st.markdown("#### Aggregation Candidates — Below Materiality")
        st.dataframe(
            immaterial[["Account", "Category", col, "% of Base"]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

        # Check if aggregated groups become material
        st.markdown("**Aggregation Groups** (items in same IFRS 18 category):")
        for cat in _CATS:
            cat_imm = immaterial[immaterial["Category"] == cat]
            if len(cat_imm) == 0:
                continue
            group_total = cat_imm[col].sum()
            group_abs = abs(group_total)
            group_material = group_abs >= threshold
            items = ", ".join(cat_imm["Account"].tolist())
            status = "**material in aggregate**" if group_material else "immaterial in aggregate"
            st.markdown(
                f"- **{cat}** ({len(cat_imm)} items): {items}\n"
                f"  Combined: {group_total:,.0f} ({group_abs/base*100:.1f}% of base) — {status}"
            )
            if group_material:
                st.warning(
                    f"Items in {cat} are material when aggregated ({group_abs/base*100:.1f}%). "
                    f"Consider whether further disaggregation is needed even though "
                    f"individual items are below threshold."
                )
    else:
        st.success("All items are individually material — no aggregation needed.")

    # Function vs Nature
    st.markdown("---")
    st.markdown("#### Expense Presentation: Function vs Nature")

    func_kw = ["cost of sales", "cost of goods", "selling", "distribution",
               "administrative", "admin", "general and admin", "marketing",
               "research and development"]
    nat_kw = ["depreciation", "amortisation", "amortization", "employee benefit",
              "staff cost", "wages", "salaries", "raw material", "inventory write",
              "impairment", "share-based payment"]

    accts = df["Account"].str.lower()
    func_items = [(a, kw) for a in accts for kw in func_kw if kw in a]
    nat_items = [(a, kw) for a in accts for kw in nat_kw if kw in a]

    if len(func_items) > len(nat_items):
        st.warning(
            f"Presentation appears to be **by function** ({len(func_items)} function items "
            f"vs {len(nat_items)} nature items)."
        )
        st.markdown("""
**Required nature disclosure in notes (IFRS 18.72):**

The following must be disclosed by nature when function presentation is used:
""")
        nature_required = {
            "Depreciation": "depreciation",
            "Amortisation": "amortisation",
            "Employee benefits expense": "employee",
            "Write-down of inventories": "inventory write",
            "Impairment losses": "impairment",
        }
        for label, kw in nature_required.items():
            found = any(kw in a for a in accts)
            amounts = df[df["Account"].str.lower().str.contains(kw, na=False)][col].sum()
            if found:
                st.markdown(f"- {label}: **{amounts:,.0f}** (found in data)")
            else:
                st.markdown(f"- {label}: _Not found — must be disclosed in notes_")

    elif len(nat_items) > len(func_items):
        st.success(
            f"Presentation appears to be **by nature** ({len(nat_items)} nature items). "
            f"No additional nature disclosure required in notes."
        )
    else:
        st.info(
            "Mixed or unclear presentation. If any functional line items are used "
            "(e.g. Cost of Sales, Admin Expenses), nature disaggregation is required in notes."
        )

    # Aggregated preview
    st.markdown("---")
    st.markdown("#### Preview: Aggregated P&L")
    preview = []
    for cat in _CATS:
        cat_all = analysis[analysis["Category"] == cat]
        if cat_all.empty:
            continue
        for _, r in cat_all[cat_all["Material"]].iterrows():
            preview.append({"Line Item": r["Account"], "Category": cat, col: r[col]})
        cat_imm = cat_all[~cat_all["Material"]]
        if len(cat_imm) == 1:
            # Single immaterial item — still show it rather than "Other (1 item)"
            r = cat_imm.iloc[0]
            preview.append({"Line Item": r["Account"], "Category": cat, col: r[col]})
        elif len(cat_imm) > 1:
            preview.append({
                "Line Item": f"Other {cat.lower()} items ({len(cat_imm)} items)",
                "Category": cat,
                col: cat_imm[col].sum(),
            })
    if preview:
        st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)
        st.caption(f"Reduced from {len(df)} to {len(preview)} line items")


# ===================================================================
# Tab 3: IFRS 18 Income Statement
# ===================================================================

def _render_statement(df, cols):
    st.subheader("IFRS 18 Income Statement")
    st.markdown(
        "Statement of Profit or Loss with the three mandatory subtotals "
        "and five categories required by IFRS 18."
    )

    rows = []
    totals = {}
    for cat in IFRS18Category:
        items = df[df["Category"] == cat.value]
        cat_tot = {c: 0 for c in cols}

        # Always show Operating and Income Tax; skip others only if empty
        if items.empty and cat not in (IFRS18Category.OPERATING, IFRS18Category.INCOME_TAX):
            totals[cat] = cat_tot
            continue

        # Category header
        row = {"Line Item": cat.value, "Style": "header"}
        for c in cols:
            row[c] = None
        rows.append(row)

        # Line items
        for _, item in items.iterrows():
            row = {"Line Item": f"    {item['Account']}", "Style": "item"}
            for c in cols:
                val = item.get(c, 0)
                row[c] = val
                cat_tot[c] += val
            rows.append(row)

        totals[cat] = cat_tot

        # Category subtotal
        if len(items) > 1:
            row = {"Line Item": f"  Total {cat.value}", "Style": "subtotal"}
            row.update(cat_tot)
            rows.append(row)

        rows.append({"Line Item": "", "Style": "blank", **{c: None for c in cols}})

        # Mandatory subtotals
        if cat == IFRS18Category.OPERATING:
            row = {"Line Item": "OPERATING PROFIT / (LOSS)", "Style": "mandatory"}
            row.update(totals[cat])
            rows.append(row)
            rows.append({"Line Item": "", "Style": "blank", **{c: None for c in cols}})
        elif cat == IFRS18Category.INVESTING:
            row = {"Line Item": "PROFIT / (LOSS) BEFORE FINANCING AND INCOME TAXES", "Style": "mandatory"}
            row.update({
                c: totals[IFRS18Category.OPERATING][c] + totals[IFRS18Category.INVESTING][c]
                for c in cols
            })
            rows.append(row)
            rows.append({"Line Item": "", "Style": "blank", **{c: None for c in cols}})

    # Final mandatory subtotal
    row = {"Line Item": "PROFIT / (LOSS) FOR THE PERIOD", "Style": "mandatory"}
    row.update({c: sum(t[c] for t in totals.values()) for c in cols})
    rows.append(row)

    stmt = pd.DataFrame(rows)
    display = stmt.copy()
    for c in cols:
        display[c] = display.apply(
            lambda r: f"{r[c]:,.0f}" if pd.notna(r[c]) and r["Style"] != "blank" else "",
            axis=1,
        )
    display = display.drop(columns=["Style"])
    st.dataframe(display, use_container_width=True, hide_index=True, height=700)

    # Export
    c1, c2 = st.columns(2)
    with c1:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
            display.to_excel(w, sheet_name="IFRS 18 P&L", index=False)
            ws = w.sheets["IFRS 18 P&L"]
            ws.set_column(0, 0, 55)
            for j in range(1, len(display.columns)):
                ws.set_column(j, j, 18)
        st.download_button(
            "Download Excel", buf.getvalue(),
            "ifrs18_income_statement.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c2:
        st.download_button(
            "Download CSV", display.to_csv(index=False),
            "ifrs18_income_statement.csv", "text/csv",
        )


# ===================================================================
# Tab 4: MPM Disclosures
# ===================================================================

_MPM_TEMPLATES = {
    "Adjusted EBITDA": {
        "desc": "Earnings before interest, taxes, depreciation, amortisation, "
                "adjusted for non-recurring items",
        "rationale": "Provides useful information about the entity's underlying "
                     "operating performance by excluding items not indicative of "
                     "recurring operations",
        "from": "Operating Profit / (Loss)",
        "adjustments": [
            "Add back: Depreciation and amortisation",
            "Add back: Restructuring costs",
            "Add back: Impairment losses",
            "Add back: Share-based payment expense",
        ],
    },
    "Adjusted Operating Profit": {
        "desc": "Operating profit adjusted for significant items that management "
                "considers non-recurring",
        "rationale": "Helps users understand the entity's recurring operating "
                     "performance by removing items that vary significantly between periods",
        "from": "Operating Profit / (Loss)",
        "adjustments": [
            "Add back: Restructuring costs",
            "Add back: Impairment losses",
            "Exclude: Gain/loss on disposal of operations",
        ],
    },
    "Custom MPM": {
        "desc": "", "rationale": "",
        "from": "Operating Profit / (Loss)", "adjustments": [],
    },
}


def _render_mpm(df, cols):
    st.subheader("Management-Defined Performance Measures")
    st.markdown("""
**IFRS 18 MPM requirements (disclosed in a single note):**

1. **Description** of the aspect of financial performance the MPM communicates
2. **Rationale** — why management believes it provides useful information
3. **Reconciliation** to the most directly comparable IFRS-required subtotal or total
4. **Income tax effect** of each reconciling item
5. **Non-controlling interest (NCI) effect** of each reconciling item
6. **Explanation of changes** — new, discontinued, or modified MPMs must be justified

**What is NOT an MPM:** ratios (e.g. EPS, ROE), operational metrics (same-store sales),
cash flow measures, or measures from oral/social media communications only.
    """)

    col = cols[0]
    operating = _cat_sum(df, "Operating", col)
    investing = _cat_sum(df, "Investing", col)
    total_pl = df[col].sum()

    # Starting amounts for reconciliation
    subtotals = {
        "Operating Profit / (Loss)": operating,
        "Profit / (Loss) Before Financing and Income Taxes": operating + investing,
        "Profit / (Loss)": total_pl,
    }

    if "mpms" not in st.session_state:
        st.session_state["mpms"] = []

    template = st.selectbox("Add from template", list(_MPM_TEMPLATES.keys()))
    if st.button("Add MPM"):
        t = _MPM_TEMPLATES[template]
        st.session_state["mpms"].append({
            "name": template if template != "Custom MPM" else "New Custom MPM",
            "desc": t["desc"], "rationale": t["rationale"], "from": t["from"],
            "adjustments": [
                {"Item": a, "Amount": 0, "Tax Effect": 0, "NCI Effect": 0}
                for a in t["adjustments"]
            ],
        })
        st.rerun()

    for i, mpm in enumerate(st.session_state["mpms"]):
        with st.expander(f"MPM: {mpm['name']}", expanded=True):
            mpm["name"] = st.text_input("Name", mpm["name"], key=f"mn_{i}")
            mpm["desc"] = st.text_area(
                "Description — what aspect of performance does this communicate?",
                mpm["desc"], key=f"md_{i}",
            )
            mpm["rationale"] = st.text_area(
                "Rationale — why is this useful to users of financial statements?",
                mpm["rationale"], key=f"mr_{i}",
            )
            mpm["from"] = st.selectbox(
                "Reconcile from (nearest IFRS-required subtotal)",
                list(subtotals.keys()),
                index=list(subtotals.keys()).index(mpm.get("from", "Operating Profit / (Loss)")),
                key=f"mf_{i}",
            )

            start = subtotals[mpm["from"]]
            st.markdown(f"**{mpm['from']}**: {start:,.0f}")

            # Adjustments with tax and NCI effects
            st.markdown("**Reconciling items:**")
            adj_df = pd.DataFrame(
                mpm["adjustments"]
                or [{"Item": "", "Amount": 0, "Tax Effect": 0, "NCI Effect": 0}]
            )
            edited = st.data_editor(
                adj_df, num_rows="dynamic", use_container_width=True, key=f"ma_{i}",
            )
            mpm["adjustments"] = edited.to_dict("records")

            adj_total = edited["Amount"].sum() if "Amount" in edited.columns else 0
            tax_total = edited["Tax Effect"].sum() if "Tax Effect" in edited.columns else 0
            nci_total = edited["NCI Effect"].sum() if "NCI Effect" in edited.columns else 0
            mpm_val = start + adj_total

            # Reconciliation table
            st.markdown("**Reconciliation:**")
            recon = [{"": mpm["from"], "Pre-tax": start, "Tax Effect": "", "NCI Effect": ""}]
            for adj in mpm["adjustments"]:
                recon.append({
                    "": f"  {adj.get('Item', '')}",
                    "Pre-tax": adj.get("Amount", 0),
                    "Tax Effect": adj.get("Tax Effect", 0),
                    "NCI Effect": adj.get("NCI Effect", 0),
                })
            recon.append({
                "": f"**{mpm['name']}**",
                "Pre-tax": mpm_val,
                "Tax Effect": tax_total,
                "NCI Effect": nci_total,
            })
            st.dataframe(pd.DataFrame(recon), use_container_width=True, hide_index=True)

            st.markdown(f"### {mpm['name']}: **{mpm_val:,.0f}**")
            if tax_total != 0:
                st.markdown(f"After tax: **{mpm_val + tax_total:,.0f}**")
            if nci_total != 0:
                st.markdown(f"Attributable to owners: **{mpm_val + tax_total - nci_total:,.0f}**")

            c1, c2 = st.columns([3, 1])
            with c2:
                if st.button("Remove MPM", key=f"rm_{i}"):
                    st.session_state["mpms"].pop(i)
                    st.rerun()

    if not st.session_state.get("mpms"):
        st.info("No MPMs defined. Add one above if your entity uses adjusted performance measures.")
