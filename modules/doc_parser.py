"""Parse financial statement tables from PDF, Word, and image files.

PDF extraction strategies (tried in order, first-one-that-works wins):
1. Google Document AI Form Parser (ML model purpose-built for borderless
   financial tables — handles real-world FS PDFs with narrative, notes,
   subtotals, and multi-column layouts). Primary path.
2. pdfplumber table detection (4 strategies for different layouts).
3. Word-position clustering (handles borderless tables without ML).
4. Layout-preserving text parsing (line-by-line).
5. OCR (for scanned PDFs — pytesseract + Pillow).

Paths 2–5 are fallbacks when Document AI is unavailable or returns nothing.

Multi-page support: tables spanning pages are merged.
"""

import os
import re
import io
import logging
import pandas as pd
import pdfplumber
from collections import Counter
from docx import Document

logger = logging.getLogger(__name__)

# Document AI config — overridable via env vars.
_DOCAI_PROJECT = os.environ.get("DOCUMENT_AI_PROJECT", "ifrs18tool-15496")
_DOCAI_LOCATION = os.environ.get("DOCUMENT_AI_LOCATION", "eu")
_DOCAI_PROCESSOR_ID = os.environ.get("DOCUMENT_AI_PROCESSOR_ID", "d66b71583b1a1ebf")


# ---------------------------------------------------------------------------
# Number parsing
# ---------------------------------------------------------------------------

def _clean_number(value) -> float | None:
    """Parse a financial number string.  Handles (parens), currency, thousands sep."""
    if value is None:
        return None
    if not isinstance(value, str):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    s = value.strip()
    if not s or s in ("-", "—", "–", "n/a", "N/A", "nil", "Nil", "None", ""):
        return 0.0

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    elif s.startswith("-") or s.startswith("–") or s.startswith("—"):
        negative = True
        s = s[1:]

    s = re.sub(r"[£$€¥₹\s'\u00a0\u2009]", "", s)
    s = s.replace(",", "").replace(" ", "")

    if s.endswith("-"):
        negative = True
        s = s[:-1]

    if not s:
        return 0.0

    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def _is_number_like(value: str) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s or s in ("-", "—", "–"):
        return False
    result = _clean_number(s)
    return result is not None and result != 0.0


def _is_header_value(value: str) -> bool:
    s = value.strip()
    if not s:
        return False
    if re.match(r"^(FY|CY|PY)?\s*\d{4}$", s, re.IGNORECASE):
        return True
    header_words = [
        "amount", "total", "note", "notes", "current", "prior",
        "year", "period", "restated", "audited", "unaudited",
        "budget", "actual", "forecast", "eur", "usd", "gbp", "chf",
        "rm", "r'000", "'000", "000", "million", "m", "$m", "£m",
        "thousands", "in thousands", "rs", "inr",
    ]
    return s.lower() in header_words or re.match(r"^\d{4}/\d{2,4}$", s)


# ---------------------------------------------------------------------------
# Table scoring
# ---------------------------------------------------------------------------

def _score_table(df: pd.DataFrame) -> float:
    if df.shape[1] < 2 or df.shape[0] < 3:
        return 0

    score = 0
    first_col = df.iloc[:, 0].astype(str)
    text_cells = sum(1 for v in first_col if v.strip() and not _is_number_like(v))
    score += (text_cells / max(len(first_col), 1)) * 25

    num_col_count = 0
    total_num_cells = 0
    for col_idx in range(1, df.shape[1]):
        col_vals = df.iloc[:, col_idx].astype(str)
        num_cells = sum(1 for v in col_vals if _is_number_like(v))
        if num_cells / max(len(col_vals), 1) > 0.2:
            num_col_count += 1
            total_num_cells += num_cells
    score += min(num_col_count, 3) * 10
    score += min(total_num_cells, 20)

    financial_keywords = [
        "revenue", "sales", "cost", "profit", "loss", "income", "expense",
        "tax", "interest", "dividend", "depreciation", "amortis", "ebitda",
        "operating", "gross", "net", "total", "finance", "asset", "liabilit",
        "equity", "cash", "receivable", "payable", "inventory", "provision",
        "impairment", "turnover", "borrowing",
    ]
    keyword_hits = sum(
        1 for v in first_col
        if any(kw in v.lower() for kw in financial_keywords)
    )
    score += (keyword_hits / max(len(first_col), 1)) * 25

    return min(score, 100)


