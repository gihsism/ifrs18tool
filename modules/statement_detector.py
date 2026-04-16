"""Auto-detect statement type from uploaded financial data.

Strategy: score the ENTIRE table against known patterns for each statement type,
then classify individual items within the detected context.
This avoids the trap of misclassifying P&L items like "Impairment of Trade
Receivables" as BS just because "receivable" appears in the name.
"""

import re
import pandas as pd
from modules.ifrs18_categories import (
    StatementType,
    IFRS18Category,
    BSCategory,
    classify_pnl_item,
    classify_bs_item,
)


# ===================================================================
# Table-level detection keywords (strong signals for each statement)
# ===================================================================

# These are items that almost exclusively appear in ONE statement type.
# We count matches across the whole table to determine what the table IS.

_PNL_SIGNALS = [
    # Very strong (long phrases beat BS keywords in per-row scoring)
    "revenue", "turnover", "cost of sales", "cost of goods sold",
    "gross profit", "operating profit", "profit before tax",
    "profit for the year", "profit for the period",
    "loss for the year", "loss for the period",
    "earnings per share", "eps", "ebitda", "ebit",
    # Strong
    "selling expense", "selling & distribution", "selling and distribution",
    "distribution cost", "marketing expense",
    "administrative expense", "admin expense", "general expense",
    "other operating income", "other operating expense",
    "finance cost", "finance income",
    "income tax expense", "tax expense", "tax benefit",
    "current income tax", "current tax", "deferred tax expense", "deferred tax benefit",
    "depreciation", "amortisation", "amortization",
    "depreciation - ppe", "depreciation of property",
    "amortisation - intangible", "amortisation of intangible",
    "impairment loss", "impairment of trade receivable",
    "impairment of goodwill", "impairment of intangible",
    "impairment of financial asset",
    "employee benefit expense", "employee benefits expense", "staff cost",
    "wages", "salaries",
    "interest income", "interest expense",
    "interest income - bank", "interest expense - bank",
    "interest expense - lease",
    "dividend income",
    "share of profit of associate", "share of profit of joint",
    "share of loss of associate", "share of loss of joint",
    "discontinued operation",
    "restructuring cost", "restructuring expense",
    "fair value gain on", "fair value loss on",
    "fair value gain on equity", "fair value gain on investment",
    "gain on disposal of investment", "loss on disposal of investment",
    "gain on disposal of investment property",
    "gain on disposal of ppe", "loss on disposal of ppe",
    "gain on disposal of subsidiary",
    "rental income from investment property",
    "rental income from investment", "rental income",
    "investment income",
    "foreign exchange gain", "foreign exchange loss",
    "foreign exchange loss on borrowing",
    "unwinding of discount",
]

_BS_SIGNALS = [
    # Very strong
    "total assets", "total liabilities", "total equity",
    "net assets", "shareholders equity", "stockholders equity",
    # Strong — asset side
    "property plant and equipment", "ppe",
    "intangible asset", "goodwill",
    "right-of-use asset",
    "investment property",
    "trade receivable", "accounts receivable",
    "trade and other receivable",
    "inventory", "inventories",
    "cash and cash equivalent",
    "prepayment", "prepaid",
    "contract asset",
    "deferred tax asset",
    # Strong — equity
    "share capital", "ordinary share", "common stock",
    "share premium", "retained earning",
    "other reserve", "revaluation reserve",
    "non-controlling interest", "minority interest",
    "treasury share",
    # Strong — liability side
    "trade payable", "accounts payable",
    "trade and other payable",
    "borrowing", "bank loan",
    "lease liabilit",
    "deferred tax liabilit",
    "provision for", "provisions",
    "pension liabilit", "defined benefit obligation",
    "contract liabilit", "deferred revenue",
    "accrued expense", "accrual",
    "current portion of",
    "bond payable", "debenture",
    "dividend payable",
]

_CF_SIGNALS = [
    # Very strong
    "cash flow from operating", "cash from operating",
    "cash flow from investing", "cash from investing",
    "cash flow from financing", "cash from financing",
    "net cash from", "net cash used in",
    "net increase in cash", "net decrease in cash",
    "cash at beginning", "cash at end",
    "cash and cash equivalents at",
    # Strong
    "operating activities", "investing activities", "financing activities",
    "purchase of ppe", "purchase of property",
    "proceeds from disposal", "proceeds from sale of",
    "proceeds from borrowing", "repayment of borrowing",
    "payment of lease", "lease payment",
    "dividends paid", "interest paid", "interest received",
    "dividends received", "tax paid", "income tax paid",
    "proceeds from issue of share",
    "acquisition of subsidiary",
    "purchase of investment",
    "changes in working capital",
    "adjustments for",
    "depreciation and amortisation",  # in CF context
]


