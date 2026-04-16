"""Step 6: Management-Defined Performance Measures (MPMs) — IFRS 18 disclosure."""

import streamlit as st
import pandas as pd
import io
from modules.ifrs18_categories import IFRS18Category


# Common MPM templates
MPM_TEMPLATES = {
    "Adjusted EBITDA": {
        "description": "Earnings before interest, taxes, depreciation, and amortisation, "
        "adjusted for non-recurring items",
        "rationale": "Management believes this measure provides useful information about "
        "the entity's underlying operating performance by excluding items that "
        "are not indicative of recurring operations.",
        "reconcile_from": "Operating Profit / (Loss)",
        "typical_adjustments": [
            "Add back: Depreciation and amortisation",
            "Add back: Restructuring costs",
            "Add back: Impairment losses",
            "Add back: Share-based payment expense",
        ],
    },
    "Adjusted Operating Profit": {
        "description": "Operating profit adjusted for significant items that management "
        "considers non-recurring or not representative of underlying performance",
        "rationale": "This measure helps users understand the entity's recurring operating "
        "performance by removing the effects of items that vary significantly "
        "between periods.",
        "reconcile_from": "Operating Profit / (Loss)",
        "typical_adjustments": [
            "Add back: Restructuring costs",
            "Add back: Impairment losses",
            "Exclude: Gain/loss on disposal of operations",
        ],
    },
    "Core Earnings": {
        "description": "Profit for the period excluding items that management considers "
        "to be outside the entity's core operations",
        "rationale": "Core earnings provides a view of the entity's performance from its "
        "principal activities by excluding volatile or non-recurring items.",
        "reconcile_from": "Profit / (Loss)",
        "typical_adjustments": [
            "Exclude: Fair value gains/losses on investments",
            "Exclude: Restructuring costs",
            "Exclude: Impairment losses",
            "Exclude: Foreign exchange gains/losses",
        ],
    },
    "Custom MPM": {
        "description": "",
        "rationale": "",
        "reconcile_from": "Operating Profit / (Loss)",
        "typical_adjustments": [],
    },
}


