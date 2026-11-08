# -*- coding: utf-8 -*-
"""Metrics layer: compute objective valuation/leverage indicators and compare
current readings with the eve of the five historical crashes.

Inputs  (data/): shiller_monthly.csv, downloads/fred_*.csv, downloads/yahoo_*.csv
Outputs (output/): metrics_current.json + console summary table.

Series used:
  - CAPE / GS10 / CPI        : Shiller monthly, 1871-
  - NCBCEL / GDP             : nonfinancial corporate equity MV ($M) vs nominal GDP ($B SAAR)
  - BOGZ1FL663067003Q / GDP  : brokers' customer receivables (margin) vs GDP
  - NDX/TWII/NVDA/CSCO/^GSPC : daily closes for run-up (GSY) variables
"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
DL = DATA / "downloads"
OUT = HERE.parent / "output"
OUT.mkdir(exist_ok=True)

AS_OF = "2026-11-06"  # last trading day in our daily data

# ---------------------------------------------------------------- helpers
def load_yahoo(sym: str) -> pd.DataFrame:
    df = pd.read_csv(DL / f"yahoo_{sym}.csv", parse_dates=["date"])
    return df.set_index("date").sort_index()


def peak_info(df: pd.DataFrame, lo: str, hi: str) -> tuple[pd.Timestamp, float]:
    """Return (peak date, peak price) within a window, using adjusted close."""
    w = df.loc[lo:hi, "adjclose"]
    peak_date = w.idxmax()
    return peak_date, float(w.loc[peak_date])


def runup_stats(df: pd.DataFrame, peak_date: pd.Timestamp) -> dict:
    """GSY run-up variables measured at a peak: 2y return and slope (share of
    the run-up realised in the last 8 months)."""
    p2y = df["adjclose"].asof(peak_date - pd.DateOffset(years=2))
    p8m = df["adjclose"].asof(peak_date - pd.DateOffset(months=8))
    peak = float(df["adjclose"].asof(peak_date))
    ret2y = peak / p2y - 1.0
    slope = (peak - p8m) / (peak - p2y) if peak > p2y else float("nan")
    return {"peak_date": str(peak_date.date()), "peak": peak,
            "ret_2y_pct": round(100 * ret2y, 1), "slope_8m": round(slope, 3),
            "passes_100pct": bool(ret2y >= 1.0)}


# ---------------------------------------------------------------- load
shiller = pd.read_csv(DATA / "shiller_monthly.csv", parse_dates=["date"]).set_index("date")
gdp = pd.read_csv(DL / "fred_GDP.csv", parse_dates=["observation_date"]).set_index("observation_date")["GDP"]
ncb = pd.read_csv(DL / "fred_NCBCEL.csv", parse_dates=["observation_date"]).set_index("observation_date")["NCBCEL"]
margin = pd.read_csv(DL / "fred_BOGZ1FL663067003Q.csv", parse_dates=["observation_date"]).set_index("observation_date")["BOGZ1FL663067003Q"]
# GDP is in $B SAAR, NCBCEL/margin in $M -> put everything in $B
ncb_b = ncb / 1000.0
margin_b = margin / 1000.0

# align quarterly macro to monthly for percentile ranking (ffill)
mv_gdp = (ncb_b / gdp).dropna()
margin_gdp = (margin_b / gdp).dropna()

# ---------------------------------------------------------------- 1) CAPE / ECY
cape = shiller["cape"].dropna()
cape_now = float(cape.iloc[-1])
cape_pct = float((cape < cape_now).mean() * 100)

gs10 = shiller["gs10"]
cpi = shiller["cpi"]
infl10 = (cpi / cpi.shift(120) - 1.0) * 100          # trailing 10y avg total inflation, %/decade
infl10_avg = infl10 / 10.0                            # %/year
real_rate = gs10 - infl10_avg                         # 10y yield minus trailing-10y avg inflation
ecy_nom = 100 / cape - gs10                           # nominal ECY, %
ecy_real = 100 / cape - real_rate                     # Shiller-style real ECY, %

def snap(series: pd.Series, when: str) -> float | None:
    """Value as of the last observation on/before `when`."""
    idx = series.loc[:when].dropna()
    return float(idx.iloc[-1]) if len(idx) else None

crash_eves = {
    "1929-09": "1929-09-30", "1973-01": "1973-01-31", "1987-08": "1987-08-31",
    "2000-03": "2000-03-31", "2007-10": "2007-10-31", "2021-11": "2021-11-30",
}

cape_table = {}
for label, when in crash_eves.items():
    cape_table[label] = {
        "cape": snap(cape, when),
        "ecy_nom": snap(ecy_nom, when),
        "ecy_real": snap(ecy_real, when),
        "gs10": snap(gs10, when),
    }
cape_table["2026-10 (now)"] = {
    "cape": cape_now,
    "ecy_nom": float(ecy_nom.iloc[-1]),
    "ecy_real": float(ecy_real.iloc[-1]),
    "gs10": float(gs10.iloc[-1]),
}
ecy_nom_pct = float((ecy_nom.dropna() < ecy_nom.iloc[-1]).mean() * 100)
ecy_real_pct = float((ecy_real.dropna() < ecy_real.iloc[-1]).mean() * 100)

# ---------------------------------------------------------------- 2) market value / GDP
mv_table = {}
for label, q in [("2000-03", "2000-03-31"), ("2007-10", "2007-10-31"),
                 ("2021-11", "2021-12-31"), ("2026-04 (now)", "2026-04-01")]:
    mv = mv_gdp.asof(pd.Timestamp(q))
    mg = margin_gdp.asof(pd.Timestamp(q))
    mv_table[label] = {"nonfin_mv_gdp": round(float(mv), 3) if pd.notna(mv) else None,
                       "margin_gdp": round(float(mg), 3) if pd.notna(mg) else None}
mv_now = mv_table["2026-04 (now)"]["nonfin_mv_gdp"]
mv_pct = float((mv_gdp.dropna() < mv_now).mean() * 100)
mg_now = mv_table["2026-04 (now)"]["margin_gdp"]
mg_pct = float((margin_gdp.dropna() < mg_now).mean() * 100)

# ---------------------------------------------------------------- 3) GSY run-ups
ndx = load_yahoo("ndx"); twii = load_yahoo("twii")
nvda = load_yahoo("nvda"); csco = load_yahoo("csco"); gspc = load_yahoo("gspc")

gsy = {}
d, p = peak_info(ndx, "2026-09-01", "2026-11-01"); gsy["NDX 2026 (now)"] = runup_stats(ndx, d)
d, p = peak_info(ndx, "1999-12-01", "2000-04-30"); gsy["NDX 2000-03"] = runup_stats(ndx, d)
d, p = peak_info(ndx, "2021-11-01", "2021-12-15"); gsy["NDX 2021-11"] = runup_stats(ndx, d)
d, p = peak_info(twii, "2026-09-01", "2026-11-01"); gsy["TAIEX 2026 (now)"] = runup_stats(twii, d)
d, p = peak_info(twii, "2000-01-01", "2000-04-30"); gsy["TAIEX 2000"] = runup_stats(twii, d)
d, p = peak_info(nvda, "2026-09-01", "2026-11-01"); gsy["NVDA 2026 (now)"] = runup_stats(nvda, d)
d, p = peak_info(csco, "2000-01-01", "2000-04-30"); gsy["CSCO 2000-03"] = runup_stats(csco, d)
# NOTE: Yahoo silently truncates pre-1970 daily data, so 1929 uses Shiller monthly S&P
sp_price = shiller["price"].dropna()
sp29_peak_date = sp_price.loc["1929-07-01":"1929-09-30"].idxmax()
p2y = sp_price.asof(sp29_peak_date - pd.DateOffset(years=2))
p8m = sp_price.asof(sp29_peak_date - pd.DateOffset(months=8))
pk = float(sp_price.loc[sp29_peak_date])
gsy["SPX 1929-09 (monthly)"] = {
    "peak_date": str(sp29_peak_date.date()), "peak": pk,
    "ret_2y_pct": round(100 * (pk / p2y - 1), 1),
    "slope_8m": round((pk - p8m) / (pk - p2y), 3),
    "passes_100pct": bool(pk / p2y - 1 >= 1.0)}
d, p = peak_info(gspc, "1972-12-01", "1973-03-01"); gsy["SPX 1973-01"] = runup_stats(gspc, d)
d, p = peak_info(gspc, "2000-02-01", "2000-04-30"); gsy["SPX 2000-03"] = runup_stats(gspc, d)
d, p = peak_info(gspc, "2007-09-01", "2007-11-30"); gsy["SPX 2007-10"] = runup_stats(gspc, d)

# NDX valuation expansion proxy: CAPE change over the same 2y windows
cape_exp = {
    "2000-03": round(float(cape.asof("2000-03-31") / cape.asof("1998-03-31") - 1) * 100, 1),
    "2021-11": round(float(cape.asof("2021-11-30") / cape.asof("2019-11-30") - 1) * 100, 1),
    "2026-10 (now)": round(float(cape_now / cape.asof("2024-10-31") - 1) * 100, 1),
}

# current distance from peak for the live indices
def dd_now(df: pd.DataFrame, lo: str, hi: str) -> float:
    d_, p_ = peak_info(df, lo, hi)
    last = float(df["adjclose"].iloc[-1])
    return round(100 * (last / p_ - 1), 1)

live = {
    "NDX": {"peak": str(peak_info(ndx, "2026-09-01", "2026-11-01")[0].date()),
            "drawdown_pct": dd_now(ndx, "2026-09-01", "2026-11-01")},
    "TAIEX": {"peak": str(peak_info(twii, "2026-09-01", "2026-11-01")[0].date()),
              "drawdown_pct": dd_now(twii, "2026-09-01", "2026-11-01")},
    "NVDA": {"peak": str(peak_info(nvda, "2026-09-01", "2026-11-01")[0].date()),
             "drawdown_pct": dd_now(nvda, "2026-09-01", "2026-11-01")},
    "SPX": {"peak": str(peak_info(gspc, "2026-09-01", "2026-11-01")[0].date()),
            "drawdown_pct": dd_now(gspc, "2026-09-01", "2026-11-01")},
}

# ---------------------------------------------------------------- save
result = {
    "as_of": AS_OF,
    "cape": {"now": cape_now, "percentile_since_1871": round(cape_pct, 1),
             "peaks": cape_table,
             "ecy_nom_percentile": round(ecy_nom_pct, 1),
             "ecy_real_percentile": round(ecy_real_pct, 1)},
    "mv_gdp": {"now_nonfin_mv_gdp": mv_now, "percentile_since_1945": round(mv_pct, 1),
               "by_date": mv_table, "margin_gdp_now": mg_now,
               "margin_gdp_percentile_since_1945": round(mg_pct, 1)},
    "gsy_runups": gsy,
    "cape_expansion_2y_pct": cape_exp,
    "live_drawdowns": live,
}
(OUT / "metrics_current.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

# ---------------------------------------------------------------- print
print("=== CAPE / ECY (Shiller monthly) ===")
print(f"now {cape_now:.2f}  percentile {cape_pct:.0f}% (since 1871)")
for k, v in cape_table.items():
    print(f"  {k:<16} CAPE={v['cape']:.2f}  ECYnom={v['ecy_nom']:.2f}%  ECYreal={v['ecy_real']:.2f}%  GS10={v['gs10']:.2f}%")
print(f"ECY nominal percentile: {ecy_nom_pct:.0f}%  | ECY real percentile: {ecy_real_pct:.0f}%")

print("\n=== Nonfin MV/GDP & margin/GDP (Z.1 quarterly) ===")
for k, v in mv_table.items():
    print(f"  {k:<16} MV/GDP={v['nonfin_mv_gdp']}  margin/GDP={v['margin_gdp']}")
print(f"MV/GDP percentile: {mv_pct:.0f}% | margin/GDP percentile: {mg_pct:.0f}% (since 1945)")

print("\n=== GSY run-ups at peaks ===")
for k, v in gsy.items():
    print(f"  {k:<16} peak={v['peak']}  2y={v['ret_2y_pct']:>6.1f}%  slope8m={v['slope_8m']:>5.2f}  >=100%: {v['passes_100pct']}")
print(f"\nCAPE expansion over 2y: {cape_exp}")
print("\n=== live drawdowns ===")
for k, v in live.items():
    print(f"  {k}: peak {v['peak']}  drawdown {v['drawdown_pct']:+.1f}%")