# ---------------------------------------------------------------------------
# Table standardisation
# ---------------------------------------------------------------------------

def _standardise_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", pd.NA).replace("None", pd.NA)
    df = df.dropna(how="all").dropna(axis=1, how="all").fillna("")
    df = df.reset_index(drop=True)

    if df.shape[0] < 2 or df.shape[1] < 2:
        return pd.DataFrame()

    # Detect header row
    header_row_idx = None
    for check_idx in range(min(3, len(df))):
        row_vals = df.iloc[check_idx].astype(str).tolist()
        non_first = row_vals[1:]
        header_like = sum(1 for v in non_first if _is_header_value(v) or not v.strip())
        has_big_number = any(
            _is_number_like(v) and abs(_clean_number(v) or 0) >= 100
            and not re.match(r"^\d{4}$", v.strip())
            for v in non_first
        )
        if header_like >= len(non_first) * 0.5 and not has_big_number:
            header_row_idx = check_idx
            break

    if header_row_idx is not None:
        header = [str(c).strip() for c in df.iloc[header_row_idx]]
        df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
        header[0] = "Account"
        for i in range(1, len(header)):
            if not header[i]:
                header[i] = f"Column {i}"
        df.columns = header
    else:
        df.columns = ["Account"] + [f"Column {i}" for i in range(1, df.shape[1])]

    # Deduplicate column names
    cols = list(df.columns)
    cols[0] = "Account"
    seen = {}
    for i in range(1, len(cols)):
        name = cols[i]
        if name in seen:
            seen[name] += 1
            cols[i] = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
    df.columns = cols

    df["Account"] = df.iloc[:, 0].astype(str).str.strip()

    for i in range(1, len(df.columns)):
        df.iloc[:, i] = df.iloc[:, i].astype(str).apply(_clean_number)

    # Drop empty columns
    cols_to_drop = []
    for i in range(1, len(df.columns)):
        col_series = df.iloc[:, i]
        if col_series.isna().all() or (col_series.fillna(value=0, inplace=False) == 0).all():
            cols_to_drop.append(df.columns[i])
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    df = df[df["Account"].str.strip().str.len() > 0].copy()
    amount_cols = [c for c in df.columns if c != "Account"]
    if amount_cols:
        df = df.dropna(subset=amount_cols, how="all")
    for col in amount_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df.reset_index(drop=True)


def _final_score(std_df: pd.DataFrame, raw_score: float) -> float:
    """Re-score a standardised table with quality checks."""
    amount_cols = [c for c in std_df.columns if c != "Account"]
    score = raw_score

    if len(amount_cols) >= 2:
        score += 15
    score += min(len(std_df), 30)

    year_cols = sum(
        1 for c in amount_cols if re.match(r"^(FY|CY|PY)?\s*\d{4}$", str(c))
    )
    score += year_cols * 15

    multi_space = sum(1 for v in std_df["Account"] if "  " in str(v))
    score -= (multi_space / max(len(std_df), 1)) * 30

    junk = sum(
        1 for v in std_df["Account"]
        if re.match(r"^(for\s+the|year\s+ended|as\s+at|note\s|account\s)", str(v).lower().strip())
    )
    score -= junk * 10

    name_lengths = [len(str(v).strip()) for v in std_df["Account"]]
    avg_len = sum(name_lengths) / max(len(name_lengths), 1)
    short = sum(1 for l in name_lengths if l < 10)
    if avg_len < 15 and short > len(name_lengths) * 0.3:
        score -= 20

    # Narrative-text rejection. On real-world annual reports the heuristic
    # extractors (word clustering, line-by-line) happily turn paragraphs into
    # "tables" — first column ends up holding fragments like "These costs
    # arose f" or "the   five    other     major". Financial account names
    # are short (1-6 words), don't end mid-word, and don't contain large
    # internal whitespace runs.
    def _looks_like_prose(text: str) -> bool:
        s = str(text).strip()
        if not s:
            return False
        words = s.split()
        if len(words) > 8:
            return True
        # Last word is truncated (no terminal punctuation, ends mid-word)
        if len(words) >= 3 and len(words[-1]) <= 4 and words[-1][-1].isalpha():
            full = sum(1 for w in words if len(w) >= 6)
            if full < 2:
                return True
        # 4+ consecutive spaces suggests column-bleed from a narrative layout
        if "    " in s:
            return True
        return False

    prose_rows = sum(1 for v in std_df["Account"] if _looks_like_prose(v))
    prose_ratio = prose_rows / max(len(std_df), 1)
    if prose_ratio > 0.3:
        score -= 50  # very likely narrative misextraction
    elif prose_ratio > 0.15:
        score -= 25

    for col in amount_cols:
        zero_ratio = (std_df[col] == 0).sum() / max(len(std_df), 1)
        if zero_ratio > 0.5:
            score -= 15

    return score