def render_mpm():
    st.header("Step 6: Management-Defined Performance Measures")

    st.markdown("""
**IFRS 18 requires disclosure of MPMs** — subtotals of income and expenses that:
1. Are **not required** by IFRS Standards
2. Are used in **public communications** outside financial statements
3. Communicate **management's view** of financial performance

For each MPM, you must disclose: description, rationale, reconciliation to the nearest
IFRS subtotal, income tax effect, and NCI effect of each reconciling item.
    """)

    # Check if we have classified data for auto-populating
    has_data = "classified_pnl" in st.session_state
    if has_data:
        df = st.session_state["classified_pnl"]
        amount_cols = [c for c in df.columns if c not in ("Account", "Category")]
        operating_profit = df[df["Category"] == IFRS18Category.OPERATING.value][amount_cols[0]].sum() if amount_cols else 0
        total_pl = df[amount_cols[0]].sum() if amount_cols else 0
    else:
        amount_cols = []
        operating_profit = 0
        total_pl = 0

    # MPM selection
    st.subheader("Define Your MPMs")

    if "mpms" not in st.session_state:
        st.session_state["mpms"] = []

    template = st.selectbox("Add from template", list(MPM_TEMPLATES.keys()))
    if st.button("Add MPM"):
        t = MPM_TEMPLATES[template]
        st.session_state["mpms"].append({
            "name": template if template != "Custom MPM" else "New Custom MPM",
            "description": t["description"],
            "rationale": t["rationale"],
            "reconcile_from": t["reconcile_from"],
            "adjustments": [
                {"Item": adj, "Amount": 0, "Tax Effect": 0, "NCI Effect": 0}
                for adj in t["typical_adjustments"]
            ],
        })
        st.rerun()

    # Display and edit each MPM
    for i, mpm in enumerate(st.session_state["mpms"]):
        with st.expander(f"MPM: {mpm['name']}", expanded=True):
            mpm["name"] = st.text_input("MPM Name", value=mpm["name"], key=f"mpm_name_{i}")
            mpm["description"] = st.text_area(
                "Description — what aspect of performance does this communicate?",
                value=mpm["description"],
                key=f"mpm_desc_{i}",
            )
            mpm["rationale"] = st.text_area(
                "Rationale — why does management believe this is useful?",
                value=mpm["rationale"],
                key=f"mpm_rat_{i}",
            )
            mpm["reconcile_from"] = st.selectbox(
                "Reconcile from (nearest IFRS subtotal)",
                [
                    "Operating Profit / (Loss)",
                    "Profit / (Loss) Before Financing and Income Taxes",
                    "Profit / (Loss)",
                ],
                index=["Operating Profit / (Loss)",
                       "Profit / (Loss) Before Financing and Income Taxes",
                       "Profit / (Loss)"].index(mpm["reconcile_from"]),
                key=f"mpm_rec_{i}",
            )

            # Starting amount
            if mpm["reconcile_from"] == "Operating Profit / (Loss)":
                start_amount = operating_profit
            elif mpm["reconcile_from"] == "Profit / (Loss)":
                start_amount = total_pl
            else:
                start_amount = operating_profit  # Simplified

            st.markdown(f"**{mpm['reconcile_from']}**: {start_amount:,.0f}")

            # Adjustments table
            st.markdown("**Reconciling Items:**")
            adj_df = pd.DataFrame(
                mpm["adjustments"] if mpm["adjustments"]
                else [{"Item": "", "Amount": 0, "Tax Effect": 0, "NCI Effect": 0}]
            )
            edited_adj = st.data_editor(
                adj_df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key=f"mpm_adj_{i}",
            )
            mpm["adjustments"] = edited_adj.to_dict("records")

            # Calculate MPM value
            adj_total = edited_adj["Amount"].sum() if "Amount" in edited_adj.columns else 0
            tax_total = edited_adj["Tax Effect"].sum() if "Tax Effect" in edited_adj.columns else 0
            nci_total = edited_adj["NCI Effect"].sum() if "NCI Effect" in edited_adj.columns else 0
            mpm_value = start_amount + adj_total

            st.markdown(f"### {mpm['name']}: **{mpm_value:,.0f}**")

            # Reconciliation table
            recon_rows = [
                {"": mpm["reconcile_from"], "Amount": start_amount, "Tax Effect": "", "NCI Effect": ""},
            ]
            for adj in mpm["adjustments"]:
                recon_rows.append({
                    "": f"  {adj.get('Item', '')}",
                    "Amount": adj.get("Amount", 0),
                    "Tax Effect": adj.get("Tax Effect", 0),
                    "NCI Effect": adj.get("NCI Effect", 0),
                })
            recon_rows.append({
                "": f"**{mpm['name']}**",
                "Amount": mpm_value,
                "Tax Effect": tax_total,
                "NCI Effect": nci_total,
            })
            st.dataframe(pd.DataFrame(recon_rows), use_container_width=True, hide_index=True)

            # Remove button
            if st.button(f"Remove this MPM", key=f"remove_mpm_{i}"):
                st.session_state["mpms"].pop(i)
                st.rerun()

    # Export all MPM disclosures
    if st.session_state.get("mpms"):
        st.subheader("Export MPM Disclosures")
        if st.button("Generate MPM Note", type="primary"):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                for j, mpm in enumerate(st.session_state["mpms"]):
                    sheet_name = mpm["name"][:31]  # Excel sheet name limit

                    # Summary
                    summary = pd.DataFrame([
                        {"Field": "MPM Name", "Value": mpm["name"]},
                        {"Field": "Description", "Value": mpm["description"]},
                        {"Field": "Rationale", "Value": mpm["rationale"]},
                        {"Field": "Reconciled From", "Value": mpm["reconcile_from"]},
                    ])
                    summary.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)

                    # Reconciliation
                    adj_df = pd.DataFrame(mpm["adjustments"])
                    adj_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=7)

            st.download_button(
                "Download MPM Disclosures (Excel)",
                data=buffer.getvalue(),
                file_name="ifrs18_mpm_disclosures.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("No MPMs defined yet. Add one using the templates above.")
