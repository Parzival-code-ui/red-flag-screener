"""Refresh data/raw from screener.in public company pages.

Run on your own machine (needs internet):

    python -m screener.fetch                 # whole universe
    python -m screener.fetch TCS INFY        # just these symbols

Writes data/raw/fetched.jsonl, which overrides the bundled snapshot files.
Be polite: one request every ~1.5 s. For personal/academic use only.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .universe import ALL_SYMBOLS, FORCE_STANDALONE

BASE = "https://www.screener.in"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "fetched.jsonl"
HEADERS = {"User-Agent": "Mozilla/5.0 (red-flag-screener; academic project)"}
PERIOD = re.compile(r"^[A-Z][a-z]{2} \d{4}$")
DELAY = 1.5


def num(text):
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    t = re.sub(r"[,%₹\s]", "", str(text))
    if t in ("", "-"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_table(table) -> tuple[list[str], dict[str, dict[str, float | None]]]:
    if table is None:
        return [], {}
    cols = [th.get_text("\n", strip=True).split("\n")[0].strip()
            for th in table.select("thead th")][1:]
    rows = {}
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        key = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True).replace("+", "")).strip()
        rows[key] = {cols[i]: num(c.get_text(strip=True)) for i, c in enumerate(cells[1:]) if i < len(cols)}
    return cols, rows


def _pick(rows, pattern, years, as_int=True):
    key = next((k for k in rows if re.match(pattern, k)), None)
    out = []
    for y in years:
        v = num(rows[key].get(y)) if key else None
        out.append(None if v is None else (round(v) if as_int else round(v, 2)))
    return out


def extract(html: str, schedules: dict[str, dict], years_limit: int = 12) -> dict | None:
    """Parse one company page (plus schedule JSON) into the compact record format."""
    soup = BeautifulSoup(html, "html.parser")
    cols, pl = parse_table(soup.select_one("#profit-loss table.data-table"))
    years = [c for c in cols if PERIOD.match(c)][-years_limit:]
    if len(years) < 3:
        return None
    _, bs = parse_table(soup.select_one("#balance-sheet table.data-table"))
    _, cf = parse_table(soup.select_one("#cash-flow table.data-table"))
    shp_table = soup.select_one("#yearly-shp table") or soup.select_one("#quarterly-shp table")
    _, shp = parse_table(shp_table)
    oa, ol, ex = (schedules.get(k, {}) for k in ("oa", "ol", "ex"))
    prom_key = next((k for k in shp if k.startswith("Promoters")), None)
    f = {
        "sales": _pick(pl, r"^(Sales|Revenue)", years), "op": _pick(pl, r"^Operating Profit", years),
        "oi": _pick(pl, r"^Other Income", years), "int": _pick(pl, r"^Interest", years),
        "dep": _pick(pl, r"^Depreciation", years), "pbt": _pick(pl, r"^Profit before tax", years),
        "np": _pick(pl, r"^Net Profit", years),
        "eq": _pick(bs, r"^Equity Capital", years), "res": _pick(bs, r"^Reserves", years),
        "bor": _pick(bs, r"^Borrowings", years), "ol": _pick(bs, r"^Other Liabilities", years),
        "ta": _pick(bs, r"^Total Assets", years), "fa": _pick(bs, r"^Fixed Assets", years),
        "oa": _pick(bs, r"^Other Assets", years),
        "cfo": _pick(cf, r"^Cash from Operating", years),
        "rec": _pick(oa, r"^Trade receiv", years), "cash": _pick(oa, r"^Cash Equiv", years),
        "nci": _pick(ol, r"^Non controlling", years),
        "mat": _pick(ex, r"^Material Cost", years, as_int=False),
        "prom": [num(shp[prom_key].get(y)) if prom_key else None for y in years],
    }
    return {"y": [y.replace(" ", "") for y in years], "f": f}


def fetch_symbol(session: requests.Session, sym: str) -> dict:
    variants = [""] if sym in FORCE_STANDALONE else ["consolidated/", ""]
    for variant in variants:
        url = f"{BASE}/company/{quote(sym)}/{variant}"
        r = session.get(url, timeout=30)
        time.sleep(DELAY)
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        node = soup.select_one("[data-company-id]")
        schedules = {}
        if node:
            cid = node["data-company-id"]
            for key, parent, section in [("oa", "Other Assets", "balance-sheet"),
                                         ("ol", "Other Liabilities", "balance-sheet"),
                                         ("ex", "Expenses", "profit-loss")]:
                params = {"parent": parent, "section": section}
                if variant:
                    params["consolidated"] = ""
                try:
                    j = session.get(f"{BASE}/api/company/{cid}/schedules/", params=params, timeout=30)
                    schedules[key] = j.json() if j.ok else {}
                except (requests.RequestException, ValueError):
                    schedules[key] = {}
                time.sleep(DELAY / 2)
        rec = extract(r.text, schedules)
        if rec is None or (variant and len(rec["y"]) < 6):
            continue  # too little consolidated history -> try standalone
        return {"s": sym, "b": "c" if variant else "s", **rec}
    return {"s": sym, "err": "not found or no data"}


def main(symbols: list[str]) -> None:
    session = requests.Session()
    session.headers.update(HEADERS)
    ok = 0
    with OUT.open("w") as fh:
        for i, sym in enumerate(symbols, 1):
            try:
                rec = fetch_symbol(session, sym)
            except requests.RequestException as e:
                rec = {"s": sym, "err": str(e)}
            status = rec.get("err") or f"{len(rec['y'])} years ({'consolidated' if rec['b'] == 'c' else 'standalone'})"
            print(f"[{i}/{len(symbols)}] {sym}: {status}")
            if "err" not in rec:
                fh.write(json.dumps(rec) + "\n")
                ok += 1
    print(f"Saved {ok} companies to {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:] or ALL_SYMBOLS)