def _dedupe_and_rank(candidates: list[tuple[pd.DataFrame, float]]) -> list[pd.DataFrame]:
    """Standardise, deduplicate, re-score, and rank candidate tables.

    Drops any candidate whose final score falls below the financial-table
    floor — this is the main defence against narrative-text false positives
    that the per-page heuristics happily produce on annual reports.
    """
    final = []
    seen = set()

    candidates.sort(key=lambda x: x[1], reverse=True)

    for raw_df, raw_score in candidates:
        try:
            std = _standardise_table(raw_df)
        except Exception:
            continue
        if std.empty or len(std) < 2:
            continue

        sig = (len(std), len(std.columns), tuple(std["Account"].head(5).tolist()))
        if sig in seen:
            continue
        seen.add(sig)

        score = _final_score(std, raw_score)
        # A real financial table almost always clears 35 on this scorer
        # (year columns + multiple amounts + recognisable accounts). Below
        # that we're in narrative-misextraction territory.
        if score < 35:
            continue
        final.append((std, score))

    final.sort(key=lambda x: x[1], reverse=True)
    return [df for df, _ in final]


# ---------------------------------------------------------------------------
# PDF: line-by-line text parsing (used by the main extractor and OCR path)
# ---------------------------------------------------------------------------

# Matches financial numbers: 500,000 or (280,000) or -45,000 or 8,500 or 2026
_NUM_TOKEN = re.compile(
    r"\([\s£$€¥]*[\d,]+\.?\d*\)"   # parenthesised: (280,000)
    r"|[\-–—][\s£$€¥]*[\d,]+\.?\d*"  # negative: -45,000
    r"|[\d,]+\.?\d*"                   # plain: 500,000
)


def _parse_financial_line(line: str) -> dict | None:
    """Parse a single text line into account description + number columns.

    Handles both layout-preserved text (numbers separated by spaces/tabs) and
    OCR output (numbers may be separated by single spaces).
    """
    line = line.strip()
    if not line or len(line) < 5:
        return None

    # Find all number tokens in the line
    matches = list(_NUM_TOKEN.finditer(line))
    if not matches:
        return None

    # Identify which matches are "real" financial numbers (not part of text)
    # Walk from the end of the line backwards to find the rightmost cluster of numbers
    real_numbers = []
    for m in reversed(matches):
        token = m.group().strip()
        val = _clean_number(token)
        if val is None:
            continue
        # Skip 4-digit numbers that look like years when they're part of description
        if re.match(r"^\d{4}$", token) and m.start() < len(line) * 0.3:
            continue
        real_numbers.append((m.start(), m.end(), val, token))

    real_numbers.reverse()

    if not real_numbers:
        return None

    # The description is everything before the first real number
    first_num_pos = real_numbers[0][0]
    desc = line[:first_num_pos].strip()
    desc = re.sub(r"[\s\.\-–—:]+$", "", desc)

    if len(desc) < 2:
        return None

    # Extract numbers
    nums = [val for _, _, val, _ in real_numbers]
    if not nums:
        return None

    row = {"Account": desc}
    for i, n in enumerate(nums):
        row[f"Column {i+1}"] = n
    return row


