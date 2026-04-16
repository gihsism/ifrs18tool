"""Step 1: Data Input — Upload financial statements with auto-detection."""

import streamlit as st
import pandas as pd
from modules.doc_parser import (
    extract_tables_from_pdf,
    extract_tables_from_docx,
    extract_tables_from_image,
    _ocr_available,
)
from modules.statement_detector import detect_table_type, auto_classify


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_PNL = pd.DataFrame({
    "Account": [
        "Revenue", "Cost of Sales", "Selling & Distribution Costs",
        "Administrative Expenses", "Other Operating Income",
        "Depreciation - PPE", "Amortisation - Intangibles",
        "Employee Benefits Expense", "Impairment of Trade Receivables",
        "Restructuring Costs",
        "Dividend Income", "Interest Income - Bank Deposits",
        "Gain on Disposal of Investment Property",
        "Fair Value Gain on Equity Investments",
        "Share of Profit of Associates",
        "Rental Income from Investment Property",
        "Interest Expense - Bank Loans",
        "Interest Expense - Lease Liabilities",
        "Unwinding of Discount on Provisions",
        "Foreign Exchange Loss on Borrowings",
        "Current Income Tax Expense", "Deferred Tax Benefit",
    ],
    "Current Year": [
        500000, -280000, -35000, -45000, 12000, -22000, -8000,
        -65000, -3500, -7000, 8500, 4200, 15000, 6800, 12500,
        9200, -18000, -5500, -1200, -3800, -22000, 4500,
    ],
    "Prior Year": [
        460000, -258000, -32000, -42000, 10000, -20000, -7500,
        -60000, -2800, 0, 7200, 3800, 0, 4500, 11000,
        8800, -16500, -5000, -1100, -2500, -19500, 3200,
    ],
})

SAMPLE_BS = pd.DataFrame({
    "Account": [
        "Property, Plant and Equipment", "Intangible Assets", "Goodwill",
        "Investment Property", "Right-of-Use Assets",
        "Investment in Associates",
        "Inventories", "Trade Receivables", "Prepayments",
        "Cash and Cash Equivalents",
        "Share Capital", "Retained Earnings", "Other Reserves",
        "Long-term Borrowings", "Lease Liabilities",
        "Deferred Tax Liability", "Provisions",
        "Trade Payables", "Accrued Expenses",
        "Current Portion of Borrowings", "Tax Payable",
    ],
    "Current Year": [
        350000, 120000, 80000, 95000, 45000, 75000,
        62000, 85000, 12000, 48000,
        -200000, -450000, -35000,
        -150000, -42000, -18000, -25000,
        -38000, -22000, -15000, -7000,
    ],
    "Prior Year": [
        320000, 110000, 80000, 88000, 48000, 68000,
        58000, 78000, 10000, 55000,
        -200000, -410000, -30000,
        -140000, -45000, -16000, -22000,
        -35000, -19000, -12000, -6000,
    ],
})

SAMPLE_CF = pd.DataFrame({
    "Account": [
        "Cash flows from operating activities",
        "Profit before tax",
        "Depreciation and amortisation",
        "Impairment losses",
        "Share-based payment expense",
        "Finance costs",
        "Finance income",
        "Share of profit of associates",
        "Changes in trade receivables",
        "Changes in inventories",
        "Changes in trade payables",
        "Income tax paid",
        "Net cash from operating activities",
        "Cash flows from investing activities",
        "Purchase of PPE",
        "Proceeds from sale of investments",
        "Interest received",
        "Dividends received",
        "Net cash from investing activities",
        "Cash flows from financing activities",
        "Proceeds from borrowings",
        "Repayment of borrowings",
        "Interest paid",
        "Dividends paid",
        "Payment of lease liabilities",
        "Net cash from financing activities",
        "Net increase in cash and cash equivalents",
        "Cash at beginning of year",
        "Cash at end of year",
    ],
    "Current Year": [
        0, 75700, 30000, 3500, 2000, 28500, -12700, -12500,
        -7000, -4000, 3000, -22000,
        84500,
        0, -52000, 18000, 4200, 8500,
        -21300,
        0, 50000, -30000, -18000, -15000, -5500,
        -18500,
        44700, 55000, 99700,
    ],
    "Prior Year": [
        0, 59600, 27500, 2800, 1500, 25100, -11800, -11000,
        -5000, -2000, 4000, -19500,
        72200,
        0, -45000, 12000, 3800, 7200,
        -22000,
        0, 40000, -25000, -16500, -12000, -5000,
        -18500,
        31700, 23300, 55000,
    ],
})


