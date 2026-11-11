"""Company universe: Nifty 50 non-financials + known Indian blow-ups for backtesting."""

# Nifty 50 constituents as listed on screener.in (Nov 2026), excluding banks, NBFCs,
# insurers and exchanges (HDFCBANK, ICICIBANK, SBIN, BAJFINANCE, KOTAKBANK, AXISBANK,
# BAJAJFINSV, SHRIRAMFIN, SBILIFE, HDFCLIFE, BSE, JIOFIN) – their balance sheets
# need a different rulebook (NPAs, provisioning, capital adequacy).
NIFTY50_NONFIN = {
    "RELIANCE": "Reliance Industries", "BHARTIARTL": "Bharti Airtel", "TCS": "TCS",
    "LT": "Larsen & Toubro", "HINDUNILVR": "Hindustan Unilever", "INFY": "Infosys",
    "SUNPHARMA": "Sun Pharma", "TITAN": "Titan Company", "ADANIPORTS": "Adani Ports",
    "M&M": "Mahindra & Mahindra", "MARUTI": "Maruti Suzuki", "HCLTECH": "HCL Technologies",
    "ADANIENT": "Adani Enterprises", "ULTRACEMCO": "UltraTech Cement", "ITC": "ITC",
    "ETERNAL": "Eternal (Zomato)", "JSWSTEEL": "JSW Steel", "NTPC": "NTPC",
    "BAJAJ-AUTO": "Bajaj Auto", "ONGC": "ONGC", "BEL": "Bharat Electronics",
    "COALINDIA": "Coal India", "NESTLEIND": "Nestle India", "ASIANPAINT": "Asian Paints",
    "POWERGRID": "Power Grid", "TATASTEEL": "Tata Steel", "INDIGO": "InterGlobe Aviation",
    "HINDALCO": "Hindalco", "GRASIM": "Grasim", "EICHERMOT": "Eicher Motors",
    "TECHM": "Tech Mahindra", "TRENT": "Trent", "APOLLOHOSP": "Apollo Hospitals",
    "DRREDDY": "Dr Reddy's Labs", "CIPLA": "Cipla", "TMPV": "Tata Motors PV",
    "TATACONSUM": "Tata Consumer", "MAXHEALTH": "Max Healthcare",
}

# Consolidated numbers for these are distorted by a lending arm (or, for Nestle,
# consolidated history is too short), so standalone statements are used.
FORCE_STANDALONE = {"GRASIM", "M&M", "LT", "BAJAJ-AUTO", "NESTLEIND"}

# Known blow-ups. `test_fy` is the last fiscal year whose annual numbers were public
# *before* the event, so the backtest only uses information available at the time.
BLOWUPS = {
    "MANPASAND":  {"name": "Manpasand Beverages", "test_fy": 2018, "event": "May 2019 – auditor resigned, GST fraud probe"},
    "VAKRANGEE":  {"name": "Vakrangee",           "test_fy": 2017, "event": "Jan 2018 – auditor exit, stock fell ~90%"},
    "COFFEEDAY":  {"name": "Coffee Day Enterprises", "test_fy": 2018, "event": "Jul 2019 – founder's death, ₹2,000 Cr+ diversion found"},
    "ZEEL":       {"name": "Zee Entertainment",   "test_fy": 2018, "event": "Jan 2019 – promoter pledge crisis"},
    "JETAIRWAYS": {"name": "Jet Airways",         "test_fy": 2018, "event": "Apr 2019 – grounded, insolvency"},
    "SINTEX":     {"name": "Sintex Industries",   "test_fy": 2018, "event": "2019 – loan defaults, insolvency"},
    "BCG":        {"name": "Brightcom Group",     "test_fy": 2022, "event": "Aug 2023 – SEBI order on misstated accounts"},
    "GENSOL":     {"name": "Gensol Engineering",  "test_fy": 2024, "event": "Apr 2025 – SEBI order on fund diversion"},
    "COX&KINGS":  {"name": "Cox & Kings",         "test_fy": 2018, "event": "Jun 2019 – loan defaults, fraud probe"},
    "KWALITY":    {"name": "Kwality Ltd",         "test_fy": 2017, "event": "2018 – bank fraud, insolvency"},
    "GITANJALI":  {"name": "Gitanjali Gems",      "test_fy": 2017, "event": "Feb 2018 – PNB fraud"},
    "RCOM":       {"name": "Reliance Communications", "test_fy": 2016, "event": "2017 – debt crisis, insolvency"},
}

ALL_SYMBOLS = list(NIFTY50_NONFIN) + list(BLOWUPS)


def display_name(sym: str) -> str:
    if sym in NIFTY50_NONFIN:
        return NIFTY50_NONFIN[sym]
    if sym in BLOWUPS:
        return BLOWUPS[sym]["name"]
    return sym
