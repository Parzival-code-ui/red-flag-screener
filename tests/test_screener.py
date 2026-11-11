import math

import pandas as pd
import pytest

from screener.backtest import summary
from screener.data import _parse_line, fiscal_year, load_raw
from screener.fetch import extract
from screener.flags import FLAG_KEYS, compute
from screener.universe import BLOWUPS, NIFTY50_NONFIN


@pytest.fixture(scope="module")
def scored():
    return compute(load_raw())


def test_parse_line_restores_nulls():
    rec = _parse_line('{"s":"X","b":"c","y":["Mar2020","Mar2021"],"f":{"prom":[,5.5],"nci":[,]}}')
    assert rec["f"]["prom"] == [None, 5.5]
    assert rec["f"]["nci"] == [None, None]


def test_fiscal_year():
    assert fiscal_year("Mar2018") == 2018
    assert fiscal_year("Dec2015") == 2015
    with pytest.raises(ValueError):
        fiscal_year("TTM")


def test_universe_loaded(scored):
    syms = set(scored.symbol)
    assert set(NIFTY50_NONFIN) <= syms
    assert set(BLOWUPS) <= syms


def test_cash_conversion_hand_calc(scored):
    # Asian Paints FY2024-26: CFO 6104+4424+7088 / PAT 5558+3710+4395
    r = scored[(scored.symbol == "ASIANPAINT") & (scored.fy == 2026)].iloc[0]
    assert r.cfo_to_pat_3y == pytest.approx((6104 + 4424 + 7088) / (5558 + 3710 + 4395))


def test_altman_hand_calc(scored):
    r = scored[(scored.symbol == "TCS") & (scored.fy == 2026)].iloc[0]
    ta, nw = 181167, 362 + 106878
    x1 = (113171 - (62644 - 1238)) / ta
    x2 = 106878 / ta
    x3 = (65487 + 1227) / ta
    x4 = nw / (ta - nw)
    assert r.altman_z == pytest.approx(6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4)


def test_flags_are_bool_or_nan(scored):
    for k in FLAG_KEYS:
        vals = scored[k].dropna().unique()
        assert set(map(bool, vals)) <= {True, False}


def test_no_lookahead(scored):
    """Score for a year must not change if later years are deleted."""
    raw = load_raw()
    cut = raw[~((raw.symbol == "GENSOL") & (raw.fy > 2023))]
    a = compute(cut).query("symbol == 'GENSOL' and fy == 2023").iloc[0]
    b = scored.query("symbol == 'GENSOL' and fy == 2023").iloc[0]
    assert a.score == b.score
    for col in ["beneish_m", "altman_z", "cfo_to_pat_3y"]:
        assert (math.isnan(a[col]) and math.isnan(b[col])) or a[col] == pytest.approx(b[col])


def test_backtest_separates_groups(scored):
    res = summary(scored)
    assert res["n_blowups"] == len(BLOWUPS)
    assert res["blowup_avg_score"] > 2 * res["control_avg_score"]


SAMPLE_HTML = """
<div data-company-id="42"></div>
<section id="profit-loss"><table class="data-table"><thead><tr><th></th>
<th>Mar 2023</th><th>Mar 2024\n<span>12m</span></th><th>Mar 2025</th><th>TTM</th></tr></thead><tbody>
<tr><td class="text"><button>Sales&nbsp;<span>+</span></button></td><td>1,000</td><td>1,200</td><td>1,500</td><td>1,600</td></tr>
<tr><td class="text">Operating Profit</td><td>200</td><td>240</td><td>300</td><td>310</td></tr>
<tr><td class="text">Net Profit <span>+</span></td><td>100</td><td>120</td><td>-</td><td>150</td></tr>
</tbody></table></section>
<section id="balance-sheet"><table class="data-table"><thead><tr><th></th><th>Mar 2023</th><th>Mar 2024</th><th>Mar 2025</th><th>Sep 2025</th></tr></thead>
<tbody><tr><td class="text">Total Assets</td><td>900</td><td>1,000</td><td>1,100</td><td>1,150</td></tr></tbody></table></section>
<section id="cash-flow"><table class="data-table"><thead><tr><th></th><th>Mar 2023</th><th>Mar 2024</th><th>Mar 2025</th></tr></thead>
<tbody><tr><td class="text">Cash from Operating Activity +</td><td>80</td><td>90</td><td>-20</td></tr></tbody></table></section>
<div id="yearly-shp"><table class="data-table"><thead><tr><th></th><th>Mar 2024</th><th>Mar 2025</th></tr></thead>
<tbody><tr><td class="text">Promoters +</td><td>55.10%</td><td>49.90%</td></tr></tbody></table></div>
"""


def test_fetch_extract_parses_screener_layout():
    sched = {"oa": {"Trade receivables": {"Mar 2023": "150", "Mar 2024": "200", "Mar 2025": "400"}},
             "ex": {"Material Cost %": {"Mar 2023": "55.50%", "Mar 2024": "56%", "Mar 2025": "57%"}}}
    rec = extract(SAMPLE_HTML, sched)
    assert rec["y"] == ["Mar2023", "Mar2024", "Mar2025"]
    assert rec["f"]["sales"] == [1000, 1200, 1500]
    assert rec["f"]["np"] == [100, 120, None]
    assert rec["f"]["cfo"] == [80, 90, -20]
    assert rec["f"]["rec"] == [150, 200, 400]
    assert rec["f"]["mat"] == [55.5, 56.0, 57.0]
    assert rec["f"]["prom"] == [None, 55.1, 49.9]
    assert rec["f"]["bor"] == [None, None, None]