def _load_file(uploaded):
    """Load data from uploaded file.  Returns (df_or_none, tables_or_none)."""
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded), None
    elif name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded), None
    elif name.endswith(".pdf"):
        tables = extract_tables_from_pdf(uploaded)
        return None, tables if tables else None
    elif name.endswith(".docx"):
        tables = extract_tables_from_docx(uploaded)
        return None, tables if tables else None
    elif name.endswith((".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp")):
        tables = extract_tables_from_image(uploaded)
        return None, tables if tables else None
    return None, None


def _process_and_store(df: pd.DataFrame, entity_type: str):
    """Auto-detect, classify, and store data split by statement type."""
    classified = auto_classify(df, entity_type)

    # Split by statement type and store
    for stmt_type in classified["Statement"].unique():
        subset = classified[classified["Statement"] == stmt_type].copy()
        key = _stmt_key(stmt_type)
        st.session_state[key] = subset

    st.session_state["all_classified"] = classified
    st.session_state["loaded_statements"] = set(classified["Statement"].unique())

    # Auto-save to disk
    from modules.persistence import auto_save
    auto_save()


def _stmt_key(stmt_type: str) -> str:
    """Session state key for a statement type."""
    return {
        "Profit or Loss": "classified_pnl",
        "Balance Sheet": "classified_bs",
        "Cash Flow": "classified_cf",
    }.get(stmt_type, "classified_other")


