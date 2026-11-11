"""Load raw screener.in extracts (JSON lines) into a tidy company-year DataFrame."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# field key -> meaning (all ₹ crore unless noted)
FIELDS = {
    "sales": "Sales / revenue", "op": "Operating profit (EBITDA)", "oi": "Other income",
    "int": "Interest", "dep": "Depreciation", "pbt": "Profit before tax", "np": "Net profit",
    "eq": "Equity capital", "res": "Reserves", "bor": "Borrowings",
    "ol": "Other liabilities", "ta": "Total assets", "fa": "Fixed assets (net block)",
    "oa": "Other assets (≈ current assets)", "cfo": "Cash from operations",
    "rec": "Trade receivables", "cash": "Cash & equivalents",
    "nci": "Non-controlling interest", "mat": "Material cost (% of sales)",
    "prom": "Promoter holding (%)",
}

_EMPTY = re.compile(r"(?<=[\[,])(?=[,\]])")


def _parse_line(line: str) -> dict:
    # The browser extractor drops nulls as bare commas ("[,,3]"); restore them.
    return json.loads(_EMPTY.sub("null", line))


def fiscal_year(label: str) -> int:
    """'Mar2018' -> 2018, 'Dec2015' -> 2015, 'Jun2015' -> 2015."""
    m = re.match(r"^[A-Za-z]{3}\s?(\d{4})$", label.strip())
    if not m:
        raise ValueError(f"bad period label {label!r}")
    return int(m.group(1))


def load_raw(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read every *.jsonl in raw_dir. Later files override earlier ones per symbol."""
    records: dict[str, dict] = {}
    for path in sorted(raw_dir.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                rec = _parse_line(line)
                if "f" in rec:
                    records[rec["s"]] = rec
    rows = []
    for sym, rec in records.items():
        basis = "consolidated" if rec.get("b") == "c" else "standalone"
        for i, label in enumerate(rec["y"]):
            row = {"symbol": sym, "period": label, "fy": fiscal_year(label), "basis": basis}
            for k in FIELDS:
                vals = rec["f"].get(k) or []
                row[k] = vals[i] if i < len(vals) else None
            rows.append(row)
    df = pd.DataFrame(rows)
    # A 15-month transition year can produce two labels in one FY; keep the later one.
    df = df.drop_duplicates(["symbol", "fy"], keep="last")
    for k in FIELDS:
        df[k] = pd.to_numeric(df[k], errors="coerce")
    return df.sort_values(["symbol", "fy"]).reset_index(drop=True)