# ---------------------------------------------------------------------------
# OCR: for scanned PDFs and images
# ---------------------------------------------------------------------------

def _ocr_available() -> bool:
    """Check if OCR dependencies are available."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_image(image) -> list[dict]:
    """Run OCR on a PIL Image and parse financial lines.

    Starts with the single best combination (raw image + PSM 6 block layout)
    and only tries alternate preprocessing / PSM modes if the first pass
    yielded fewer than 3 usable rows. This cuts OCR time dramatically on
    normal financial statement images.
    """
    import pytesseract
    from PIL import ImageFilter, ImageOps

    def _run(processed, psm: int) -> list[dict]:
        try:
            text = pytesseract.image_to_string(processed, config=f"--oem 3 --psm {psm}")
        except Exception:
            return []
        rows = []
        for line in text.split("\n"):
            row = _parse_financial_line(line)
            if row:
                rows.append(row)
        return rows

    # Primary pass — the combination that works for ~90% of clean PDFs.
    best = _run(image, 6)
    if len(best) >= 3:
        return best

    # Only fall back if primary failed.
    try:
        sharpened = ImageOps.autocontrast(image.convert("L")).filter(ImageFilter.SHARPEN)
    except Exception:
        sharpened = None

    for processed, psm in [(sharpened, 6), (image, 4), (sharpened, 4)]:
        if processed is None:
            continue
        rows = _run(processed, psm)
        if len(rows) > len(best):
            best = rows
        if len(best) >= 3:
            break

    return best


def _ocr_pdf_pages(file) -> list[tuple[pd.DataFrame, float]]:
    """OCR each page of a PDF as an image."""
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        return []

    if not _ocr_available():
        return []

    try:
        file.seek(0)
        pdf_bytes = file.read()
        # 200 DPI is ~4x faster than 300 and still accurate enough for OCR of
        # printed financial statements. 300 was overkill.
        images = convert_from_bytes(pdf_bytes, dpi=200)
    except Exception:
        return []

    all_rows = []
    for img in images:
        all_rows.extend(_ocr_image(img))

    if len(all_rows) >= 3:
        df = pd.DataFrame(all_rows).fillna(0)
        score = _score_table(
            pd.DataFrame({str(i): df.iloc[:, i].astype(str) for i in range(df.shape[1])})
        )
        return [(df, max(score, 15))]
    return []


def extract_tables_from_image(file) -> list[pd.DataFrame]:
    """Extract financial tables from an image file (PNG, JPG, etc.)."""
    from PIL import Image

    if not _ocr_available():
        return []

    try:
        img = Image.open(file)
    except Exception:
        return []

    rows = _ocr_image(img)

    if len(rows) < 3:
        return []

    df = pd.DataFrame(rows).fillna(0)
    score = _score_table(
        pd.DataFrame({str(i): df.iloc[:, i].astype(str) for i in range(df.shape[1])})
    )
    return _dedupe_and_rank([(df, max(score, 15))])


# ---------------------------------------------------------------------------
# Google Document AI — primary extraction path for PDFs
# ---------------------------------------------------------------------------

_DOCAI_SYNC_PAGE_LIMIT = 15  # Form Parser sync quota
_DOCAI_SYNC_SIZE_LIMIT = 30 * 1024 * 1024

# Keywords that identify primary financial statement pages. Matched against
# lower-cased page text so we only send the pages that actually contain a
# main FS form to Document AI — not the whole annual report.
_PRIMARY_STATEMENT_KEYWORDS = [
    # P&L / OCI
    "statement of profit or loss",
    "statement of comprehensive income",
    "consolidated income statement",
    "income statement",
    "profit and loss account",
    "statement of operations",
    # Balance sheet
    "statement of financial position",
    "balance sheet",
    # Cash flow
    "statement of cash flows",
    "statement of cash flow",
    "cash flow statement",
    "cashflow statement",
    # Changes in equity (SoCE)
    "statement of changes in equity",
    "statement of changes in shareholders' equity",
    "statement of changes in shareholders equity",
    "statement of stockholders' equity",
    "statement of stockholders equity",
]


def _pdf_page_count(pdf_bytes: bytes) -> int:
    try:
        from pypdf import PdfReader
        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
    except Exception:
        return 0


def _find_primary_statement_pages(pdf_bytes: bytes, max_scan: int = 300) -> list[int]:
    """Locate primary-statement pages in a PDF.

    Two-tier strategy:
      1. **Keyword match** on lower-cased page text — the cheap, reliable
         path for English-language FS.
      2. **Number-density heuristic** — for non-English filings (German
         "Bilanz", French "Bilan", multilingual reports, etc.) we score each
         page by how many numeric tokens vs words it contains. The top
         number-dense pages in the first half of the document are returned.

    Returns a sorted, deduplicated list of 0-based page indexes plus the
    following page (statements often span two pages for comparative columns).
    """
    hits: set[int] = set()
    page_count = 0
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
            pages_text: list[str] = []
            for i, page in enumerate(pdf.pages[:max_scan]):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                pages_text.append(text)
                if any(kw in text.lower() for kw in _PRIMARY_STATEMENT_KEYWORDS):
                    hits.add(i)
                    if i + 1 < page_count:
                        hits.add(i + 1)
    except Exception:
        return []

    if hits:
        return sorted(hits)

    # Fallback: number-density heuristic. Pages with a high ratio of numeric
    # tokens are likely primary statements. We bias toward earlier pages
    # because primary statements normally appear before notes.
    scores: list[tuple[int, float]] = []
    for i, text in enumerate(pages_text):
        if not text:
            continue
        tokens = text.split()
        if len(tokens) < 20:
            continue
        num_tokens = sum(1 for t in tokens if _is_number_like(t))
        density = num_tokens / max(len(tokens), 1)
        # Bias: earlier pages get a small lift.
        position_bias = max(0.0, 1.0 - (i / max(page_count, 1)) * 0.5)
        scores.append((i, density * position_bias))

    if not scores:
        return []

    # Take the top number-dense pages, capped at 12 to leave headroom inside
    # the 15-page DocAI sync limit for adjacent-page expansion.
    scores.sort(key=lambda x: x[1], reverse=True)
    top = [i for i, score in scores[:12] if score > 0.15]
    if not top:
        return []

    expanded: set[int] = set(top)
    for i in top:
        if i + 1 < page_count:
            expanded.add(i + 1)
    return sorted(expanded)[:15]


def _pdf_subset(pdf_bytes: bytes, page_indexes: list[int]) -> bytes | None:
    """Build a new PDF containing only the given 0-based pages."""
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for idx in page_indexes:
            if 0 <= idx < len(reader.pages):
                writer.add_page(reader.pages[idx])
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as e:
        logger.warning("pypdf subset failed: %s", e)
        return None


def _call_docai(pdf_bytes: bytes):
    """Make one synchronous Document AI call. Returns the Document or None."""
    try:
        from google.cloud import documentai
    except ImportError:
        return None

    try:
        client = documentai.DocumentProcessorServiceClient(
            client_options={
                "api_endpoint": f"{_DOCAI_LOCATION}-documentai.googleapis.com"
            }
        )
        name = (
            f"projects/{_DOCAI_PROJECT}/locations/{_DOCAI_LOCATION}"
            f"/processors/{_DOCAI_PROCESSOR_ID}"
        )
        request = documentai.ProcessRequest(
            name=name,
            raw_document=documentai.RawDocument(
                content=pdf_bytes, mime_type="application/pdf",
            ),
        )
        return client.process_document(request=request).document
    except Exception as e:
        logger.warning("Document AI call failed: %s", e)
        return None


def _extract_via_document_ai(file) -> list[tuple[pd.DataFrame, float]]:
    """Extract tables from a PDF via Google Document AI Form Parser.

    For PDFs ≤ 15 pages, sends the whole document. For larger PDFs (typical
    annual reports), auto-detects the pages that contain primary statements
    (P&L / BS / CF) and sends only those — keeping us under the sync quota
    and the free-tier page budget.

    Returns [] on any error so callers fall back to heuristics.
    """
    try:
        file.seek(0)
        pdf_bytes = file.read()
    except Exception:
        return []

    if len(pdf_bytes) > _DOCAI_SYNC_SIZE_LIMIT:
        return []

    page_count = _pdf_page_count(pdf_bytes)

    if page_count == 0 or page_count <= _DOCAI_SYNC_PAGE_LIMIT:
        # Small PDF — send as-is.
        payload = pdf_bytes
    else:
        # Large PDF — shrink to the primary-statement pages only.
        candidate_pages = _find_primary_statement_pages(pdf_bytes)
        if not candidate_pages:
            logger.info(
                "Document AI: %d-page PDF, no primary-statement titles detected; "
                "falling back to heuristics.", page_count,
            )
            return []
        if len(candidate_pages) > _DOCAI_SYNC_PAGE_LIMIT:
            # Defensive truncation. Should rarely trip — a real FS rarely has
            # more than 10-ish primary-statement pages.
            candidate_pages = candidate_pages[:_DOCAI_SYNC_PAGE_LIMIT]
        logger.info(
            "Document AI: %d-page PDF, extracting pages %s",
            page_count, [p + 1 for p in candidate_pages],
        )
        payload = _pdf_subset(pdf_bytes, candidate_pages)
        if not payload:
            return []

    doc = _call_docai(payload)
    if doc is None:
        return []

    full_text = doc.text or ""

    def _layout_text(layout) -> str:
        """Slice document.text using a Layout's text_anchor segments."""
        if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
            return ""
        parts = []
        for seg in layout.text_anchor.text_segments:
            start = int(seg.start_index) if seg.start_index else 0
            end = int(seg.end_index)
            parts.append(full_text[start:end])
        return "".join(parts).strip().replace("\n", " ")

    candidates: list[tuple[pd.DataFrame, float]] = []
    for page in doc.pages:
        for table in page.tables:
            rows = []
            for header_row in table.header_rows:
                rows.append([_layout_text(c.layout) for c in header_row.cells])
            for body_row in table.body_rows:
                rows.append([_layout_text(c.layout) for c in body_row.cells])

            # Need at least a header + 2 data rows, and 2+ columns.
            if len(rows) < 3 or not rows or len(rows[0]) < 2:
                continue

            # Normalise row widths (DocAI occasionally produces ragged rows).
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]

            df = pd.DataFrame(rows).fillna("")
            score = _score_table(df)
            # DocAI tables are already semantic — boost the floor so they beat
            # fuzzy heuristic tables of similar raw score.
            if score > 10:
                candidates.append((df, score + 20))

    return candidates


