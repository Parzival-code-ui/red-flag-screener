"""Streamlit dashboard: `streamlit run app.py`"""
import altair as alt
import pandas as pd
import streamlit as st

from screener.backtest import ALERT_SCORE, blowup_rows, summary
from screener.data import load_raw
from screener.flags import ALTMAN_DISTRESS, BENEISH_THRESHOLD, FLAGS, FLAG_KEYS, MAX_SCORE, compute, latest
from screener.universe import BLOWUPS, NIFTY50_NONFIN, display_name

st.set_page_config(page_title="Red-Flag Screener · Nifty 50", page_icon="🚩", layout="wide")

FLAG_LABEL = {f.key: f.label for f in FLAGS}
RISK_ICON = {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟢 Low"}


@st.cache_data
def scored() -> pd.DataFrame:
    s = compute(load_raw())
    s["name"] = s["symbol"].map(display_name)
    return s


def flag_text(row) -> str:
    raised = [FLAG_LABEL[k] for k in FLAG_KEYS if row.get(k) is True or row.get(k) == 1.0]
    return " · ".join(raised) if raised else "—"


s = scored()
st.title("🚩 Accounting Red-Flag Screener")
st.caption("Nifty 50 non-financial companies, scored on warning signs in their published "
           "financials. A flag is a reason to dig deeper — not a verdict, and not investment advice.")

tab_screen, tab_company, tab_backtest, tab_method = st.tabs(
    ["Screener", "Company deep-dive", "Backtest: past blow-ups", "Methodology"])

# ---------------- Screener ----------------
with tab_screen:
    cur = latest(s[s.symbol.isin(NIFTY50_NONFIN)]).copy()
    cur["Risk"] = cur["risk"].astype(str).map(RISK_ICON).fillna("⚪ Not enough data")
    cur["Flags raised"] = cur.apply(flag_text, axis=1)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Companies", len(cur))
    c2.metric("High risk", int((cur.risk == "High").sum()))
    c3.metric("Medium risk", int((cur.risk == "Medium").sum()))
    c4.metric("Latest fiscal year", int(cur.fy.max()))
    min_score = st.slider("Show companies with score at least", 0, MAX_SCORE, 0)
    view = cur[cur.score >= min_score].sort_values(["score", "symbol"], ascending=[False, True])
    st.dataframe(
        view[["name", "symbol", "fy", "score", "Risk", "Flags raised", "cfo_to_pat_3y",
              "beneish_m", "altman_z", "promoter_change_2y"]],
        hide_index=True, width="stretch", height=35 * (len(view) + 1) + 3,
        column_config={
            "name": "Company", "symbol": "NSE", "fy": st.column_config.NumberColumn("FY", format="%d"),
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=MAX_SCORE, format="%d"),
            "cfo_to_pat_3y": st.column_config.NumberColumn("CFO / PAT (3y)", format="%.2f"),
            "beneish_m": st.column_config.NumberColumn("Beneish M", format="%.2f"),
            "altman_z": st.column_config.NumberColumn("Altman Z''", format="%.2f"),
            "promoter_change_2y": st.column_config.NumberColumn("Promoter Δ 2y (pp)", format="%.1f"),
        })
    st.caption("Score = weighted count of flags raised (max %d). Low ≤ 2, Medium 3–5, High ≥ 6." % MAX_SCORE)

# ---------------- Company ----------------
with tab_company:
    options = sorted(s.symbol.unique(), key=lambda x: (x not in NIFTY50_NONFIN, display_name(x)))
    sym = st.selectbox("Company", options, format_func=lambda x: f"{display_name(x)} ({x})"
                       + ("  — past blow-up" if x in BLOWUPS else ""))
    g = s[s.symbol == sym].sort_values("fy")
    if sym in BLOWUPS:
        st.warning(f"**{BLOWUPS[sym]['event']}**. Backtest uses FY{BLOWUPS[sym]['test_fy']} numbers.")
    st.caption(f"Statements: {g.basis.iloc[0]} · figures in ₹ crore · source: screener.in")
    last = g.iloc[-1]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Score (FY{int(last.fy)})", f"{int(last.score)} / {MAX_SCORE}")
    m2.metric("CFO / PAT (3y)", "—" if pd.isna(last.cfo_to_pat_3y) else f"{last.cfo_to_pat_3y:.2f}")
    m3.metric("Beneish M", "—" if pd.isna(last.beneish_m) else f"{last.beneish_m:.2f}")
    m4.metric("Altman Z''", "—" if pd.isna(last.altman_z) else f"{last.altman_z:.2f}")

    score_chart = alt.Chart(g).mark_bar().encode(
        x=alt.X("fy:O", title="Fiscal year"), y=alt.Y("score:Q", title="Red-flag score",
                                                         scale=alt.Scale(domain=[0, MAX_SCORE])),
        color=alt.Color("risk:N", scale=alt.Scale(domain=["Low", "Medium", "High"],
                                                  range=["#4c9a6a", "#e0a03a", "#c8463d"]), title="Risk"),
        tooltip=["fy", "score", "risk"]).properties(height=220)
    st.altair_chart(score_chart, width="stretch")

    left, right = st.columns(2)
    cash = g.melt("fy", ["np", "cfo"], "series", "₹ crore").replace({"np": "Net profit", "cfo": "Operating cash flow"})
    left.altair_chart(alt.Chart(cash).mark_line(point=True).encode(
        x=alt.X("fy:O", title=None), y="₹ crore:Q",
        color=alt.Color("series:N", title=None, scale=alt.Scale(range=["#1f4e79", "#e0a03a"])),
        tooltip=["fy", "series", "₹ crore"]).properties(title="Profit vs cash", height=260),
        width="stretch")
    bal = g.assign(debtor_days=g.debtor_days, debt_pct=g.debt_to_assets * 100)
    bal = bal.melt("fy", ["debtor_days", "debt_pct"], "series", "value").replace(
        {"debtor_days": "Debtor days", "debt_pct": "Borrowings % of assets"})
    right.altair_chart(alt.Chart(bal).mark_line(point=True).encode(
        x=alt.X("fy:O", title=None), y=alt.Y("value:Q", title=None),
        color=alt.Color("series:N", title=None, scale=alt.Scale(range=["#c8463d", "#1f4e79"])),
        tooltip=["fy", "series", alt.Tooltip("value:Q", format=".1f")]).properties(
        title="Receivables and leverage", height=260), width="stretch")

    grid = g.set_index("fy")[FLAG_KEYS].T
    grid.index = [FLAG_LABEL[k] for k in grid.index]
    grid = grid.apply(lambda col: col.map(lambda v: "🚩" if v is True or v == 1.0 else ("·" if v is False or v == 0.0 else "n/a")))
    grid.columns = [f"FY{c}" for c in grid.columns]
    st.markdown("**Flag history**")
    st.dataframe(grid, width="stretch", height=35 * (len(grid) + 1) + 3)

