"""Accounting red-flag metrics and scoring.

Every metric is computed per company-year using only that year and earlier years,
so a score for FY2018 uses nothing published after the FY2018 annual report.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Flag:
    key: str
    label: str
    weight: int
    why: str


FLAGS = [
    Flag("f_cash_conversion", "Profits not turning into cash", 2,
         "Operating cash flow over the last 3 or 5 years is under half of net profit. Reported "
         "profit that never shows up as cash is the most common sign of aggressive accounting."),
    Flag("f_receivables", "Receivables growing faster than sales", 1,
         "Receivables as a share of sales rose 30%+ over two years and debtor days exceed 60. "
         "Booking sales that customers haven't paid for inflates revenue."),
    Flag("f_beneish", "Beneish M-Score above -1.78", 2,
         "The 8-variable Beneish model puts the company in the 'likely manipulator' zone."),
    Flag("f_altman", "Altman Z'' in distress zone", 2,
         "Emerging-market Altman Z'' below 1.1 means a weak balance sheet and higher "
         "probability of financial distress."),
    Flag("f_promoter", "Promoter stake falling sharply", 2,
         "Promoter holding fell 5+ percentage points in two years — often pledged shares being "
         "invoked or promoters selling out."),
    Flag("f_debt_funded_receivables", "Debt-funded receivables", 1,
         "Receivables are over 30% of total assets and borrowings over 30% too — the company is "
         "borrowing to carry customers who haven't paid."),
    Flag("f_debt_growth", "Debt surging despite 'profits'", 1,
         "Borrowings up 50%+ in two years while operating cash covers less than 80% of profit."),
    Flag("f_cash_and_debt", "Lots of cash and lots of debt", 1,
         "Cash is over 10% of assets while borrowings are over 30% — why borrow at high rates "
         "if the cash is really there?"),
    Flag("f_other_income", "Leaning on other income", 1,
         "Other income is over 30% of profit before tax, so the core business earns less "
         "than the headline suggests."),
    Flag("f_interest_cover", "Weak interest cover", 1,
         "EBIT covers interest less than 1.5 times."),
]
FLAG_KEYS = [f.key for f in FLAGS]
MAX_SCORE = sum(f.weight for f in FLAGS)

BENEISH_THRESHOLD = -1.78
ALTMAN_DISTRESS = 1.1
ALTMAN_SAFE = 2.6


def _safe_div(a, b):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = a / b
    return out.where((b != 0) & b.notna() & a.notna())


def _clip(s, lo=0.0, hi=5.0):
    return s.clip(lower=lo, upper=hi)


def _metrics_one(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("fy").copy()
    prev = g.shift(1)
    prev2 = g.shift(2)

    nci = g["nci"].fillna(0)
    networth = g["eq"].fillna(0) + g["res"].fillna(0)
    total_liab = g["ta"] - networth
    cur_liab = (g["ol"] - nci)  # Screener's "other liabilities" ≈ current liabilities + NCI

    # --- cash conversion (3y rolling) ---
    np3 = g["np"].rolling(3, min_periods=3).sum()
    cfo3 = g["cfo"].rolling(3, min_periods=3).sum()
    g["cfo_to_pat_3y"] = _safe_div(cfo3, np3).where(np3 > 0)
    np5 = g["np"].rolling(5, min_periods=4).sum()
    cfo5 = g["cfo"].rolling(5, min_periods=4).sum()
    g["cfo_to_pat_5y"] = _safe_div(cfo5, np5).where(np5 > 0)

    # --- receivables ---
    g["debtor_days"] = _safe_div(g["rec"] * 365, g["sales"])
    rec_ratio = _safe_div(g["rec"], g["sales"])
    rec_ratio_2y = _safe_div(prev2["rec"], prev2["sales"])
    g["rec_ratio_change_2y"] = _safe_div(rec_ratio, rec_ratio_2y) - 1

    # --- Beneish 8-variable M-score (SGAI set to 1: SG&A not available) ---
    mat = g["mat"].where(g["mat"].between(5, 100))
    gm = (1 - mat / 100).fillna(_safe_div(g["op"], g["sales"]))
    gm_prev = gm.shift(1)
    dsri = _safe_div(_safe_div(g["rec"], g["sales"]), _safe_div(prev["rec"], prev["sales"]))
    gmi = _safe_div(gm_prev, gm).where((gm > 0) & (gm_prev > 0))
    aq = 1 - _safe_div(g["oa"] + g["fa"], g["ta"])
    aqi = _safe_div(aq, aq.shift(1)).where(aq.shift(1) > 0.01)
    sgi = _safe_div(g["sales"], prev["sales"])
    dr = _safe_div(g["dep"], g["dep"] + g["fa"])
    depi = _safe_div(dr.shift(1), dr)
    lev = _safe_div(g["bor"].fillna(0) + g["ol"], g["ta"])
    lvgi = _safe_div(lev, lev.shift(1))
    tata = _safe_div(g["np"] - g["cfo"], g["ta"])
    comps = {"dsri": dsri, "gmi": gmi, "aqi": aqi, "sgi": sgi, "depi": depi, "lvgi": lvgi}
    for k, v in comps.items():
        g[f"b_{k}"] = _clip(v)
    g["b_tata"] = tata.clip(-1, 1)
    # Missing components default to the neutral value 1 (or 0 for TATA).
    filled = {k: g[f"b_{k}"].fillna(1.0) for k in comps}
    g["beneish_m"] = (
        -4.84 + 0.92 * filled["dsri"] + 0.528 * filled["gmi"] + 0.404 * filled["aqi"]
        + 0.892 * filled["sgi"] + 0.115 * filled["depi"] - 0.172 * 1.0
        + 4.679 * g["b_tata"].fillna(0) - 0.327 * filled["lvgi"]
    )
    # Need at least sales, receivables and TATA to call the score meaningful.
    g.loc[dsri.isna() | sgi.isna() | tata.isna(), "beneish_m"] = np.nan

    # --- Altman Z'' (emerging markets, book equity) ---
    x1 = _safe_div(g["oa"] - cur_liab, g["ta"])
    x2 = _safe_div(g["res"], g["ta"])
    x3 = _safe_div(g["pbt"] + g["int"].fillna(0), g["ta"])
    x4 = _safe_div(networth, total_liab).clip(-5, 10)
    g["altman_z"] = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4

    # --- promoter holding ---
    g["promoter_change_2y"] = g["prom"] - prev2["prom"]

    # --- debt ---
    g["borrowings_growth_2y"] = _safe_div(g["bor"], prev2["bor"]) - 1
    g["debt_to_assets"] = _safe_div(g["bor"], g["ta"])
    g["cash_to_assets"] = _safe_div(g["cash"], g["ta"])
    g["receivables_to_assets"] = _safe_div(g["rec"], g["ta"])
    ebit = g["pbt"] + g["int"].fillna(0)
    g["interest_cover"] = _safe_div(ebit, g["int"]).where(g["int"] > 0)
    g["other_income_share"] = _safe_div(g["oi"], g["pbt"]).where(g["pbt"] > 0)
    return g


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """Add metric columns, flag columns (True/False/NaN), `score` and `risk` band."""
    out = pd.concat([_metrics_one(g) for _, g in df.groupby("symbol", sort=False)],
                    ignore_index=True)

    def flag(cond, *required):
        known = pd.concat([out[c].notna() for c in required], axis=1).all(axis=1)
        return cond.where(known)  # NaN when inputs are missing

    cc = pd.concat([out["cfo_to_pat_3y"] < 0.5, out["cfo_to_pat_5y"] < 0.5], axis=1).any(axis=1)
    cc_known = out["cfo_to_pat_3y"].notna() | out["cfo_to_pat_5y"].notna()
    out["f_cash_conversion"] = cc.where(cc_known)
    out["f_receivables"] = flag((out["rec_ratio_change_2y"] > 0.30) & (out["debtor_days"] > 60),
                                "rec_ratio_change_2y", "debtor_days")
    out["f_beneish"] = flag(out["beneish_m"] > BENEISH_THRESHOLD, "beneish_m")
    out["f_altman"] = flag(out["altman_z"] < ALTMAN_DISTRESS, "altman_z")
    out["f_promoter"] = flag(out["promoter_change_2y"] <= -5, "promoter_change_2y")
    out["f_debt_growth"] = flag((out["borrowings_growth_2y"] > 0.5) & (out["bor"] > 0.05 * out["ta"])
                                & (out["cfo_to_pat_3y"] < 0.8),
                                "borrowings_growth_2y", "cfo_to_pat_3y")
    out["f_cash_and_debt"] = flag((out["cash_to_assets"] > 0.10) & (out["debt_to_assets"] > 0.30),
                                  "cash_to_assets", "debt_to_assets")
    out["f_debt_funded_receivables"] = flag(
        (out["receivables_to_assets"] > 0.30) & (out["debt_to_assets"] > 0.30),
        "receivables_to_assets", "debt_to_assets")
    out["f_other_income"] = flag(out["other_income_share"] > 0.30, "other_income_share")
    out["f_interest_cover"] = flag(out["interest_cover"] < 1.5, "interest_cover")

    weights = {f.key: f.weight for f in FLAGS}
    out["score"] = sum(out[k].fillna(False).astype(bool).astype(int) * w for k, w in weights.items())
    out["flags_checked"] = out[FLAG_KEYS].notna().sum(axis=1)
    out["risk"] = pd.cut(out["score"], [-1, 2, 5, MAX_SCORE + 1], labels=["Low", "Medium", "High"])
    out.loc[out["flags_checked"] < 4, "risk"] = np.nan  # too little data to judge
    return out


def latest(scored: pd.DataFrame) -> pd.DataFrame:
    """Most recent fiscal year per company."""
    return scored.sort_values("fy").groupby("symbol").tail(1).reset_index(drop=True)


def raised_flags(row: pd.Series) -> list[Flag]:
    return [f for f in FLAGS if row.get(f.key) is True or row.get(f.key) == 1.0]
