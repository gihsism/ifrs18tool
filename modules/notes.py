"""Step 2: Notes — browse the extracted notes corpus and the links from
primary-statement lines to their supporting notes."""

import streamlit as st
import pandas as pd


_STMT_LABELS = {
    "classified_pnl": "Income Statement",
    "classified_bs": "Balance Sheet",
    "classified_cf": "Cash Flow Statement",
}


def render_notes():
    st.header("Step 2: Notes to the Financial Statements")

    notes = st.session_state.get("notes_corpus") or {}
    refs = st.session_state.get("note_references") or {}

    if not notes:
        st.info(
            "No notes were extracted from the uploaded PDF yet. Upload a full "
            "annual-report PDF in Step 1 — the notes-to-the-FS section will be "
            "parsed automatically."
        )
        return

    st.caption(
        f"**{len(notes)} notes** extracted. Notes referenced from the primary "
        "statements are marked ⭐ and carry enriched tables from Document AI. "
        "Other notes hold text only (fast, free extraction)."
    )

    # Build reverse index: {note_num: [(statement, account, row_idx), ...]}
    referenced_by: dict[int, list[tuple[str, str, int]]] = {}
    for stmt_key, row_refs in refs.items():
        df = st.session_state.get(stmt_key)
        if df is None:
            continue
        label = _STMT_LABELS.get(stmt_key, stmt_key)
        for row_idx, note_nums in row_refs.items():
            try:
                account = str(df.iloc[int(row_idx)]["Account"])
            except Exception:
                account = f"(row {row_idx})"
            for n in note_nums:
                referenced_by.setdefault(n, []).append((label, account, int(row_idx)))

    # Controls
    show_referenced_only = st.checkbox(
        "Show only notes referenced from the primary statements", value=False,
    )

    sorted_nums = sorted(notes.keys())
    for num in sorted_nums:
        note = notes[num]
        is_referenced = num in referenced_by
        if show_referenced_only and not is_referenced:
            continue

        title = note.get("title", "")
        pages = _format_page_range(note)
        star = "⭐ " if is_referenced else ""
        tables = note.get("tables") or []

        with st.expander(
            f"{star}**Note {num}** — {title} ({pages})"
            + (f" · {len(tables)} table(s)" if tables else ""),
            expanded=False,
        ):
            if is_referenced:
                st.markdown("**Referenced from:**")
                for label, account, _ in referenced_by[num]:
                    st.markdown(f"- {label}: *{account}*")
                st.markdown("")

            if tables:
                for i, tbl in enumerate(tables):
                    st.markdown(f"**Table {i + 1}:**")
                    st.dataframe(tbl, use_container_width=True, hide_index=True)
                st.markdown("")

            text = note.get("text", "").strip()
            if text:
                st.markdown("**Text:**")
                # Truncate very long notes with an option to see more.
                if len(text) > 3000:
                    st.text_area(
                        "Note body", value=text, height=400,
                        key=f"note_text_{num}", label_visibility="collapsed",
                    )
                else:
                    st.write(text)
            else:
                st.caption("_(no text body captured)_")


def _format_page_range(note: dict) -> str:
    start = note.get("page_start")
    end = note.get("page_end")
    if start is None:
        return "—"
    if end is None or end <= start:
        return f"p. {start + 1}"
    return f"p. {start + 1}–{end + 1}"