# ---------------------------------------------------------------------------
# PDF: multi-page table merging
# ---------------------------------------------------------------------------

def _try_merge_pages(tables: list[pd.DataFrame]) -> list[pd.DataFrame]:
    """Attempt to merge tables from consecutive pages that look like continuations.

    Heuristic: two tables are continuations if they have the same number of columns
    and similar column names.
    """
    if len(tables) <= 1:
        return tables

    merged = [tables[0]]
    for tbl in tables[1:]:
        prev = merged[-1]
        # Same columns? Try to merge
        if (
            list(prev.columns) == list(tbl.columns)
            and len(prev.columns) >= 2
        ):
            # Check that tbl doesn't re-introduce a header
            first_acct = str(tbl.iloc[0].get("Account", "")).lower()
            if first_acct not in ("account", "description", "line item", ""):
                merged[-1] = pd.concat([prev, tbl], ignore_index=True)
                continue
        merged.append(tbl)

    return merged


# ---------------------------------------------------------------------------
# PDF: main entry point
# ---------------------------------------------------------------------------

_PDFPLUMBER_STRATEGIES = [
    {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
    {"vertical_strategy": "text", "horizontal_strategy": "text",
     "snap_tolerance": 10, "join_tolerance": 10,
     "min_words_vertical": 2, "min_words_horizontal": 1},
    {"vertical_strategy": "lines_strict", "horizontal_strategy": "lines_strict"},
    {"vertical_strategy": "lines", "horizontal_strategy": "text",
     "snap_tolerance": 8, "join_tolerance": 8},
]


def extract_tables_from_pdf(file) -> list[pd.DataFrame]:
    """Extract financial tables from a PDF.

    Combines two extractors and merges their candidates so we don't lose any
    primary statement:
      - Document AI Form Parser (best at borderless tables, semantic
        row/column structure). Limited to 15-page subsets, so for full annual
        reports we send only the detected primary-statement pages.
      - pdfplumber + word-clustering + text fallback (per-page, free). For
        annual-report-sized PDFs this is also restricted to the detected
        primary-statement pages — running it on every page of a 100-page
        document turns narrative paragraphs into dozens of garbage "tables".
    Both feed into the same dedupe/rank pipeline; the +20 score boost on DocAI
    candidates means clean DocAI tables win when both extractors found them,
    and a hard score floor in dedupe drops any narrative misextraction.
    """
    all_candidates: list[tuple[pd.DataFrame, float]] = []

    # Primary path: Document AI on detected primary-statement pages.
    all_candidates.extend(_extract_via_document_ai(file))

    try:
        file.seek(0)
    except Exception:
        pass

    # Decide which pages the heuristic sweep should look at. For small PDFs
    # (≤ DocAI sync limit) we look at everything; for larger reports we use
    # the same primary-statement-page detection that DocAI used, so the
    # heuristics complement DocAI on the SAME pages instead of dredging
    # narrative chapters elsewhere in the report.
    try:
        file.seek(0)
        pdf_bytes_for_pages = file.read()
        file.seek(0)
    except Exception:
        pdf_bytes_for_pages = b""

    page_filter: set[int] | None = None
    if pdf_bytes_for_pages:
        page_count = _pdf_page_count(pdf_bytes_for_pages)
        if page_count > _DOCAI_SYNC_PAGE_LIMIT:
            detected = _find_primary_statement_pages(pdf_bytes_for_pages)
            if detected:
                page_filter = set(detected)

    try:
        with pdfplumber.open(file) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                if page_filter is not None and page_idx not in page_filter:
                    continue
                page_got_good_table = False

                # Try structured table extraction with early-exit.
                for settings in _PDFPLUMBER_STRATEGIES:
                    try:
                        page_tables = page.extract_tables(table_settings=settings)
                    except Exception:
                        continue
                    for raw_table in page_tables or []:
                        if not raw_table or len(raw_table) < 3:
                            continue
                        df = pd.DataFrame(raw_table).fillna("")
                        score = _score_table(df)
                        if score > 15:
                            all_candidates.append((df, score))
                            if score > 40:
                                page_got_good_table = True
                    if page_got_good_table:
                        break

                if page_got_good_table:
                    continue

                # Fallback 1: word-position clustering for borderless tables.
                wpc = _cluster_page_words(page)
                if wpc is not None:
                    all_candidates.append(wpc)
                    if wpc[1] > 40:
                        continue

                # Fallback 2: line-by-line text parsing.
                try:
                    text = page.extract_text(layout=True, x_density=3, y_density=3) or ""
                except Exception:
                    text = ""
                rows = []
                for line in text.split("\n"):
                    row = _parse_financial_line(line)
                    if row:
                        rows.append(row)
                if len(rows) >= 3:
                    df = pd.DataFrame(rows).fillna(0)
                    score = _score_table(
                        pd.DataFrame({str(i): df.iloc[:, i].astype(str) for i in range(df.shape[1])})
                    )
                    all_candidates.append((df, max(score, 20)))
    except Exception:
        pass

    results = _dedupe_and_rank(all_candidates)

    # OCR only if text extraction yielded nothing — scanned PDF case.
    if not results:
        try:
            file.seek(0)
        except Exception:
            pass
        ocr_candidates = _ocr_pdf_pages(file)
        if ocr_candidates:
            results = _dedupe_and_rank(ocr_candidates)

    if len(results) > 1:
        results = _try_merge_pages(results)

    logger.info("Extracted %d primary-statement tables from PDF", len(results))
    return results


def _cluster_page_words(page) -> tuple[pd.DataFrame, float] | None:
    """Word-position clustering for a single page (no PDF re-open)."""
    try:
        words = page.extract_words(
            keep_blank_chars=True, x_tolerance=5, y_tolerance=3,
        )
    except Exception:
        return None
    if not words:
        return None

    rows_by_y: dict[int, list] = {}
    for w in words:
        y_key = round(w["top"] / 4) * 4
        rows_by_y.setdefault(y_key, []).append(w)

    sorted_ys = sorted(rows_by_y.keys())
    page_rows = [sorted(rows_by_y[y], key=lambda w: w["x0"]) for y in sorted_ys]
    if len(page_rows) < 4:
        return None

    num_x_positions = []
    for row_words in page_rows:
        for w in row_words:
            if _is_number_like(w["text"]):
                num_x_positions.append(round(w["x1"] / 10) * 10)

    if not num_x_positions:
        return None

    x_counts = Counter(num_x_positions)
    col_rights = sorted([x for x, c in x_counts.items() if c >= 2])
    if not col_rights:
        return None

    merged_cols = [col_rights[0]]
    for x in col_rights[1:]:
        if x - merged_cols[-1] > 30:
            merged_cols.append(x)
        elif x_counts.get(x, 0) > x_counts.get(merged_cols[-1], 0):
            merged_cols[-1] = x

    desc_right = merged_cols[0] - 20 if merged_cols else page.width * 0.5

    table_data = []
    for row_words in page_rows:
        desc_parts = [w["text"] for w in row_words if w["x0"] < desc_right]
        desc = " ".join(desc_parts).strip()

        num_values = [""] * len(merged_cols)
        for w in row_words:
            if w["x0"] >= desc_right - 5:
                best_col = min(
                    range(len(merged_cols)),
                    key=lambda c: abs(w["x1"] - merged_cols[c]),
                )
                existing = num_values[best_col]
                num_values[best_col] = (
                    (existing + " " + w["text"]).strip() if existing else w["text"]
                )

        if desc or any(v for v in num_values):
            table_data.append([desc] + num_values)

    if len(table_data) < 3:
        return None

    df = pd.DataFrame(table_data).fillna("")
    score = _score_table(df)
    if score <= 15:
        return None
    return df, score


# ---------------------------------------------------------------------------
# Word (.docx) parsing
# ---------------------------------------------------------------------------

def extract_tables_from_docx(file) -> list[pd.DataFrame]:
    doc = Document(file)
    tables = []

    for table in doc.tables:
        data = []
        for row in table.rows:
            data.append([cell.text.strip() for cell in row.cells])
        if len(data) < 2:
            continue
        df = pd.DataFrame(data).fillna("")
        score = _score_table(df)
        if score > 10:
            std = _standardise_table(df)
            if not std.empty and len(std) >= 2:
                tables.append((std, score))

    if not tables:
        para_tables = _parse_docx_paragraphs(doc)
        tables.extend(para_tables)

    tables.sort(key=lambda x: x[1], reverse=True)
    return [df for df, _ in tables]


def _parse_docx_paragraphs(doc: Document) -> list[tuple[pd.DataFrame, float]]:
    rows = []
    for para in doc.paragraphs:
        row = _parse_financial_line(para.text)
        if row:
            rows.append(row)

    if len(rows) >= 3:
        df = pd.DataFrame(rows).fillna(0)
        return [(df, 20)]
    return []
