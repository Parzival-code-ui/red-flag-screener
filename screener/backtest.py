"""Would the screener have flagged known blow-ups before they happened?

Blow-ups are scored on the last annual numbers public before the event (`test_fy`).
Controls are current Nifty 50 non-financials scored over the same span of years.
Note the survivorship bias: controls are today's survivors, so they look cleaner than
a random large-cap would have looked at the time.
"""
from __future__ import annotations

import pandas as pd

from .flags import FLAG_KEYS
from .universe import BLOWUPS, NIFTY50_NONFIN

ALERT_SCORE = 3  # score at or above this counts as "flagged"


def blowup_rows(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sym, meta in BLOWUPS.items():
        r = scored[(scored.symbol == sym) & (scored.fy == meta["test_fy"])]
        if r.empty:
            continue
        r = r.iloc[0].copy()
        r["name"], r["event"] = meta["name"], meta["event"]
        rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)


def control_rows(scored: pd.DataFrame) -> pd.DataFrame:
    fys = [m["test_fy"] for m in BLOWUPS.values()]
    c = scored[scored.symbol.isin(NIFTY50_NONFIN) & scored.fy.between(min(fys), max(fys))]
    return c[c["flags_checked"] >= 4]


def summary(scored: pd.DataFrame) -> dict:
    b, c = blowup_rows(scored), control_rows(scored)
    flag_rates = pd.DataFrame({
        "blowups": b[FLAG_KEYS].fillna(False).astype(bool).mean(),
        "nifty_controls": c[FLAG_KEYS].fillna(False).astype(bool).mean(),
    })
    return {
        "n_blowups": len(b),
        "n_control_years": len(c),
        "blowup_hit_rate": float((b.score >= ALERT_SCORE).mean()),
        "control_false_alarm_rate": float((c.score >= ALERT_SCORE).mean()),
        "blowup_avg_score": float(b.score.mean()),
        "control_avg_score": float(c.score.mean()),
        "flag_rates": flag_rates,
    }


if __name__ == "__main__":
    from .data import load_raw
    from .flags import compute

    s = compute(load_raw())
    res = summary(s)
    b = blowup_rows(s)
    print(b[["symbol", "fy", "score", "risk"]].to_string(index=False))
    for k, v in res.items():
        if k != "flag_rates":
            print(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}")
    print((res["flag_rates"] * 100).round(0))
