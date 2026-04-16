"""Step 4: IFRS 18 Income Statement Generator."""

import streamlit as st
import pandas as pd
import io
from modules.ifrs18_categories import IFRS18Category


def _generate_ifrs18_income_statement(df: pd.DataFrame, amount_cols: list[str]) -> pd.DataFrame:
    """Generate a fully formatted IFRS 18 income statement."""
    category_order = [
        IFRS18Category.OPERATING,
        IFRS18Category.INVESTING,
        IFRS18Category.FINANCING,
        IFRS18Category.INCOME_TAX,
        IFRS18Category.DISCONTINUED,
    ]

    rows = []
    running_totals = {col: {} for col in amount_cols}

    for cat in category_order:
        cat_items = df[df["Category"] == cat.value]
        if len(cat_items) == 0 and cat not in (
            IFRS18Category.OPERATING,
            IFRS18Category.INCOME_TAX,
        ):
            for col in amount_cols:
                running_totals[col][cat.value] = 0
            continue

        # Category header
        row = {"Line Item": cat.value, "Style": "header"}
        for col in amount_cols:
            row[col] = None
        rows.append(row)

        # Line items
        cat_total = {col: 0 for col in amount_cols}
        for _, item in cat_items.iterrows():
            row = {"Line Item": f"    {item['Account']}", "Style": "item"}
            for col in amount_cols:
                val = item[col] if col in item.index else 0
                row[col] = val
                cat_total[col] += val
            rows.append(row)

        for col in amount_cols:
            running_totals[col][cat.value] = cat_total[col]

        # Category subtotal
        row = {"Line Item": f"  Total {cat.value}", "Style": "subtotal"}
        for col in amount_cols:
            row[col] = cat_total[col]
        rows.append(row)

        # Blank row
        row = {"Line Item": "", "Style": "blank"}
        for col in amount_cols:
            row[col] = None
        rows.append(row)

        # Mandatory subtotals after Operating and Investing
        if cat == IFRS18Category.OPERATING:
            row = {"Line Item": "OPERATING PROFIT / (LOSS)", "Style": "mandatory_subtotal"}
            for col in amount_cols:
                row[col] = running_totals[col].get(IFRS18Category.OPERATING.value, 0)
            rows.append(row)
            row = {"Line Item": "", "Style": "blank"}
            for col in amount_cols:
                row[col] = None
            rows.append(row)

        elif cat == IFRS18Category.INVESTING:
            row = {
                "Line Item": "PROFIT / (LOSS) BEFORE FINANCING AND INCOME TAXES",
                "Style": "mandatory_subtotal",
            }
            for col in amount_cols:
                row[col] = (
                    running_totals[col].get(IFRS18Category.OPERATING.value, 0)
                    + running_totals[col].get(IFRS18Category.INVESTING.value, 0)
                )
            rows.append(row)
            row = {"Line Item": "", "Style": "blank"}
            for col in amount_cols:
                row[col] = None
            rows.append(row)

    # Final total
    row = {"Line Item": "PROFIT / (LOSS) FOR THE PERIOD", "Style": "mandatory_subtotal"}
    for col in amount_cols:
        row[col] = sum(running_totals[col].values())
    rows.append(row)

    result = pd.DataFrame(rows)
    return result


def _style_statement(df: pd.DataFrame, amount_cols: list[str]) -> pd.DataFrame:
    """Return display-ready dataframe without the Style column."""
    display = df.copy()
    for col in amount_cols:
        display[col] = display.apply(
            lambda r: (
                f"{r[col]:,.0f}" if pd.notna(r[col]) and r[col] != "" and r["Style"] != "blank"
                else ""
            ),
            axis=1,
        )
    display = display.drop(columns=["Style"])
    return display


def render_statements():
    st.header("Step 4: IFRS 18 Income Statement")

    if "classified_pnl" not in st.session_state:
        st.warning("Please complete Step 2: Classification first.")
        return

    df = st.session_state["classified_pnl"]
    amount_cols = [c for c in df.columns if c not in ("Account", "Category")]

    if not amount_cols:
        st.error("No amount columns found.")
        return

    st.markdown(
        "This is your **IFRS 18 compliant** Statement of Profit or Loss with the "
        "three mandatory subtotals."
    )

    # Generate statement
    statement = _generate_ifrs18_income_statement(df, amount_cols)
    display_df = _style_statement(statement, amount_cols)

    # Display with formatting
    def highlight_rows(row):
        style_row = statement.iloc[row.name]
        if style_row["Style"] == "header":
            return ["font-weight: bold; background-color: #e8eaf6;"] * len(row)
        elif style_row["Style"] == "mandatory_subtotal":
            return [
                "font-weight: bold; background-color: #c8e6c9; "
                "border-top: 2px solid #333; border-bottom: 2px solid #333;"
            ] * len(row)
        elif style_row["Style"] == "subtotal":
            return ["font-weight: bold; border-top: 1px solid #999;"] * len(row)
        elif style_row["Style"] == "blank":
            return [""] * len(row)
        return [""] * len(row)

    styled = display_df.style.apply(highlight_rows, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=700)

    # Store for later use
    st.session_state["ifrs18_statement"] = statement
    st.session_state["ifrs18_display"] = display_df

    # Export options
    st.subheader("Export")
    col1, col2 = st.columns(2)

    with col1:
        # Excel export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            export_df = display_df.copy()
            export_df.to_excel(writer, sheet_name="IFRS 18 P&L", index=False)

            workbook = writer.book
            worksheet = writer.sheets["IFRS 18 P&L"]

            # Formatting
            header_fmt = workbook.add_format({"bold": True, "bg_color": "#e8eaf6"})
            subtotal_fmt = workbook.add_format({
                "bold": True,
                "bg_color": "#c8e6c9",
                "top": 2,
                "bottom": 2,
            })
            cat_subtotal_fmt = workbook.add_format({"bold": True, "top": 1})

            for i, row in statement.iterrows():
                if row["Style"] == "header":
                    for j in range(len(export_df.columns)):
                        worksheet.write(i + 1, j, export_df.iloc[i, j], header_fmt)
                elif row["Style"] == "mandatory_subtotal":
                    for j in range(len(export_df.columns)):
                        worksheet.write(i + 1, j, export_df.iloc[i, j], subtotal_fmt)
                elif row["Style"] == "subtotal":
                    for j in range(len(export_df.columns)):
                        worksheet.write(i + 1, j, export_df.iloc[i, j], cat_subtotal_fmt)

            worksheet.set_column(0, 0, 50)
            for j in range(1, len(export_df.columns)):
                worksheet.set_column(j, j, 18)

        st.download_button(
            "Download Excel",
            data=buffer.getvalue(),
            file_name="ifrs18_income_statement.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col2:
        csv = display_df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="ifrs18_income_statement.csv",
            mime="text/csv",
        )