# ---------------- Backtest ----------------
with tab_backtest:
    res = summary(s)
    st.markdown("Each blow-up is scored on the **last annual numbers that were public before the "
                "event**. Controls are today's Nifty 50 non-financials over the same years.")
    b1, b2, b3 = st.columns(3)
    b1.metric(f"Blow-ups flagged (score ≥ {ALERT_SCORE})",
              f"{round(res['blowup_hit_rate'] * res['n_blowups'])} / {res['n_blowups']}")
    b2.metric("False-alarm rate in Nifty company-years", f"{res['control_false_alarm_rate']:.0%}")
    b3.metric("Average score: blow-ups vs Nifty", f"{res['blowup_avg_score']:.1f} vs {res['control_avg_score']:.1f}")
    br = blowup_rows(s)
    br["Flags raised"] = br.apply(flag_text, axis=1)
    br["Caught?"] = br.score.ge(ALERT_SCORE).map({True: "✅ Yes", False: "❌ Missed"})
    st.dataframe(br[["name", "fy", "score", "Caught?", "Flags raised", "event"]], hide_index=True,
                 width="stretch", height=35 * (len(br) + 1) + 3,
                 column_config={"name": "Company", "fy": st.column_config.NumberColumn("Scored on FY", format="%d"),
                                "score": "Score", "event": "What happened"})
    rates = (res["flag_rates"] * 100).reset_index(names="flag")
    rates["flag"] = rates["flag"].map(FLAG_LABEL)
    rates = rates.melt("flag", ["blowups", "nifty_controls"], "group", "pct").replace(
        {"blowups": "Blow-ups", "nifty_controls": "Nifty controls"})
    st.altair_chart(alt.Chart(rates).mark_bar().encode(
        y=alt.Y("flag:N", title=None, sort="-x", axis=alt.Axis(labelLimit=320)), x=alt.X("pct:Q", title="% of cases flagged"),
        color=alt.Color("group:N", title=None, scale=alt.Scale(range=["#c8463d", "#8a94a6"])),
        yOffset="group:N", tooltip=["flag", "group", alt.Tooltip("pct:Q", format=".0f")]).properties(
        title="Which flags separate blow-ups from healthy companies?", height=380), width="stretch")
    st.info("**Read this honestly.** 12 blow-ups is a tiny sample, the thresholds were tuned while "
            "looking at these same cases (in-sample), and the controls are survivors. Outright frauds with "
            "fabricated cash (Manpasand, Vakrangee) can pass every ratio test — that's a known limit of "
            "statement-based screening.")

# ---------------- Methodology ----------------
with tab_method:
    st.markdown("### The flags")
    st.dataframe(pd.DataFrame([{"Flag": f.label, "Weight": f.weight, "What it means": f.why} for f in FLAGS]),
                 hide_index=True, width="stretch")
    st.markdown(f"""
### Models
- **Beneish M-Score (8-variable).** DSRI, GMI, AQI, SGI, DEPI, LVGI, TATA; SGAI is fixed at 1 because
  SG&A isn't broken out in the source data. Above **{BENEISH_THRESHOLD}** = likely manipulator.
  Gross margin uses material cost where reported, otherwise operating margin.
- **Altman Z'' (emerging-market version).** 6.56·WC/TA + 3.26·RE/TA + 6.72·EBIT/TA + 1.05·BookEquity/TL.
  Below **{ALTMAN_DISTRESS}** = distress zone. Working capital is approximated as
  "other assets" minus "other liabilities" (excluding minority interest).

### Data
- Annual statements from screener.in (consolidated where meaningful; standalone for Grasim, M&M,
  L&T, Bajaj Auto and Nestlé — lending arms or short consolidated history distort the group numbers).
- Banks, NBFCs, insurers and exchanges are excluded: these ratios don't apply to lenders.
- Promoter holding history starts in FY2017, so the promoter flag can't fire for older years.
  Pledge data isn't in the free source yet.
- Screener figures may include later restatements, a mild look-ahead risk in the backtest.

### Limitations
A screener reads published numbers. It can't see forged bank statements, related-party
round-tripping hidden off the books, or a promoter quietly pledging shares between filings.
""")
