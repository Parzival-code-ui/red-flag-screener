"""Build a self-contained HTML version of the dashboard: dist/index.html

    python scripts/export_static.py

All scoring runs here in Python; the page only displays the results, so it can be
hosted anywhere (no server, no Python) and opened on a phone.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from screener.backtest import ALERT_SCORE, blowup_rows, summary  # noqa: E402
from screener.data import load_raw  # noqa: E402
from screener.flags import (ALTMAN_DISTRESS, BENEISH_THRESHOLD, FLAG_KEYS, FLAGS,  # noqa: E402
                            MAX_SCORE, compute)
from screener.universe import BLOWUPS, NIFTY50_NONFIN, display_name  # noqa: E402

METRICS = ["cfo_to_pat_3y", "cfo_to_pat_5y", "beneish_m", "altman_z", "promoter_change_2y",
           "debtor_days", "debt_to_assets", "interest_cover", "other_income_share",
           "np", "cfo", "sales", "bor", "rec"]


def clean(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float):
        return round(v, 3)
    return v


def flag_val(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return bool(v)


def build() -> dict:
    s = compute(load_raw())
    companies = []
    for sym, g in s.groupby("symbol"):
        g = g.sort_values("fy")
        companies.append({
            "symbol": sym, "name": display_name(sym), "basis": g.basis.iloc[0],
            "nifty": sym in NIFTY50_NONFIN,
            "blowup": BLOWUPS.get(sym),
            "years": [{
                "fy": int(r.fy), "score": int(r.score),
                "risk": None if str(r.risk) == "nan" else str(r.risk),
                "flags": {k: flag_val(r[k]) for k in FLAG_KEYS},
                **{m: clean(r[m]) for m in METRICS},
            } for _, r in g.iterrows()],
        })
    res = summary(s)
    rates = res.pop("flag_rates")
    b = blowup_rows(s)
    return {
        "maxScore": MAX_SCORE, "alertScore": ALERT_SCORE,
        "beneishThreshold": BENEISH_THRESHOLD, "altmanDistress": ALTMAN_DISTRESS,
        "flags": [{"key": f.key, "label": f.label, "weight": f.weight, "why": f.why} for f in FLAGS],
        "companies": companies,
        "backtest": {
            **{k: clean(v) for k, v in res.items()},
            "rows": [{"symbol": r.symbol, "fy": int(r.fy), "score": int(r.score)} for _, r in b.iterrows()],
            "rates": {k: {"blowups": clean(rates.loc[k, "blowups"]),
                          "controls": clean(rates.loc[k, "nifty_controls"])} for k in FLAG_KEYS},
        },
    }


def main() -> None:
    data = json.dumps(build(), separators=(",", ":"), ensure_ascii=False)
    template = (ROOT / "web" / "template.html").read_text()
    out = ROOT / "dist" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(template.replace("/*__DATA__*/null", data))
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
