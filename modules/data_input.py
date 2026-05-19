"""Step 1: Data Input & Classification — Upload financial statements,
auto-detect statement type, and review/adjust IFRS 18 classifications inline."""

import streamlit as st
import pandas as pd
from modules.doc_parser import (
    extract_tables_from_pdf,
    extract_tables_from_docx,
    extract_tables_from_image,
    _ocr_available,
)
from modules.statement_detector import detect_table_type, auto_classify
from modules.classification import render_classification


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


def _process_and_store(df: pd.DataFrame, entity_type: str, source: dict | None = None):
    """Auto-detect, classify, and store data split by statement type.

    When `source` is provided, also stores the raw pre-classification frame
    and its source metadata so the upload can be reanalyzed later.
    """
    # Clear previously-classified statements so a reanalysis doesn't leave
    # stale data from a different upload in session state.
    for key in (
        "classified_pnl", "classified_bs", "classified_cf",
        "notes_corpus", "note_references",
    ):
        st.session_state.pop(key, None)

    classified = auto_classify(df, entity_type)

    # Split by statement type and store
    for stmt_type in classified["Statement"].unique():
        subset = classified[classified["Statement"] == stmt_type].copy()
        key = _stmt_key(stmt_type)
        st.session_state[key] = subset

    st.session_state["all_classified"] = classified
    st.session_state["loaded_statements"] = set(classified["Statement"].unique())

    # Remember the raw upload so the user can reanalyze it later
    if source is not None:
        st.session_state["raw_upload"] = df.copy()
        st.session_state["raw_upload_source"] = source

    # Extract notes corpus from the original PDF (if any). Runs inline so the
    # user sees notes ready by the time they navigate to Step 2.
    _extract_and_store_notes()

    # Auto-save to disk
    from modules.persistence import auto_save
    auto_save()


def _reextract_from_saved_files(entity_type: str):
    """Re-run the full upload pipeline on the originally-uploaded file bytes.

    Used by the Reanalyse button — applies the current parser version (DocAI,
    heuristics, notes extraction) to a previously-uploaded file without
    requiring the user to re-upload it.
    """
    import io as _io

    file_bytes = st.session_state.get("raw_upload_files_bytes") or {}
    if not file_bytes:
        return

    all_dfs: list[pd.DataFrame] = []
    names: list[str] = []
    for fname, data in file_bytes.items():
        wrapped = _io.BytesIO(data)
        wrapped.name = fname
        with st.spinner(f"Re-extracting {fname}..."):
            df, tables = _load_file(wrapped)
        names.append(fname)
        if tables:
            # PDF / DOCX / image — take every extracted table; we already
            # auto-rank/dedupe them inside the parser.
            all_dfs.extend(tables)
        elif df is not None and len(df) > 0:
            # CSV / Excel — best-effort: keep first column as Account, treat
            # remaining numeric columns as periods. Lossy for files where the
            # user previously did manual column mapping; re-upload if so.
            mapped = df.copy()
            cols = list(mapped.columns)
            if cols:
                mapped.columns = ["Account"] + [
                    f"Year {i + 1}" for i in range(len(cols) - 1)
                ]
            for col in mapped.columns[1:]:
                mapped[col] = pd.to_numeric(mapped[col], errors="coerce").fillna(0)
            all_dfs.append(mapped)

    if not all_dfs:
        st.warning(
            "Re-extraction returned no tables. The original files may be "
            "scanned-only or in a format the new pipeline can't read."
        )
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    _process_and_store(
        combined, entity_type,
        source={"type": "files", "names": names},
    )
    st.success(f"Re-extracted {len(all_dfs)} table(s) from {len(names)} file(s).")


def _extract_and_store_notes():
    """Build the notes corpus from any PDF in raw_upload_files_bytes, then
    enrich notes referenced from the primary statements via Document AI."""
    from modules.notes_parser import (
        extract_notes_corpus,
        detect_note_references,
        enrich_notes_with_docai,
    )

    file_bytes = st.session_state.get("raw_upload_files_bytes") or {}
    # Prefer the largest PDF — typical case is one annual-report PDF plus
    # maybe an Excel working paper.
    pdf_bytes = None
    for name, data in file_bytes.items():
        if name.lower().endswith(".pdf"):
            if pdf_bytes is None or len(data) > len(pdf_bytes):
                pdf_bytes = data
    if not pdf_bytes:
        return

    with st.spinner("Extracting notes to the financial statements..."):
        notes = extract_notes_corpus(pdf_bytes)
    if not notes:
        return

    # Collect which notes are referenced from each classified statement
    # (so we can star them in the UI and feed them to disaggregation later).
    refs_by_stmt: dict[str, dict[int, list[int]]] = {}
    for key in ("classified_pnl", "classified_bs", "classified_cf"):
        df = st.session_state.get(key)
        if df is None:
            continue
        stmt_refs = detect_note_references(df)
        if stmt_refs:
            refs_by_stmt[key] = stmt_refs

    # Run Document AI on every note in parallel to extract structured
    # breakdown tables. Notes longer than _MAX_NOTE_PAGES_FOR_DOCAI keep
    # text only (caps cost and latency on rare multi-page schedules).
    with st.spinner(
        f"Extracting structured tables from {len(notes)} note(s) via Document AI..."
    ):
        notes = enrich_notes_with_docai(notes, pdf_bytes)

    st.session_state["notes_corpus"] = notes
    st.session_state["note_references"] = refs_by_stmt

    # Re-classify any P&L rows that reference a note, using the note text
    # as additional context. Mostly matters for ambiguous items like
    # "Interest" or "Other income" where the category depends on what's
    # actually inside the note.
    _reclassify_with_notes(refs_by_stmt, notes, entity_type)