def render_data_input():
    st.header("Step 1: Data Input")

    st.markdown(
        "Upload your financial statements. The tool **automatically identifies** whether "
        "data is from the Income Statement (P&L), Balance Sheet, or Cash Flow Statement. "
        "You can upload a single statement or multiple files."
    )

    entity_type = st.session_state.get("entity_type", "General (non-financial)")

    tab_upload, tab_sample = st.tabs(["Upload File(s)", "Use Sample Data"])

    with tab_upload:
        # Show OCR status
        ocr_ok = _ocr_available()
        if ocr_ok:
            st.caption("OCR enabled — scanned PDFs and images (PNG, JPG) are supported.")
        else:
            st.caption(
                "OCR not available — install `tesseract` for scanned PDF and image support. "
                "Text-based PDFs, Excel, CSV, and Word files work without OCR."
            )

        accepted_types = ["xlsx", "xls", "csv", "pdf", "docx"]
        if ocr_ok:
            accepted_types.extend(["png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"])

        files = st.file_uploader(
            "Upload financial statements",
            type=accepted_types,
            accept_multiple_files=True,
            help=(
                "Supported: Excel, CSV, PDF, Word"
                + (", PNG, JPG, TIFF (via OCR)" if ocr_ok else "")
                + ". Each file is auto-detected as P&L, BS, or CF."
            ),
        )

        if files:
            all_dfs = []
            for uploaded in files:
                with st.spinner(f"Processing {uploaded.name}..."):
                    df, tables = _load_file(uploaded)

                if tables:
                    st.success(f"Found **{len(tables)}** table(s) in {uploaded.name}")
                    for i, tbl in enumerate(tables):
                        scores = detect_table_type(tbl)
                        best = max(scores, key=scores.get)
                        confidence = scores[best]
                        with st.expander(
                            f"{uploaded.name} — Table {i+1}: "
                            f"{len(tbl)} rows, detected as **{best}** "
                            f"({confidence:.0%} confidence)",
                            expanded=(i == 0),
                        ):
                            edited = st.data_editor(
                                tbl, use_container_width=True, hide_index=True,
                                num_rows="dynamic", key=f"tbl_{uploaded.name}_{i}",
                            )
                            if st.button(
                                f"Include this table", key=f"inc_{uploaded.name}_{i}",
                            ):
                                all_dfs.append(edited)
                                st.success("Added!")

                elif df is None and tables is None:
                    file_ext = uploaded.name.rsplit(".", 1)[-1].lower()
                    if file_ext in ("png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"):
                        st.error(
                            f"Could not extract data from {uploaded.name}. "
                            "Ensure the image contains a clear financial table. "
                            + ("" if ocr_ok else "Install `tesseract` for OCR support.")
                        )
                    elif file_ext == "pdf":
                        st.error(
                            f"No tables found in {uploaded.name}. "
                            "If this is a scanned PDF, "
                            + ("OCR was attempted but found no financial data." if ocr_ok
                               else "install `tesseract` and `poppler` for OCR support.")
                        )
                    else:
                        st.error(f"Could not read {uploaded.name}.")

                elif df is not None and len(df) > 0:
                    scores = detect_table_type(df)
                    best = max(scores, key=scores.get)
                    confidence = scores[best]

                    st.success(
                        f"Loaded **{len(df)}** rows from {uploaded.name} — "
                        f"detected as **{best}** ({confidence:.0%} confidence)"
                    )

                    # Column mapping
                    cols = list(df.columns)
                    st.subheader(f"Map Columns — {uploaded.name}")
                    account_col = st.selectbox(
                        "Account / Description column", cols, index=0,
                        key=f"acc_{uploaded.name}",
                    )
                    amount_cols = st.multiselect(
                        "Amount column(s)",
                        [c for c in cols if c != account_col],
                        default=[c for c in cols if c != account_col][:2],
                        key=f"amt_{uploaded.name}",
                    )
                    if amount_cols:
                        mapped = df[[account_col] + amount_cols].copy()
                        mapped.columns = ["Account"] + [
                            f"Year {i+1}" for i in range(len(amount_cols))
                        ]
                        for col in mapped.columns[1:]:
                            mapped[col] = pd.to_numeric(mapped[col], errors="coerce").fillna(0)
                        all_dfs.append(mapped)

            if all_dfs and st.button("Confirm & Classify All", type="primary"):
                combined = pd.concat(all_dfs, ignore_index=True)
                _process_and_store(combined, entity_type)
                st.rerun()

    with tab_sample:
        st.markdown("Load sample data to explore the tool.")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Load Sample P&L"):
                _process_and_store(SAMPLE_PNL.copy(), entity_type)
                st.rerun()
        with col2:
            if st.button("Load Sample BS"):
                _process_and_store(SAMPLE_BS.copy(), entity_type)
                st.rerun()
        with col3:
            if st.button("Load Sample CF"):
                _process_and_store(SAMPLE_CF.copy(), entity_type)
                st.rerun()
        with col4:
            if st.button("Load All Three"):
                combined = pd.concat([
                    SAMPLE_PNL.copy(), SAMPLE_BS.copy(), SAMPLE_CF.copy(),
                ], ignore_index=True)
                _process_and_store(combined, entity_type)
                st.rerun()

    # --- Current status ---
    loaded = st.session_state.get("loaded_statements", set())
    if loaded:
        st.markdown("---")
        st.subheader("Loaded Data")
        for stmt_type in sorted(loaded):
            key = _stmt_key(stmt_type)
            if key in st.session_state:
                df = st.session_state[key]
                n = len(df)
                st.markdown(f"**{stmt_type}**: {n} line items")
                with st.expander(f"Preview {stmt_type}", expanded=False):
                    st.dataframe(df, use_container_width=True, hide_index=True)

        st.sidebar.success(f"Loaded: {', '.join(sorted(loaded))}")
