"""Step 5: Cash Flow Statement — IFRS 18 format (indirect method starting from operating profit)."""

import streamlit as st
import pandas as pd
import io
from modules.ifrs18_categories import IFRS18Category


# Default non-cash adjustment items
DEFAULT_ADJUSTMENTS = [
    {"Description": "Depreciation and amortisation", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Impairment losses", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Share-based payment expense", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Gain/loss on disposal of PPE", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Changes in trade receivables", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Changes in inventories", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Changes in trade payables", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Changes in provisions", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Income tax paid", "Current Year": 0, "Prior Year": 0, "CF Category": "Operating"},
    {"Description": "Interest received", "Current Year": 0, "Prior Year": 0, "CF Category": "Investing"},
    {"Description": "Dividends received", "Current Year": 0, "Prior Year": 0, "CF Category": "Investing"},
    {"Description": "Purchase of PPE", "Current Year": 0, "Prior Year": 0, "CF Category": "Investing"},
    {"Description": "Proceeds from sale of PPE", "Current Year": 0, "Prior Year": 0, "CF Category": "Investing"},
    {"Description": "Purchase of investments", "Current Year": 0, "Prior Year": 0, "CF Category": "Investing"},
    {"Description": "Proceeds from sale of investments", "Current Year": 0, "Prior Year": 0, "CF Category": "Investing"},
    {"Description": "Interest paid", "Current Year": 0, "Prior Year": 0, "CF Category": "Financing"},
    {"Description": "Dividends paid", "Current Year": 0, "Prior Year": 0, "CF Category": "Financing"},
    {"Description": "Proceeds from borrowings", "Current Year": 0, "Prior Year": 0, "CF Category": "Financing"},
    {"Description": "Repayment of borrowings", "Current Year": 0, "Prior Year": 0, "CF Category": "Financing"},
    {"Description": "Payment of lease liabilities", "Current Year": 0, "Prior Year": 0, "CF Category": "Financing"},
    {"Description": "Proceeds from share issuance", "Current Year": 0, "Prior Year": 0, "CF Category": "Financing"},
]


