"""IFRS 18 classification categories and mapping rules.

IFRS 18 Operating / Investing / Financing categories apply ONLY to the
statement of profit or loss.  Balance sheet items are classified separately.
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Statement type
# ---------------------------------------------------------------------------

class StatementType(str, Enum):
    PNL = "Profit or Loss"
    BALANCE_SHEET = "Balance Sheet"


# ---------------------------------------------------------------------------
# IFRS 18 P&L categories (income / expense items only)
# ---------------------------------------------------------------------------

class IFRS18Category(str, Enum):
    OPERATING = "Operating"
    INVESTING = "Investing"
    FINANCING = "Financing"
    INCOME_TAX = "Income Tax"
    DISCONTINUED = "Discontinued Operations"


# ---------------------------------------------------------------------------
# Balance sheet groupings
# ---------------------------------------------------------------------------

class BSCategory(str, Enum):
    NON_CURRENT_ASSETS = "Non-current Assets"
    CURRENT_ASSETS = "Current Assets"
    EQUITY = "Equity"
    NON_CURRENT_LIABILITIES = "Non-current Liabilities"
    CURRENT_LIABILITIES = "Current Liabilities"


# ===================================================================
# IFRS 18 P&L classification keywords
# ===================================================================

IFRS18_PNL_RULES = {
    IFRS18Category.OPERATING: [
        "revenue", "sales", "turnover", "cost of sales", "cost of goods",
        "cost of revenue",
        "gross profit", "selling", "distribution", "marketing",
        "administrative", "admin", "general expense",
        "staff cost", "employee", "personnel",
        "wages", "salaries",
        "depreciation", "amortisation", "amortization",
        "impairment", "write-down", "write-off",
        "research", "development", "r&d",
        "other operating", "operating expense", "operating income",
        "restructuring", "warranty", "bad debt",
        "expected credit loss", "ecl", "inventory write",
        "rent expense", "lease expense",
        "foreign exchange", "fx gain", "fx loss",
        "gain on disposal of ppe", "loss on disposal of ppe",
        "disposal of property",
        "pension service cost", "defined benefit service",
        "other income", "other expense",
        "insurance revenue", "insurance service",
        # German
        "umsatzerlöse", "umsatz", "herstellungskosten", "vertriebskosten",
        "verwaltungskosten", "verwaltungsaufwand", "abschreibungen",
        "personalaufwand", "wertminderung", "sonstige betriebliche",
        "forschung und entwicklung", "materialaufwand",
        # French
        "chiffre d'affaires", "produits des activités ordinaires",
        "coût des ventes", "frais de vente", "frais administratifs",
        "frais généraux", "amortissements", "dépréciation",
        "charges de personnel", "frais de recherche",
        # Italian
        "ricavi", "costo del venduto", "costi di vendita",
        "costi amministrativi", "ammortamenti", "svalutazioni",
        "costi del personale", "costi di ricerca",
    ],
    IFRS18Category.INVESTING: [
        "dividend income", "dividend received",
        "interest income", "interest received",
        "investment income", "finance income",
        "rental income",
        "fair value gain", "fair value loss",
        "gain on disposal of investment", "loss on disposal of investment",
        "gain on disposal of subsidiary",
        "share of profit", "share of loss", "equity method",
        "share of result of associates", "share of net income of associates",
        "revaluation gain", "revaluation loss",
        # German
        "zinsertrag", "zinserträge", "finanzertrag", "beteiligungsergebnis",
        "dividendenertrag", "ergebnis aus assoziierten",
        # French
        "produits financiers", "produits d'intérêts", "dividendes reçus",
        "quote-part dans le résultat",
        # Italian
        "proventi finanziari", "interessi attivi", "dividendi",
        "quota di utile",
    ],
    IFRS18Category.FINANCING: [
        "interest expense", "interest paid", "finance cost", "finance charge",
        "borrowing cost", "loan interest", "bond interest",
        "lease interest", "interest on lease liabilit", "unwinding of discount",
        "fair value change on financial liabilit",
        "bank charge", "commitment fee",
        "net interest on defined benefit",
        "exchange difference on borrowing",
        "exchange loss on borrowing", "exchange gain on borrowing",
        "fx on debt", "fx on loan",
        "foreign exchange loss on borrowing", "foreign exchange gain on borrowing",
        # German
        "zinsaufwand", "zinsaufwendungen", "finanzaufwand",
        "finanzierungsaufwand", "fremdkapitalkosten",
        # French
        "charges financières", "charges d'intérêts", "coût de l'endettement",
        # Italian
        "oneri finanziari", "interessi passivi",
    ],
    IFRS18Category.INCOME_TAX: [
        "income tax", "tax expense", "tax benefit",
        "current tax", "deferred tax",
        "withholding tax",
        # German
        "ertragssteuern", "ertragsteuern", "steueraufwand", "latente steuern",
        # French
        "impôts sur le résultat", "impôt sur les bénéfices",
        "impôts différés", "charge d'impôt",
        # Italian
        "imposte sul reddito", "imposte correnti", "imposte differite",
    ],
    IFRS18Category.DISCONTINUED: [
        "discontinued", "held for sale",
        # German
        "aufgegebene geschäftsbereiche", "zur veräusserung gehalten",
        "zur veräußerung gehalten",
        # French
        "activités abandonnées",
        # Italian
        "attività operative cessate", "attività cessate",
    ],
}

# Keywords that match a description but don't really pin down the category —
# a supporting note (when one is referenced) is allowed to override these.
WEAK_PNL_KEYWORDS = {
    "other income", "other expense",
}

# For financial entities, these keywords reclassify to Operating
FINANCIAL_ENTITY_OVERRIDES = {
    "Banking / Lending": [
        "interest income", "interest expense", "loan interest",
        "net interest", "fee income", "commission income",
        "trading income", "trading loss",
        "fair value change on financial",
        "expected credit loss", "ecl",
    ],
    "Insurance": [
        "insurance revenue", "insurance service",
        "net insurance", "reinsurance",
        "investment income",
    ],
    "Investment Entity": [
        "dividend income", "interest income",
        "fair value gain", "fair value loss",
        "investment income", "rental income",
        "gain on disposal of investment",
        "loss on disposal of investment",
    ],
}


# ===================================================================
# BS classification keywords
# ===================================================================

BS_CLASSIFICATION_RULES = {
    BSCategory.NON_CURRENT_ASSETS: [
        "property plant", "ppe", "land and building",
        "intangible", "goodwill", "software",
        "investment property", "right-of-use", "rou asset",
        "biological asset",
        "deferred tax asset",
        "long-term investment", "equity investment",
        "investment in associate", "investment in joint venture",
        "financial asset",
    ],
    BSCategory.CURRENT_ASSETS: [
        "inventory", "inventories", "stock",
        "trade receivable", "accounts receivable",
        "other receivable", "loan receivable",
        "prepayment", "prepaid", "advance",
        "contract asset",
        "cash", "bank balance", "term deposit",
        "short-term investment",
        "tax receivable", "tax refund",
    ],
    BSCategory.EQUITY: [
        "share capital", "ordinary share", "common stock",
        "share premium", "additional paid-in",
        "retained earning", "accumulated profit", "accumulated loss",
        "reserve", "revaluation reserve", "hedging reserve",
        "translation reserve", "other comprehensive",
        "oci", "treasury",
        "non-controlling interest", "minority interest",
    ],
    BSCategory.NON_CURRENT_LIABILITIES: [
        "long-term borrowing", "bond payable", "debenture",
        "lease liabilit",
        "deferred tax liabilit",
        "pension liabilit", "defined benefit liabilit",
        "defined benefit obligation",
        "long-term payable", "other non-current liabilit",
        "provision", "provisions",
    ],
    BSCategory.CURRENT_LIABILITIES: [
        "trade payable", "accounts payable",
        "accrual", "accrued",
        "short-term borrowing", "overdraft",
        "current portion",
        "tax payable", "income tax payable",
        "contract liabilit", "deferred revenue", "unearned revenue",
        "dividend payable",
        "other payable", "other current liabilit",
    ],
}


# ===================================================================
# Classification functions
# ===================================================================

# Scan order for length ties: the more specific (non-operating) category wins.
_PNL_PRIORITY = [
    IFRS18Category.DISCONTINUED,
    IFRS18Category.INCOME_TAX,
    IFRS18Category.FINANCING,
    IFRS18Category.INVESTING,
    IFRS18Category.OPERATING,
]


def _scan_pnl_keywords(
    text: str, entity_type: str,
) -> tuple[IFRS18Category | None, str]:
    """Longest-keyword match over `text`. Returns (category, keyword) or
    (None, "") when nothing matches.

    Longest-match beats the old first-match-wins scan: "net interest on
    defined benefit" (Financing) now wins over "interest income" embedded
    in a longer label, and a banking override only wins where it is
    genuinely the most specific match.
    """
    best_cat: IFRS18Category | None = None
    best_kw = ""

    # Financial entity overrides -> Operating. Scanned first so they win
    # length ties against the generic rules for the same term.
    if entity_type != "General (non-financial)":
        for keyword in FINANCIAL_ENTITY_OVERRIDES.get(entity_type, []):
            if keyword in text and len(keyword) > len(best_kw):
                best_cat, best_kw = IFRS18Category.OPERATING, keyword

    for category in _PNL_PRIORITY:
        for keyword in IFRS18_PNL_RULES.get(category, []):
            if keyword in text and len(keyword) > len(best_kw):
                best_cat, best_kw = category, keyword

    return best_cat, best_kw


def classify_pnl_item_detailed(
    description: str,
    entity_type: str = "General (non-financial)",
    note_context: str = "",
) -> tuple[IFRS18Category, str, str]:
    """Classify a P&L line item into an IFRS 18 category.

    Returns (category, matched_keyword, source) where source is
    "description", "note", or "default".

    The description is authoritative: a clearly-labelled line ("Revenue")
    keeps its category even if the supporting note happens to mention
    "interest income" in passing. `note_context` (title + first ~500 chars
    of the referenced footnote) is consulted only when the description is
    ambiguous — no keyword match, or a weak match like "Other income".
    """
    desc = description.lower().strip()
    cat, kw = _scan_pnl_keywords(desc, entity_type)

    desc_is_weak = cat is None or kw in WEAK_PNL_KEYWORDS
    if note_context and desc_is_weak:
        ctx_cat, ctx_kw = _scan_pnl_keywords(
            note_context[:500].lower(), entity_type,
        )
        if ctx_cat is not None and ctx_kw not in WEAK_PNL_KEYWORDS:
            return ctx_cat, ctx_kw, "note"

    if cat is not None:
        return cat, kw, "description"
    return IFRS18Category.OPERATING, "", "default"


def classify_pnl_item(
    description: str,
    entity_type: str = "General (non-financial)",
    note_context: str = "",
) -> IFRS18Category:
    """Classify a P&L line item into an IFRS 18 category."""
    return classify_pnl_item_detailed(description, entity_type, note_context)[0]


def classify_bs_item(description: str) -> BSCategory:
    """Classify a balance sheet line item using longest-keyword-match."""
    desc_lower = description.lower().strip()

    best_cat = None
    best_len = 0
    for category, keywords in BS_CLASSIFICATION_RULES.items():
        for keyword in keywords:
            if keyword in desc_lower and len(keyword) > best_len:
                best_cat = category
                best_len = len(keyword)

    if best_cat is not None:
        return best_cat

    # Fallback heuristics when no keyword matches
    # Check for common patterns
    if any(w in desc_lower for w in ["asset", "receivable", "prepaid", "investment"]):
        return BSCategory.NON_CURRENT_ASSETS
    if any(w in desc_lower for w in ["liability", "payable", "borrowing", "debt", "loan"]):
        return BSCategory.NON_CURRENT_LIABILITIES
    if any(w in desc_lower for w in ["capital", "reserve", "retained", "equity", "surplus"]):
        return BSCategory.EQUITY

    # Last resort — return non-current assets (safer than current assets for unknowns)
    return BSCategory.NON_CURRENT_ASSETS
