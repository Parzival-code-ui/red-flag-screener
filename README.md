# 🚩 Accounting Red-Flag Screener (Nifty 50)

Scores India's largest non-financial companies on accounting warning signs in their
published financials, then checks whether those signs would have caught past
blow-ups **before** they happened.

> A flag is a reason to dig deeper — not a verdict, and not investment advice.

## Backtest result (v1)

Twelve Indian blow-ups, each scored on the last annual numbers public before the event:

| | |
|---|---|
| Blow-ups flagged (score ≥ 3) | **6 / 12** — Jet Airways, Brightcom, Gensol, Cox & Kings, Kwality, Gitanjali |
| False-alarm rate across Nifty company-years | **13%** |
| Average score, blow-ups vs Nifty | **3.3 vs 0.8** |

Missed: Manpasand and Vakrangee (fabricated numbers that pass every ratio test),
Zee (the pledge crisis wasn't visible in shareholding data that early), Coffee Day,
Sintex and RCom (partly flagged, below the threshold).

**Caveats:** a small sample; thresholds were tuned while looking at these same cases
(in-sample); controls are today's survivors (survivorship bias). See the Methodology tab.

## The flags

| Flag | Weight |
|---|---|
| Profits not turning into cash (CFO/PAT < 0.5 over 3 or 5 years) | 2 |
| Beneish M-Score above −1.78 | 2 |
| Altman Z'' (emerging-market) below 1.1 | 2 |
| Promoter stake down 5+ pp in two years | 2 |
| Receivables growing 30%+ faster than sales, debtor days > 60 | 1 |
| Debt-funded receivables (receivables and debt each > 30% of assets) | 1 |
| Debt up 50%+ in two years with weak cash conversion | 1 |
| Lots of cash *and* lots of debt | 1 |
| Other income > 30% of PBT | 1 |
| Interest cover < 1.5× | 1 |

Score bands: **Low ≤ 2 · Medium 3–5 · High ≥ 6** (max 14).

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

The repo ships with a data snapshot (`data/raw/*.jsonl`, pulled from screener.in in Nov 2026).
To refresh it from your own machine:

```bash
python -m screener.fetch            # whole universe, ~3 min
python -m screener.fetch TCS INFY   # specific symbols
```

This writes `data/raw/fetched.jsonl`, which overrides the snapshot.

### Static web version

```bash
python scripts/export_static.py   # -> dist/index.html
```

Builds a single self-contained HTML page with all scores precomputed, so you can host or open
it anywhere without Python (web/template.html is the page template).

## Layout

```
app.py                 Streamlit dashboard (screener, company deep-dive, backtest, methodology)
screener/universe.py   Nifty 50 non-financials + blow-up list with event dates
screener/data.py       Loads raw extracts into a company-year table
screener/flags.py      Metrics, Beneish, Altman, flags and scoring (no look-ahead)
screener/backtest.py   Blow-ups vs controls (`python -m screener.backtest`)
screener/fetch.py      screener.in scraper for refreshing data
tests/                 pytest suite, including hand-checked ratios and a no-look-ahead test
```

## Data notes

- Banks, NBFCs, insurers and exchanges are excluded because these ratios don't fit lenders.
- Standalone statements are used for Grasim, M&M, L&T, Bajaj Auto (lending arms distort the
  consolidated numbers) and Nestlé (short consolidated history).
- Screener.in doesn't break out SG&A, so Beneish's SGAI is fixed at 1. Working capital for
  Altman is approximated from "other assets" and "other liabilities".
- Promoter-holding history starts in FY2017, and pledge data isn't in the free source.

## Ideas for v2

- Add promoter **pledge** data (NSE/BSE shareholding filings) and auditor-change events.
- Expand to Nifty 500 and test out-of-sample on blow-ups not used for tuning.
- A separate rulebook for banks and NBFCs (GNPA trends, provisioning, ALM gaps).
- An LLM pass over annual-report notes to catch related-party transactions.

Data: screener.in, for personal and academic use.
