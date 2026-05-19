"""Extract the notes-to-the-financial-statements section of a PDF annual report.

Two-tier strategy (matches the main PDF extractor):
1. Cheap full-pass: pdfplumber text over every page to locate the notes
   section, segment it into individual notes, and capture each note's text body.
2. Document AI per-note (parallelised): for each note we call Document AI
   on its specific pages to extract the structured breakdown tables that
   drive disaggregation under IFRS 18. Concurrent requests keep the wait
   time down for typical 30–50-note reports.

Output is a dict keyed by note number. Each entry has:
    {
        "title": "Other operating expenses",
        "page_start": 42,   # 0-based
        "page_end": 43,     # inclusive
        "text": "<full text body>",
        "tables": [pd.DataFrame, ...],   # populated by enrichment
    }
"""

from __future__ import annotations

import io
import logging
import re
import pandas as pd
import pdfplumber
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.doc_parser import _call_docai, _pdf_subset

# Cap per-note pages sent to Document AI. A note longer than this is almost
# certainly a multi-page schedule (consolidation tree, segment reporting) —
# we keep the text body and skip table extraction to stay under the free-tier
# page budget and keep latency reasonable.
_MAX_NOTE_PAGES_FOR_DOCAI = 5

# How many DocAI calls to run in parallel. DocAI's per-project quota is 60
# requests/minute by default — well above this — and each call is I/O bound
# so threads are the simplest option. 8 keeps a 50-note enrichment under
# ~15 seconds wall time without risking quota errors.
_DOCAI_PARALLELISM = 8

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Locating the notes section
# ---------------------------------------------------------------------------

_NOTES_SECTION_MARKERS = [
    "notes to the consolidated financial statements",
    "notes to the financial statements",
    "notes to the group financial statements",
    "notes to the company financial statements",
    "notes to the accounts",
]

