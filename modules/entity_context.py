"""Entity context — auto-extracted from the uploaded FS, then confirmed by the user.

Powers better IFRS 18 classification. Everything we can detect from the uploaded
data gets pre-filled; the user only edits what we got wrong or what isn't in
the FS at all.

Stored in `st.session_state["entity_context"]` as a flat dict so every
downstream step (classification, P&L, BS, CF, transition disclosures) can read
the same answers.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Field schema
# ---------------------------------------------------------------------------

CURRENCIES = [
    "EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK",
    "CZK", "PLN", "HUF", "RON", "BGN", "HRK", "TRY", "RUB", "CNY", "HKD",
    "SGD", "INR", "BRL", "MXN", "ZAR", "AED", "SAR", "Other",
]


DEFAULTS: dict[str, Any] = {
    # Headline: what kind of entity this is — drives Operating reclassification
    # for interest, dividends, rent, FV gains, etc.
    "main_activity": "General (non-financial)",
    "activity_description": "",

    # Judgement flags the classifier needs
    "invests_in_property": False,
    "lends_as_side_activity": False,
    "has_discontinued_operations": False,
    "uses_equity_method": False,
    "has_mpms": False,

    # Reporting conventions
    "presentation_currency": "EUR",
    "functional_currency": "EUR",
    "reporting_period_end": "",
    "prior_period_label": "",
    "current_period_label": "",
    "expense_presentation": "By nature",  # "By function" | "By nature" | "Mixed"
}


# ---------------------------------------------------------------------------
# FS-based auto-detection
# ---------------------------------------------------------------------------

_CURRENCY_PATTERNS = {
    "EUR": [r"€", r"\beur\b", r"euro"],
    "USD": [r"\$", r"\busd\b", r"US dollar"],
    "GBP": [r"£", r"\bgbp\b", r"sterling", r"pound"],
    "CHF": [r"\bchf\b", r"swiss franc"],
    "JPY": [r"¥", r"\bjpy\b", r"yen"],
    "SEK": [r"\bsek\b"],
    "CNY": [r"\bcny\b", r"\brmb\b", r"renminbi", r"yuan"],
}


def _detect_currency(df: pd.DataFrame) -> str | None:
    """Peek at column headers + account labels for currency hints."""
    haystack = " ".join(str(c) for c in df.columns).lower()
    haystack += " " + " ".join(df.iloc[:, 0].astype(str).tolist()).lower()
    for code, patterns in _CURRENCY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, haystack, flags=re.IGNORECASE):
                return code
    return None


_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _detect_periods(df: pd.DataFrame) -> tuple[str, str, str]:
    """Extract (current_period_label, prior_period_label, year_end) from columns."""
    candidates: list[str] = []
    for col in df.columns:
        s = str(col)
        if _YEAR_RE.search(s) and s.lower() != "account":
            candidates.append(s)
    current = candidates[0] if candidates else ""
    prior = candidates[1] if len(candidates) > 1 else ""

    # Guess year-end from the first amount column
    year_end = ""
    if current:
        ym = re.search(r"(?:31[\s/-]+(?:dec|december)|year ended[^,]*)(.*?)(?:20\d{2})", current, re.IGNORECASE)
        if ym:
            year_end = ym.group(0)
        else:
            year = _YEAR_RE.search(current)
            if year:
                year_end = f"31 December {year.group()}"
    return current, prior, year_end


_DISCONTINUED_RE = re.compile(r"discontinued operation", re.IGNORECASE)
_ASSOCIATE_RE = re.compile(r"(share of (profit|loss).*(associate|joint venture)|equity method)", re.IGNORECASE)
_INVESTMENT_PROP_RE = re.compile(r"investment propert", re.IGNORECASE)
_INTEREST_INCOME_RE = re.compile(r"interest income", re.IGNORECASE)

# P&L row labels that only appear in "by function" presentation
_FUNCTION_LABELS = [
    "cost of sales", "cost of goods sold",
    "selling.*expense", "selling.*distribution",
    "administrative expense", "admin expense", "general.*expense",
    "gross profit",
]
# Labels that only appear in "by nature" presentation
_NATURE_LABELS = [
    "employee benefit", "staff cost", "wages and salaries",
    "raw materials", "changes in inventor",
    "depreciation.*amortis",
]


def _detect_expense_presentation(pnl: pd.DataFrame) -> str:
    if pnl.empty:
        return "By nature"
    labels = pnl["Account"].astype(str).str.lower().tolist() if "Account" in pnl.columns else []
    blob = " | ".join(labels)
    fn_hits = sum(1 for p in _FUNCTION_LABELS if re.search(p, blob, re.IGNORECASE))
    nat_hits = sum(1 for p in _NATURE_LABELS if re.search(p, blob, re.IGNORECASE))
    if fn_hits and nat_hits:
        return "Mixed"
    if fn_hits:
        return "By function"
    return "By nature"


def extract_from_fs() -> dict[str, Any]:
    """Auto-detect context fields from whatever's currently in session state.

    Never overrides user-confirmed values; only populates when we have data.
    Returns a dict with the detected fields (missing fields = couldn't tell).
    """
    detected: dict[str, Any] = {}

    all_df: pd.DataFrame | None = st.session_state.get("all_classified")
    pnl: pd.DataFrame | None = st.session_state.get("classified_pnl")
    bs: pd.DataFrame | None = st.session_state.get("classified_bs")

    # Currency — try BS header (usually cleanest), then PnL, then combined
    for df in (bs, pnl, all_df):
        if isinstance(df, pd.DataFrame) and not df.empty:
            cur = _detect_currency(df)
            if cur:
                detected["presentation_currency"] = cur
                detected["functional_currency"] = cur
                break

    # Period labels + year-end
    for df in (pnl, bs, all_df):
        if isinstance(df, pd.DataFrame) and not df.empty:
            cur_lbl, prior_lbl, y_end = _detect_periods(df)
            if cur_lbl:
                detected["current_period_label"] = cur_lbl
                detected["prior_period_label"] = prior_lbl
                detected["reporting_period_end"] = y_end
                break

    # Line-item-based flags
    if isinstance(all_df, pd.DataFrame) and not all_df.empty and "Account" in all_df.columns:
        blob = " | ".join(all_df["Account"].astype(str).tolist())
        if _DISCONTINUED_RE.search(blob):
            detected["has_discontinued_operations"] = True
        if _ASSOCIATE_RE.search(blob):
            detected["uses_equity_method"] = True
        if _INVESTMENT_PROP_RE.search(blob):
            detected["invests_in_property"] = True

    if isinstance(pnl, pd.DataFrame) and not pnl.empty:
        detected["expense_presentation"] = _detect_expense_presentation(pnl)

    # Main activity from sidebar (already selected)
    if "entity_type" in st.session_state:
        detected["main_activity"] = st.session_state["entity_type"]

    return detected


# ---------------------------------------------------------------------------
# Session-state accessors
# ---------------------------------------------------------------------------

def get_context() -> dict[str, Any]:
    """Return the merged context: defaults + auto-detected + user-confirmed."""
    ctx = dict(DEFAULTS)
    ctx.update(extract_from_fs())
    user = st.session_state.get("entity_context", {}) or {}
    ctx.update(user)
    return ctx


def set_context(values: dict[str, Any]) -> None:
    st.session_state["entity_context"] = values
    from modules.persistence import auto_save
    auto_save()


# ---------------------------------------------------------------------------
# UI: questionnaire rendered in Step 1 after upload
# ---------------------------------------------------------------------------

def render_context_form() -> None:
    """Collapsible form that lets the user review + fix the auto-detected context.

    Only shown when there's at least something loaded; otherwise silent.
    """
    if not st.session_state.get("loaded_statements"):
        return

    detected = extract_from_fs()
    saved = st.session_state.get("entity_context", {}) or {}

    def _val(field: str) -> Any:
        if field in saved:
            return saved[field]
        if field in detected:
            return detected[field]
        return DEFAULTS[field]

    # Collapsed by default if the user has already confirmed; open on first load.
    open_initially = "entity_context" not in st.session_state

    with st.expander(
        "**Entity context** — answers we'll use for classification "
        "(pre-filled from your data; confirm or adjust)",
        expanded=open_initially,
    ):
        if not saved and detected:
            detected_count = len(detected)
            st.caption(
                f"We auto-detected {detected_count} field(s) from your uploaded "
                "statements. Please review below."
            )

        with st.form("entity_context_form", clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                main_activity = st.selectbox(
                    "Main business activity",
                    ["General (non-financial)", "Banking / Lending",
                     "Insurance", "Investment Entity"],
                    index=["General (non-financial)", "Banking / Lending",
                           "Insurance", "Investment Entity"].index(
                        _val("main_activity")
                    ),
                    help="Drives which items get reclassified to Operating.",
                )
                activity_description = st.text_area(
                    "Activity description (optional)",
                    value=_val("activity_description"),
                    height=70,
                    help="Free-text note about what the entity actually does. "
                    "Useful for the classifier on edge cases.",
                )
                presentation_currency = st.selectbox(
                    "Presentation currency",
                    CURRENCIES,
                    index=CURRENCIES.index(_val("presentation_currency"))
                    if _val("presentation_currency") in CURRENCIES else 0,
                )
                functional_currency = st.selectbox(
                    "Functional currency",
                    CURRENCIES,
                    index=CURRENCIES.index(_val("functional_currency"))
                    if _val("functional_currency") in CURRENCIES else 0,
                )
                expense_presentation = st.selectbox(
                    "Expense presentation in P&L",
                    ["By function", "By nature", "Mixed"],
                    index=["By function", "By nature", "Mixed"].index(
                        _val("expense_presentation")
                    ),
                    help="IFRS 18 requires disclosing expenses by nature even "
                    "when the primary presentation is by function.",
                )

            with col2:
                reporting_period_end = st.text_input(
                    "Reporting period end",
                    value=_val("reporting_period_end"),
                    placeholder="e.g. 31 December 2025",
                )
                current_period_label = st.text_input(
                    "Current period column label",
                    value=_val("current_period_label"),
                    placeholder="e.g. FY 2025",
                )
                prior_period_label = st.text_input(
                    "Prior period column label",
                    value=_val("prior_period_label"),
                    placeholder="e.g. FY 2024",
                )

                st.markdown("**Judgement flags**")
                invests_in_property = st.checkbox(
                    "Investing in property is a main/significant activity",
                    value=_val("invests_in_property"),
                    help="If yes, rental income + FV gains on investment property "
                    "move to the Operating category.",
                )
                lends_as_side_activity = st.checkbox(
                    "Lending is a secondary activity",
                    value=_val("lends_as_side_activity"),
                    help="E.g. consumer financing by a retailer.",
                )
                has_discontinued_operations = st.checkbox(
                    "Has discontinued operations",
                    value=_val("has_discontinued_operations"),
                )
                uses_equity_method = st.checkbox(
                    "Reports associates / JVs under the equity method",
                    value=_val("uses_equity_method"),
                )
                has_mpms = st.checkbox(
                    "Presents management performance measures (MPMs)",
                    value=_val("has_mpms"),
                    help="E.g. Adjusted EBITDA, Underlying operating profit.",
                )

            submitted = st.form_submit_button("Save context", type="primary")
            if submitted:
                set_context({
                    "main_activity": main_activity,
                    "activity_description": activity_description,
                    "invests_in_property": invests_in_property,
                    "lends_as_side_activity": lends_as_side_activity,
                    "has_discontinued_operations": has_discontinued_operations,
                    "uses_equity_method": uses_equity_method,
                    "has_mpms": has_mpms,
                    "presentation_currency": presentation_currency,
                    "functional_currency": functional_currency,
                    "reporting_period_end": reporting_period_end,
                    "current_period_label": current_period_label,
                    "prior_period_label": prior_period_label,
                    "expense_presentation": expense_presentation,
                })
                # Mirror main activity into the legacy sidebar key so existing
                # classifier code keeps working unchanged.
                st.session_state["entity_type"] = main_activity
                st.success("Context saved — classification will use these values.")
