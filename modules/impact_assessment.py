"""Step 3: Impact Assessment — IAS 1 vs IFRS 18 comparison (P&L only)."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules.ifrs18_categories import IFRS18Category

_NON_AMOUNT = {"Account", "Category"}


def _amount_cols(df):
    return [c for c in df.columns if c not in _NON_AMOUNT]


def _build_ias1_pl(df: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = [{"Line Item": r["Account"], col: r[col]} for _, r in df.iterrows()]
    rows.append({"Line Item": "Profit / (Loss)", col: df[col].sum()})
    return pd.DataFrame(rows)


def _build_ifrs18_pl(df: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    cat_order = [
        IFRS18Category.OPERATING, IFRS18Category.INVESTING,
        IFRS18Category.FINANCING, IFRS18Category.INCOME_TAX,
        IFRS18Category.DISCONTINUED,
    ]
    totals = {}
    for cat in cat_order:
        items = df[df["Category"] == cat.value]
        if items.empty and cat != IFRS18Category.OPERATING:
            totals[cat] = 0
            continue
        rows.append({"Line Item": f"**{cat.value}**", col: ""})
        t = 0
        for _, r in items.iterrows():
            rows.append({"Line Item": f"  {r['Account']}", col: r[col]})
            t += r[col]
        totals[cat] = t
        if cat == IFRS18Category.OPERATING:
            rows.append({"Line Item": "**Operating Profit / (Loss)**", col: t})
        elif cat == IFRS18Category.INVESTING:
            rows.append({
                "Line Item": "**Profit Before Financing and Income Taxes**",
                col: totals[IFRS18Category.OPERATING] + totals[IFRS18Category.INVESTING],
            })
    rows.append({"Line Item": "**Profit / (Loss)**", col: sum(totals.values())})
    return pd.DataFrame(rows)


def render_impact_assessment():
    st.header("Step 3: Impact Assessment")

    if "classified_pnl" not in st.session_state:
        st.warning("Please complete Step 2: Classification first.")
        return

    df = st.session_state["classified_pnl"]
    cols = _amount_cols(df)
    if not cols:
        st.error("No amount columns found.")
        return
    col = cols[0]

    st.markdown(
        "Compare how your **income statement** changes from **IAS 1** to **IFRS 18** presentation."
    )

    # Metrics
    operating = df[df["Category"] == IFRS18Category.OPERATING.value][col].sum()
    investing = df[df["Category"] == IFRS18Category.INVESTING.value][col].sum()
    financing = df[df["Category"] == IFRS18Category.FINANCING.value][col].sum()
    tax = df[df["Category"] == IFRS18Category.INCOME_TAX.value][col].sum()
    total_pl = df[col].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Operating Profit", f"{operating:,.0f}")
    c2.metric("Investing Result", f"{investing:,.0f}")
    c3.metric("Financing Result", f"{financing:,.0f}")
    c4.metric("Total P&L", f"{total_pl:,.0f}")

    # Reclassification
    st.subheader("Reclassification Analysis")
    non_op = df[df["Category"] != IFRS18Category.OPERATING.value]
    st.markdown(
        f"**{len(non_op)}** out of **{len(df)}** P&L items are classified outside "
        f"Operating under IFRS 18."
    )
    if len(non_op) > 0:
        st.dataframe(
            non_op[["Account", "Category", col]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

    # Subtotals
    st.subheader("New Mandatory Subtotals (IFRS 18)")
    st.dataframe(pd.DataFrame({
        "Subtotal": [
            "Operating Profit / (Loss)",
            "Profit Before Financing and Income Taxes",
            "Profit / (Loss)",
        ],
        "Amount": [operating, operating + investing, total_pl],
        "Components": ["Operating only", "Operating + Investing", "All categories"],
    }), use_container_width=True, hide_index=True)

    # Side-by-side
    st.subheader("Side-by-Side: IAS 1 vs IFRS 18")
    left, right = st.columns(2)
    with left:
        st.markdown("#### IAS 1")
        st.dataframe(_build_ias1_pl(df, col), use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### IFRS 18")
        st.dataframe(_build_ifrs18_pl(df, col), use_container_width=True, hide_index=True)

    # Waterfall
    st.subheader("P&L Waterfall — IFRS 18 Categories")
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "total"],
        x=["Operating", "Investing", "Financing", "Income Tax", "Total P&L"],
        y=[operating, investing, financing, tax, 0],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#2ecc71"}},
        decreasing={"marker": {"color": "#e74c3c"}},
        totals={"marker": {"color": "#3498db"}},
        text=[f"{v:,.0f}" for v in [operating, investing, financing, tax, total_pl]],
        textposition="outside",
    ))
    fig.update_layout(showlegend=False, height=450)
    st.plotly_chart(fig, use_container_width=True)