def _reclassify_with_notes(
    refs_by_stmt: dict[str, dict[int, list[int]]],
    notes_corpus: dict[int, dict],
    entity_type: str,
):
    """Override classifications using note text where a row links to one."""
    from modules.ifrs18_categories import classify_pnl_item
    from modules.notes_parser import note_context_for

    pnl_refs = refs_by_stmt.get("classified_pnl") or {}
    if not pnl_refs:
        return

    df = st.session_state.get("classified_pnl")
    if df is None or df.empty:
        return

    df = df.copy()
    changed = 0
    for row_idx, note_nums in pnl_refs.items():
        if row_idx >= len(df):
            continue
        ctx = note_context_for(notes_corpus, note_nums)
        if not ctx:
            continue
        acct = str(df.iloc[row_idx]["Account"])
        new_cat = classify_pnl_item(acct, entity_type, note_context=ctx).value
        if new_cat != df.iloc[row_idx].get("Category"):
            df.iat[row_idx, df.columns.get_loc("Category")] = new_cat
            changed += 1
    if changed:
        st.session_state["classified_pnl"] = df
        # Also refresh the all_classified mirror so the export step stays
        # in sync with the per-statement views.
        all_df = st.session_state.get("all_classified")
        if isinstance(all_df, pd.DataFrame) and not all_df.empty:
            all_df = all_df.copy()
            mask = all_df["Statement"] == "Profit or Loss"
            all_df.loc[mask, "Category"] = df["Category"].values[:mask.sum()]
            st.session_state["all_classified"] = all_df


def _stmt_key(stmt_type: str) -> str:
    """Session state key for a statement type."""
    return {
        "Profit or Loss": "classified_pnl",
        "Balance Sheet": "classified_bs",
        "Cash Flow": "classified_cf",
    }.get(stmt_type, "classified_other")


def render_data_input():
    st.header("Step 1: Data Input & Classification")

    st.markdown(
        "Upload your financial statements. The tool **automatically identifies** whether "
        "data is from the Income Statement (P&L), Balance Sheet, or Cash Flow Statement. "
        "You can upload a single statement or multiple files."
    )

    entity_type = st.session_state.get("entity_type", "General (non-financial)")

    # Reserve a slot at the top of the page for the "previous upload" /
    # Reanalyse card. We fill it AFTER the upload tab has had a chance to
    # persist newly-uploaded bytes, so the card reflects the latest state
    # within the same render — no rerun gymnastics required.
    reanalyse_slot = st.empty()

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
            file_bytes: dict[str, bytes] = {}
            for uploaded in files:
                # Capture raw bytes for persistence / later reanalysis
                try:
                    uploaded.seek(0)
                    file_bytes[uploaded.name] = uploaded.read()
                    uploaded.seek(0)
                except Exception:
                    pass

            # Persist file bytes immediately, before any "Confirm" click.
            # Saves the user from losing their upload if extraction was poor
            # and they want to Reanalyse with a parser improvement later.
            if file_bytes:
                existing = st.session_state.get("raw_upload_files_bytes") or {}
                new_files = {
                    k: v for k, v in file_bytes.items() if k not in existing
                }
                if new_files:
                    existing.update(new_files)
                    st.session_state["raw_upload_files_bytes"] = existing
                    from modules.persistence import auto_save
                    auto_save()

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
                if file_bytes:
                    st.session_state["raw_upload_files_bytes"] = file_bytes
                source = {"type": "files", "names": [f.name for f in files]}
                _process_and_store(combined, entity_type, source=source)
                st.rerun()

    with tab_sample:
        st.markdown("Load sample data to explore the tool.")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Load Sample P&L"):
                st.session_state.pop("raw_upload_files_bytes", None)
                _process_and_store(
                    SAMPLE_PNL.copy(), entity_type,
                    source={"type": "sample", "names": ["Sample P&L"]},
                )
                st.rerun()
        with col2:
            if st.button("Load Sample BS"):
                st.session_state.pop("raw_upload_files_bytes", None)
                _process_and_store(
                    SAMPLE_BS.copy(), entity_type,
                    source={"type": "sample", "names": ["Sample BS"]},
                )
                st.rerun()
        with col3:
            if st.button("Load Sample CF"):
                st.session_state.pop("raw_upload_files_bytes", None)
                _process_and_store(
                    SAMPLE_CF.copy(), entity_type,
                    source={"type": "sample", "names": ["Sample CF"]},
                )
                st.rerun()
        with col4:
            if st.button("Load All Three"):
                st.session_state.pop("raw_upload_files_bytes", None)
                combined = pd.concat([
                    SAMPLE_PNL.copy(), SAMPLE_BS.copy(), SAMPLE_CF.copy(),
                ], ignore_index=True)
                _process_and_store(
                    combined, entity_type,
                    source={"type": "sample", "names": ["Sample P&L", "Sample BS", "Sample CF"]},
                )
                st.rerun()

    # Now fill the reserved slot at the top with the Reanalyse / previous-
    # upload card. By rendering it here (after the upload tab has had its
    # chance to persist newly-uploaded bytes), the card always reflects the
    # latest session state — no rerun gymnastics required.
    has_df = isinstance(st.session_state.get("raw_upload"), pd.DataFrame) \
        and not st.session_state["raw_upload"].empty
    has_bytes = bool(st.session_state.get("raw_upload_files_bytes"))
    if has_df or has_bytes:
        with reanalyse_slot.container():
            _render_previous_upload(entity_type)

    # Debug panel — collapsed by default. Helps diagnose state issues without
    # needing screenshots: just expand and copy the contents back.
    with st.expander("Debug info (state snapshot)", expanded=False):
        files_info = st.session_state.get("raw_upload_files_bytes") or {}
        file_summary = (
            ", ".join(f"{k} ({len(v):,} bytes)" for k, v in files_info.items())
            if files_info else "(empty)"
        )
        raw = st.session_state.get("raw_upload")
        raw_summary = (
            f"DataFrame, {len(raw)} rows, {len(raw.columns)} cols"
            if isinstance(raw, pd.DataFrame) else "(absent)"
        )
        notes = st.session_state.get("notes_corpus") or {}
        loaded_stmts = st.session_state.get("loaded_statements") or set()
        st.code(
            f"raw_upload_files_bytes: {file_summary}\n"
            f"raw_upload: {raw_summary}\n"
            f"loaded_statements: {sorted(loaded_stmts) if loaded_stmts else '(empty)'}\n"
            f"notes_corpus: {len(notes)} notes\n"
            f"signed_in: {bool(st.session_state.get('_persistence_loaded'))}\n",
            language="text",
        )

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

        # Entity context — auto-extracts what it can, prompts for the rest.
        st.markdown("---")
        from modules.entity_context import render_context_form
        render_context_form()

        # IFRS 18 classification editors — merged in from the former Step 2.
        render_classification()