def render_cash_flow():
    st.header("Step 5: Cash Flow Statement (IFRS 18)")

    st.markdown("""
**Key IFRS 18 changes to the cash flow statement:**
- Indirect method must start from **Operating Profit** (not profit before tax)
- **Interest paid** → classified as **Financing** (no longer a choice)
- **Dividends paid** → classified as **Financing**
- **Interest received** → classified as **Investing**
- **Dividends received** → classified as **Investing**
    """)

    # Get operating profit from classified data if available
    operating_profit_cy = 0
    operating_profit_py = 0
    if "classified_pnl" in st.session_state:
        df = st.session_state["classified_pnl"]
        amount_cols = [c for c in df.columns if c not in ("Account", "Category")]
        op_items = df[df["Category"] == IFRS18Category.OPERATING.value]
        if len(amount_cols) >= 1:
            operating_profit_cy = op_items[amount_cols[0]].sum()
        if len(amount_cols) >= 2:
            operating_profit_py = op_items[amount_cols[1]].sum()

    st.subheader("Starting Point: Operating Profit")
    col1, col2 = st.columns(2)
    operating_profit_cy = col1.number_input(
        "Operating Profit — Current Year",
        value=float(operating_profit_cy),
        format="%.0f",
    )
    operating_profit_py = col2.number_input(
        "Operating Profit — Prior Year",
        value=float(operating_profit_py),
        format="%.0f",
    )

    # Cash flow adjustments
    st.subheader("Cash Flow Items")
    st.markdown("Enter amounts for each cash flow item. Add or remove rows as needed.")

    if "cf_data" not in st.session_state:
        st.session_state["cf_data"] = pd.DataFrame(DEFAULT_ADJUSTMENTS)

    edited_cf = st.data_editor(
        st.session_state["cf_data"],
        column_config={
            "CF Category": st.column_config.SelectboxColumn(
                "Category",
                options=["Operating", "Investing", "Financing"],
                required=True,
            ),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="cf_editor",
    )

    if st.button("Generate Cash Flow Statement", type="primary"):
        st.session_state["cf_data"] = edited_cf

        # Build the statement
        rows = []

        # Operating activities
        rows.append({"Line": "CASH FLOWS FROM OPERATING ACTIVITIES", "Current Year": "", "Prior Year": ""})
        rows.append({"Line": "Operating profit", "Current Year": f"{operating_profit_cy:,.0f}", "Prior Year": f"{operating_profit_py:,.0f}"})
        rows.append({"Line": "Adjustments for:", "Current Year": "", "Prior Year": ""})

        op_items = edited_cf[edited_cf["CF Category"] == "Operating"]
        op_total_cy = operating_profit_cy
        op_total_py = operating_profit_py
        for _, item in op_items.iterrows():
            cy = item.get("Current Year", 0) or 0
            py = item.get("Prior Year", 0) or 0
            rows.append({"Line": f"  {item['Description']}", "Current Year": f"{cy:,.0f}", "Prior Year": f"{py:,.0f}"})
            op_total_cy += cy
            op_total_py += py

        rows.append({"Line": "Net cash from operating activities", "Current Year": f"{op_total_cy:,.0f}", "Prior Year": f"{op_total_py:,.0f}"})
        rows.append({"Line": "", "Current Year": "", "Prior Year": ""})

        # Investing activities
        rows.append({"Line": "CASH FLOWS FROM INVESTING ACTIVITIES", "Current Year": "", "Prior Year": ""})
        inv_items = edited_cf[edited_cf["CF Category"] == "Investing"]
        inv_total_cy = 0
        inv_total_py = 0
        for _, item in inv_items.iterrows():
            cy = item.get("Current Year", 0) or 0
            py = item.get("Prior Year", 0) or 0
            rows.append({"Line": f"  {item['Description']}", "Current Year": f"{cy:,.0f}", "Prior Year": f"{py:,.0f}"})
            inv_total_cy += cy
            inv_total_py += py

        rows.append({"Line": "Net cash from investing activities", "Current Year": f"{inv_total_cy:,.0f}", "Prior Year": f"{inv_total_py:,.0f}"})
        rows.append({"Line": "", "Current Year": "", "Prior Year": ""})

        # Financing activities
        rows.append({"Line": "CASH FLOWS FROM FINANCING ACTIVITIES", "Current Year": "", "Prior Year": ""})
        fin_items = edited_cf[edited_cf["CF Category"] == "Financing"]
        fin_total_cy = 0
        fin_total_py = 0
        for _, item in fin_items.iterrows():
            cy = item.get("Current Year", 0) or 0
            py = item.get("Prior Year", 0) or 0
            rows.append({"Line": f"  {item['Description']}", "Current Year": f"{cy:,.0f}", "Prior Year": f"{py:,.0f}"})
            fin_total_cy += cy
            fin_total_py += py

        rows.append({"Line": "Net cash from financing activities", "Current Year": f"{fin_total_cy:,.0f}", "Prior Year": f"{fin_total_py:,.0f}"})
        rows.append({"Line": "", "Current Year": "", "Prior Year": ""})

        # Net change
        net_cy = op_total_cy + inv_total_cy + fin_total_cy
        net_py = op_total_py + inv_total_py + fin_total_py
        rows.append({"Line": "NET INCREASE/(DECREASE) IN CASH", "Current Year": f"{net_cy:,.0f}", "Prior Year": f"{net_py:,.0f}"})

        cf_statement = pd.DataFrame(rows)
        st.session_state["cf_statement"] = cf_statement

        st.dataframe(cf_statement, use_container_width=True, hide_index=True, height=600)

        # IAS 7 comparison note
        st.info(
            "**Key difference from IAS 7 under IAS 1:** The indirect method now starts from "
            "Operating Profit (IFRS 18) instead of Profit Before Tax. Interest paid and dividends "
            "paid are now mandatorily classified as Financing. Interest and dividends received "
            "are classified as Investing."
        )

        # Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            cf_statement.to_excel(writer, sheet_name="Cash Flow IFRS 18", index=False)
            worksheet = writer.sheets["Cash Flow IFRS 18"]
            worksheet.set_column(0, 0, 50)
            worksheet.set_column(1, 2, 18)

        st.download_button(
            "Download Excel",
            data=buffer.getvalue(),
            file_name="ifrs18_cash_flow.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