def _count_signals(accounts: list[str], signal_list: list[str]) -> int:
    """Count how many items match signals from the list."""
    count = 0
    for acct in accounts:
        acct_lower = acct.lower()
        for signal in signal_list:
            if signal in acct_lower:
                count += 1
                break  # count each account only once per statement type
    return count


def detect_table_type(df: pd.DataFrame) -> dict[str, float]:
    """Score a table against each statement type.

    Returns dict of {"Profit or Loss": score, "Balance Sheet": score, "Cash Flow": score}.
    Score is a ratio 0-1 of how many rows match that statement type.
    """
    accounts = df.iloc[:, 0].astype(str).tolist()
    n = max(len(accounts), 1)

    pnl_count = _count_signals(accounts, _PNL_SIGNALS)
    bs_count = _count_signals(accounts, _BS_SIGNALS)
    cf_count = _count_signals(accounts, _CF_SIGNALS)

    return {
        "Profit or Loss": pnl_count / n,
        "Balance Sheet": bs_count / n,
        "Cash Flow": cf_count / n,
    }


def _score_row(acct_lower: str) -> str:
    """Score a single row against all statement types.

    Uses longest-matching-keyword as tie-breaker: if a row matches both PNL and BS
    keywords, the longest keyword match wins (more specific = better signal).
    """
    pnl_score = 0
    for s in _PNL_SIGNALS:
        if s in acct_lower:
            pnl_score = max(pnl_score, len(s))

    bs_score = 0
    for s in _BS_SIGNALS:
        if s in acct_lower:
            bs_score = max(bs_score, len(s))

    cf_score = 0
    for s in _CF_SIGNALS:
        if s in acct_lower:
            cf_score = max(cf_score, len(s))

    if cf_score > pnl_score and cf_score > bs_score:
        return "Cash Flow"
    if bs_score > pnl_score and bs_score > cf_score:
        return "Balance Sheet"
    if pnl_score > 0:
        return "Profit or Loss"

    return "Profit or Loss"  # default


def detect_and_tag(df: pd.DataFrame) -> pd.DataFrame:
    """Auto-detect statement type for each row.

    Strategy:
    1. Score the whole table — if >70% matches one type, tag ALL rows as that
       (handles the common case of a single-statement upload)
    2. Otherwise, classify each row individually using longest-keyword-match scoring
    """
    df = df.copy()
    accounts = df.iloc[:, 0].astype(str).tolist()

    scores = detect_table_type(df)
    dominant = max(scores, key=scores.get)
    dominant_score = scores[dominant]

    # Only tag everything as one type if it's very clearly a single statement
    # (70%+ match AND the runner-up is <30%)
    runner_up = sorted(scores.values(), reverse=True)[1]
    if dominant_score >= 0.60 and runner_up < 0.40:
        df["Statement"] = dominant
    else:
        # Mixed data or unclear — classify each row
        df["Statement"] = [_score_row(a.lower()) for a in accounts]

    return df


def auto_classify(df: pd.DataFrame, entity_type: str = "General (non-financial)") -> pd.DataFrame:
    """Full pipeline: detect statement type, then classify into categories.

    Returns df with columns: Account, amounts..., Statement, Category
    """
    df = detect_and_tag(df)

    categories = []
    for _, row in df.iterrows():
        stmt = row["Statement"]
        acct = str(row.iloc[0])

        if stmt == "Profit or Loss":
            categories.append(classify_pnl_item(acct, entity_type).value)
        elif stmt == "Balance Sheet":
            categories.append(classify_bs_item(acct).value)
        elif stmt == "Cash Flow":
            # CF items: classify as Operating/Investing/Financing activity
            categories.append(_classify_cf_item(acct))
        else:
            categories.append("Unclassified")

    df["Category"] = categories
    return df


def _classify_cf_item(description: str) -> str:
    """Classify a cash flow line item into activity type."""
    d = description.lower()

    cf_financing = [
        "proceeds from borrowing", "repayment of borrowing",
        "payment of lease", "lease payment",
        "dividends paid", "interest paid",
        "proceeds from issue", "share buyback",
        "financing activities",
    ]
    cf_investing = [
        "purchase of ppe", "purchase of property", "purchase of equipment",
        "purchase of intangible", "purchase of investment",
        "proceeds from disposal", "proceeds from sale",
        "acquisition of subsidiary", "disposal of subsidiary",
        "interest received", "dividends received",
        "investing activities",
    ]
    cf_operating = [
        "operating activities", "operating profit",
        "adjustments for", "changes in working capital",
        "depreciation", "amortisation", "amortization",
        "impairment", "tax paid", "income tax paid",
        "changes in trade", "changes in inventor",
        "changes in payable", "changes in receivable",
        "cash from operation", "cash generated",
        "share-based payment",
    ]

    for kw in cf_financing:
        if kw in d:
            return "CF - Financing"
    for kw in cf_investing:
        if kw in d:
            return "CF - Investing"
    for kw in cf_operating:
        if kw in d:
            return "CF - Operating"

    return "CF - Operating"  # default