def _render_previous_upload(entity_type: str):
    """Show the last saved upload with a button to rerun the analysis."""
    raw = st.session_state.get("raw_upload")
    source = st.session_state.get("raw_upload_source") or {}
    file_bytes = st.session_state.get("raw_upload_files_bytes") or {}

    has_df = isinstance(raw, pd.DataFrame) and not raw.empty
    has_bytes = bool(file_bytes)
    if not has_df and not has_bytes:
        return

    src_type = source.get("type", "upload")
    names = source.get("names") or list(file_bytes.keys())
    label = "Sample data" if src_type == "sample" else "Uploaded file(s)"

    with st.container(border=True):
        header = f"**Previous {label.lower()}**"
        if has_df:
            header += f" — {len(raw)} rows"
        st.markdown(header)
        if names:
            st.caption(", ".join(names))

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            # If we still have the original file bytes, "Reanalyse" re-runs the
            # full pipeline (table extraction + classification + notes). This
            # is what you want after a parser upgrade. If only the parsed df
            # is left (older session with no saved bytes), fall back to
            # re-classification only.
            if has_bytes:
                if st.button(
                    "Reanalyse",
                    type="primary",
                    help="Re-run the full pipeline (extraction + classification "
                         "+ notes) on the originally-uploaded file(s).",
                ):
                    _reextract_from_saved_files(entity_type)
                    st.rerun()
            elif has_df:
                if st.button(
                    "Reanalyse",
                    type="primary",
                    help="Re-classify the previous upload "
                         "(useful after changing entity type).",
                ):
                    _process_and_store(raw.copy(), entity_type, source=source)
                    st.success("Reanalysed with current entity settings.")
                    st.rerun()
        with col_b:
            if has_df:
                with st.popover("Preview data"):
                    st.dataframe(raw, use_container_width=True, hide_index=True)
        with col_c:
            if st.button("Clear previous upload"):
                for key in (
                    "raw_upload",
                    "raw_upload_source",
                    "raw_upload_files_bytes",
                    "notes_corpus",
                    "note_references",
                ):
                    st.session_state.pop(key, None)
                from modules.persistence import auto_save
                auto_save()
                st.rerun()

        # Offer downloads of the original uploaded files, if available
        file_bytes = st.session_state.get("raw_upload_files_bytes") or {}
        if file_bytes:
            with st.expander("Original files"):
                for fname, data in file_bytes.items():
                    st.download_button(
                        f"Download {fname}",
                        data=data,
                        file_name=fname,
                        key=f"dl_raw_{fname}",
                    )