# A note heading looks like "1. Revenue", "12 Other operating expenses",
# "Note 4: Property, plant and equipment", "Note 1 – Revenue". We require:
#  - a number 1-999 at the start of the line
#  - optional "Note" prefix, optional punctuation after the number
#    (periods, parens, colons, hyphens, en/em dashes)
#  - a title of at least 3 characters starting with an uppercase letter
#  - line ends after the title (no trailing amounts — that's a table row)
_NOTE_HEADING_RE = re.compile(
    r"^\s*(?:note\s+)?(\d{1,3})\s*[\.\)\:\-–—]?\s+"
    r"([A-Z][A-Za-z0-9 &,\-/'()–—]{2,120})\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _find_notes_section_start(pages_text: list[str]) -> int | None:
    """Return the 0-based page index where the notes section begins, or None."""
    for i, text in enumerate(pages_text):
        low = text.lower()
        if any(marker in low for marker in _NOTES_SECTION_MARKERS):
            return i
    return None


def _find_notes_start_by_heading(
    pages_text: list[str], skip_pages: set[int] | None = None,
) -> int | None:
    """Locate the notes section by finding the first 'Note 1' (or '1. <title>')
    heading on a page we haven't already identified as a primary statement.

    Many real-world annual reports don't print a "Notes to the financial
    statements" banner — they just jump straight into the numbered notes after
    the auditor report. This fallback anchors on the first note-1 heading.
    """
    skip = skip_pages or set()
    # Accept note-1 heading OR note-2 heading on a later page (very rarely the
    # FS opens with a standalone Note 1 on a shared page with other content
    # that breaks the regex; the first monotonic chain we find is good enough).
    for target_first_num in (1, 2):
        for i, text in enumerate(pages_text):
            if i in skip:
                continue
            for line in text.splitlines():
                m = _NOTE_HEADING_RE.match(line)
                if m and int(m.group(1)) == target_first_num:
                    return i
    return None


# ---------------------------------------------------------------------------
# Segmenting notes within the notes section
# ---------------------------------------------------------------------------

def _segment_notes(pages_text: list[str], start_page: int) -> dict[int, dict]:
    """Walk pages from `start_page` onwards, collecting note segments.

    Each note starts at a recognised heading ("12 Other operating expenses")
    and runs until the next heading. Multi-page notes are captured.
    """
    notes: dict[int, dict] = {}
    current_num: int | None = None
    current_buf: list[str] = []
    current_start = start_page
    current_title = ""

    def _flush(end_page: int):
        if current_num is None:
            return
        notes[current_num] = {
            "title": current_title,
            "page_start": current_start,
            "page_end": end_page,
            "text": "\n".join(current_buf).strip(),
            "tables": [],
        }

    for page_idx in range(start_page, len(pages_text)):
        text = pages_text[page_idx] or ""
        lines = text.splitlines()
        for line in lines:
            m = _NOTE_HEADING_RE.match(line)
            if m:
                num = int(m.group(1))
                title = m.group(2).strip()
                # Sanity: the number must be reasonable AND monotonically
                # increasing. Otherwise this is probably a table row that
                # happens to start with a digit, not a note heading.
                if current_num is not None and num <= current_num:
                    current_buf.append(line)
                    continue
                if current_num is not None and num > current_num + 20:
                    # Huge jump — probably a spurious match (e.g. "2026 figures").
                    current_buf.append(line)
                    continue
                _flush(page_idx)
                current_num = num
                current_title = title
                current_start = page_idx
                current_buf = []
            else:
                if current_num is not None:
                    current_buf.append(line)

    _flush(len(pages_text) - 1)
    return notes


# ---------------------------------------------------------------------------
# Note-reference detection in primary statements
# ---------------------------------------------------------------------------

# Captures "Note 12", "Notes 12, 13", "(Note 12)", "(12)" — when preceded by
# a space or parenthesis so we don't pick up digits inside amounts.
_REF_WITH_KEYWORD = re.compile(
    r"\bnotes?\s+(\d{1,3}(?:\s*[,&]\s*\d{1,3})*)", re.IGNORECASE,
)
_REF_PAREN_ONLY = re.compile(r"\((\d{1,3})\)\s*$")


def detect_note_references(classified_df: pd.DataFrame) -> dict[int, list[int]]:
    """Scan Account column for note references.

    Returns {row_index: [note_nums]}.
    """
    refs: dict[int, list[int]] = {}
    if "Account" not in classified_df.columns:
        return refs

    for idx, acct in classified_df["Account"].items():
        if not isinstance(acct, str):
            continue
        nums: list[int] = []

        for m in _REF_WITH_KEYWORD.finditer(acct):
            for tok in re.split(r"[,&\s]+", m.group(1)):
                if tok.isdigit():
                    nums.append(int(tok))

        pm = _REF_PAREN_ONLY.search(acct)
        if pm:
            nums.append(int(pm.group(1)))

        if nums:
            # Dedupe while preserving order.
            seen = set()
            refs[int(idx)] = [n for n in nums if not (n in seen or seen.add(n))]

    return refs


# ---------------------------------------------------------------------------
# Main entry: build notes corpus from PDF bytes
# ---------------------------------------------------------------------------

def extract_notes_corpus(pdf_bytes: bytes) -> dict[int, dict]:
    """Extract the notes corpus from a PDF.

    Returns {note_num: {title, page_start, page_end, text, tables}}.
    Empty dict if no notes can be located.

    Two detection strategies, tried in order:
      1. Section-header marker ("Notes to the financial statements").
      2. First 'Note 1' / '1. <Title>' heading past the primary statements.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                try:
                    pages_text.append(page.extract_text() or "")
                except Exception:
                    pages_text.append("")
    except Exception as e:
        logger.warning("Could not open PDF for notes extraction: %s", e)
        return {}

    # Strategy 1: explicit section header.
    start = _find_notes_section_start(pages_text)

    # Strategy 2: fall back to first 'Note 1' heading, skipping pages already
    # detected as primary statements (so we don't trip on numbered lines
    # inside the P&L / BS / CF).
    if start is None:
        from modules.doc_parser import _find_primary_statement_pages
        try:
            skip = set(_find_primary_statement_pages(pdf_bytes))
        except Exception:
            skip = set()
        start = _find_notes_start_by_heading(pages_text, skip_pages=skip)

    if start is None:
        logger.info("No notes section detected in PDF.")
        return {}

    notes = _segment_notes(pages_text, start)
    logger.info("Extracted %d notes starting at page %d", len(notes), start + 1)
    return notes


def enrich_notes_with_docai(
    notes: dict[int, dict],
    pdf_bytes: bytes,
    note_nums: list[int] | None = None,
) -> dict[int, dict]:
    """Call Document AI on every note's pages (or just the listed ones) and
    attach structured tables. Runs in parallel — typical 50-note report
    finishes in ~15 seconds, vs. 100+ seconds serial.

    Mutates and returns the notes dict (tables added in-place).
    """
    targets = note_nums if note_nums is not None else list(notes.keys())

    def _enrich_one(num: int) -> tuple[int, list[pd.DataFrame] | None]:
        note = notes.get(num)
        if not note or note.get("tables"):
            return num, None
        page_start = note.get("page_start")
        page_end = note.get("page_end")
        if page_start is None or page_end is None:
            return num, None
        pages = list(range(page_start, page_end + 1))
        if not pages or len(pages) > _MAX_NOTE_PAGES_FOR_DOCAI:
            return num, None
        subset = _pdf_subset(pdf_bytes, pages)
        if subset is None:
            return num, None
        doc = _call_docai(subset)
        if doc is None:
            return num, None
        return num, _docai_doc_to_tables(doc)

    with ThreadPoolExecutor(max_workers=_DOCAI_PARALLELISM) as executor:
        futures = [executor.submit(_enrich_one, n) for n in targets]
        for fut in as_completed(futures):
            try:
                num, tables = fut.result()
            except Exception as e:
                logger.warning("Note enrichment task failed: %s", e)
                continue
            if tables is not None and num in notes:
                notes[num]["tables"] = tables

    return notes


def _docai_doc_to_tables(doc) -> list[pd.DataFrame]:
    """Pull tables out of a DocAI Document response as DataFrames."""
    full_text = doc.text or ""

    def _layout_text(layout) -> str:
        if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
            return ""
        parts = []
        for seg in layout.text_anchor.text_segments:
            start = int(seg.start_index) if seg.start_index else 0
            end = int(seg.end_index)
            parts.append(full_text[start:end])
        return "".join(parts).strip().replace("\n", " ")

    tables: list[pd.DataFrame] = []
    for page in doc.pages:
        for table in page.tables:
            rows = []
            for hr in table.header_rows:
                rows.append([_layout_text(c.layout) for c in hr.cells])
            for br in table.body_rows:
                rows.append([_layout_text(c.layout) for c in br.cells])
            if len(rows) < 2 or len(rows[0]) < 2:
                continue
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            tables.append(pd.DataFrame(rows).fillna(""))
    return tables
