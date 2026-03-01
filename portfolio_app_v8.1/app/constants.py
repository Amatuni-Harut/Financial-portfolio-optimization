"""
constants.py — Константы и справочные данные приложения.

Вынесено из main.py для устранения дублирования и упрощения сопровождения.
"""

# ---------------------------------------------------------------------------
# Справочник тикеров: symbol → (company_name, sector)
# ---------------------------------------------------------------------------
TICKER_NAMES: dict[str, tuple[str, str]] = {
    # Technology
    "AAPL":  ("Apple Inc.",                  "Technology"),
    "MSFT":  ("Microsoft Corporation",        "Technology"),
    "GOOGL": ("Alphabet Inc.",                "Technology"),
    "NVDA":  ("NVIDIA Corporation",           "Technology"),
    "META":  ("Meta Platforms Inc.",          "Technology"),
    "AVGO":  ("Broadcom Inc.",               "Technology"),
    "ORCL":  ("Oracle Corporation",          "Technology"),
    "CRM":   ("Salesforce Inc.",             "Technology"),
    "ADBE":  ("Adobe Inc.",                  "Technology"),
    "INTC":  ("Intel Corporation",           "Technology"),
    # Consumer
    "AMZN":  ("Amazon.com Inc.",             "Consumer Cyclical"),
    "TSLA":  ("Tesla Inc.",                  "Consumer Cyclical"),
    "HD":    ("Home Depot Inc.",             "Consumer Cyclical"),
    "MCD":   ("McDonald's Corporation",      "Consumer Defensive"),
    "PG":    ("Procter & Gamble Co.",        "Consumer Defensive"),
    "KO":    ("Coca-Cola Company",           "Consumer Defensive"),
    "WMT":   ("Walmart Inc.",                "Consumer Defensive"),
    # Financial
    "JPM":   ("JPMorgan Chase & Co.",        "Financial Services"),
    "V":     ("Visa Inc.",                   "Financial Services"),
    "MA":    ("Mastercard Inc.",             "Financial Services"),
    "BRK-B": ("Berkshire Hathaway Inc.",     "Financial Services"),
    "BAC":   ("Bank of America Corp.",       "Financial Services"),
    "GS":    ("Goldman Sachs Group Inc.",    "Financial Services"),
    # Healthcare
    "JNJ":   ("Johnson & Johnson",           "Healthcare"),
    "UNH":   ("UnitedHealth Group Inc.",     "Healthcare"),
    "LLY":   ("Eli Lilly and Company",       "Healthcare"),
    "AMGN":  ("Amgen Inc.",                  "Healthcare"),
    "PFE":   ("Pfizer Inc.",                 "Healthcare"),
    # Energy & Industrials
    "XOM":   ("Exxon Mobil Corporation",     "Energy"),
    "CVX":   ("Chevron Corporation",         "Energy"),
    "HON":   ("Honeywell International",     "Industrials"),
    "CAT":   ("Caterpillar Inc.",            "Industrials"),
    "BA":    ("Boeing Company",              "Industrials"),
}

# ---------------------------------------------------------------------------
# Список тикеров по умолчанию (fallback когда БД недоступна)
# ---------------------------------------------------------------------------
FALLBACK_TICKERS: list[str] = list(TICKER_NAMES.keys())

# ---------------------------------------------------------------------------
# Базовый набор для bootstrap при первом запуске
# ---------------------------------------------------------------------------
BOOTSTRAP_TICKERS: list[str] = FALLBACK_TICKERS.copy()
