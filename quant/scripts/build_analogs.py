# -*- coding: utf-8 -*-
"""Analog layer: align historical crash trajectories by months-from-peak and
compute depth-conditional forward statistics.

Outputs:
  output/analogs_named.csv      named episodes: peak/trough/depth/duration
  output/analogs_paths.csv      drawdown paths aligned by months from peak (long)
  output/analogs_mined_<asset>.csv   all drawdown episodes >= threshold (data-mined)
  output/analogs_conditional.json    stats conditioned on current drawdown depth
  output/figs/*.png             charts for the report

Method notes:
- Daily series are reduced to month-end closes for path alignment; drawdown
  depth/duration statistics use the daily (or monthly, for 1929) series.
- "Months to recover" counts months from peak to the first month-end close
  back above the peak price; NaN = never recovered within available data.
- Conditional stats pool episodes and, for each depth threshold d, use the
  first day the episode's drawdown crosses -d%; forward returns are measured
  from that day. Episodes still ongoing (no trough yet) contribute duration
  and max-depth-so-far but no forward return.
- CAPE regime conditioning uses Shiller monthly CAPE at the episode start.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
DL = DATA / "downloads"
OUT = HERE.parent / "output"
FIGS = OUT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

AS_OF = "2026-11-06"


def load_yahoo(sym: str) -> tuple[pd.Series, pd.Series]:
    """Return (unadjusted close, adjusted close) as sorted Series."""
    df = pd.read_csv(DL / f"yahoo_{sym}.csv", parse_dates=["date"])
    df = df.set_index("date").sort_index()
    return df["close"].dropna(), df["adjclose"].dropna()


def daily_to_monthly(px: pd.Series) -> pd.Series:
    return px.resample("ME").last().dropna()


def episode_stats(px: pd.Series, peak_date: pd.Timestamp, px_m: pd.Series) -> dict:
    """For an episode whose peak is `peak_date`: trough, max drawdown, months to
    trough, months to recover (NaN if never). The trough search is bounded by the
    first close that reclaims the peak level (episode end), so a later, deeper
    crash belonging to a different episode cannot leak in."""
    peak_level = float(px.asof(peak_date))
    post = px.loc[peak_date:]
    rec_idx = post.index[post.values >= peak_level]
    end_date = rec_idx[1] if len(rec_idx) > 1 else post.index[-1]
    seg = post.loc[peak_date:end_date]
    trough_date = seg.idxmin()
    max_dd = float(seg.min() / peak_level - 1)
    months_trough = (trough_date - peak_date).days / 30.44
    # recovery: first month-end close >= peak level
    after = px_m.loc[peak_date:]
    rec = after[after >= peak_level]
    if len(rec) > 1:  # first entry is the peak itself
        months_rec = (rec.index[1] - peak_date).days / 30.44
    else:
        months_rec = np.nan
    return {"peak_date": str(peak_date.date()), "trough_date": str(trough_date.date()),
            "max_dd": round(max_dd * 100, 1),
            "months_to_trough": round(months_trough, 1),
            "months_to_recover": round(months_rec, 1) if pd.notna(months_rec) else None,
            "end_date": str(end_date.date())}


def aligned_path(px: pd.Series, peak_date: pd.Timestamp, px_m: pd.Series,
                 horizon_m: int = 48) -> pd.Series:
    """Drawdown (%, monthly) aligned at months from peak, capped at horizon."""
    peak_level = float(px.asof(peak_date))
    path = {}
    for m in range(horizon_m + 1):
        t = peak_date + pd.DateOffset(months=m)
        v = px_m.asof(t)
        if pd.isna(v):
            break
        path[m] = round((v / peak_level - 1) * 100, 1)
    return pd.Series(path)


# ---------------------------------------------------------------- named episodes
named = []       # rows for analogs_named.csv
paths_rows = []  # rows for analogs_paths.csv

shiller = pd.read_csv(DATA / "shiller_monthly.csv", parse_dates=["date"]).set_index("date")
sp_m = shiller["price"].dropna()  # monthly S&P since 1871 (nominal)

gspc_c, gspc_a = load_yahoo("gspc")
ndx_c, ndx_a = load_yahoo("ndx")
twii_c, twii_a = load_yahoo("twii")
n225_c, n225_a = load_yahoo("n225")
csco_c, csco_a = load_yahoo("csco")
nvda_c, nvda_a = load_yahoo("nvda")


def peak_in(px: pd.Series, lo: str, hi: str) -> pd.Timestamp:
    return px.loc[lo:hi].idxmax()


episodes = [
    # (name, close series, peak window, horizon months)
    ("SPX 1929 (monthly)", sp_m, ("1929-06-01", "1929-10-31"), 48),
    ("SPX 1973", gspc_c, ("1972-12-01", "1973-03-31"), 48),
    ("SPX 1987", gspc_c, ("1987-08-01", "1987-09-30"), 48),
    ("SPX 2000", gspc_c, ("2000-02-01", "2000-04-30"), 84),
    ("SPX 2007", gspc_c, ("2007-09-01", "2007-11-30"), 48),
    ("NDX 2000", ndx_c, ("2000-02-01", "2000-04-30"), 84),
    ("NDX 2021", ndx_c, ("2021-11-01", "2021-12-15"), 48),
    ("NDX 2026 (live)", ndx_c, ("2026-09-01", "2026-11-01"), 24),
    # NOTE: Yahoo ^TWII only starts 1997-07; the 1973-74 TAIEX crash (~-78%) is not
    # available from this source
    ("TAIEX 2000", twii_c, ("2000-01-01", "2000-05-31"), 48),
    ("TAIEX 2026 (live)", twii_c, ("2026-09-01", "2026-11-01"), 24),
    ("Nikkei 1989", n225_c, ("1989-12-01", "1990-01-31"), 160),
    ("CSCO 2000 (stock)", csco_c, ("2000-02-01", "2000-04-30"), 84),
    ("NVDA 2026 (live)", nvda_c, ("2026-09-01", "2026-11-01"), 24),
]

for name, px, (lo, hi), horizon in episodes:
    px = px.sort_index()
    px_m = daily_to_monthly(px)
    peak = peak_in(px, lo, hi)
    st = episode_stats(px, peak, px_m)
    st["episode"] = name
    named.append(st)
    p = aligned_path(px, peak, px_m, horizon_m=horizon)
    for m, v in p.items():
        paths_rows.append({"episode": name, "months_from_peak": m, "drawdown_pct": v})

named_df = pd.DataFrame(named)[["episode", "peak_date", "trough_date", "max_dd",
                                "months_to_trough", "months_to_recover"]]
named_df.to_csv(OUT / "analogs_named.csv", index=False)
pd.DataFrame(paths_rows).to_csv(OUT / "analogs_paths.csv", index=False)

# ---------------------------------------------------------------- empirical mining
def mine_episodes(px: pd.Series, min_dd: float) -> pd.DataFrame:
    """Detect drawdown episodes: from each running peak, a trough where dd <= -min_dd,
    episode ends when price reclaims the peak (new running max)."""
    px = px.sort_index()
    px_m = daily_to_monthly(px)
    rows = []
    i = 0
    idx = px.index
    while i < len(px):
        cummax = px.iloc[: i + 1].cummax().iloc[-1]
        if px.iloc[i] < cummax:
            # inside a potential drawdown from the running max
            peak_date = px.iloc[: i + 1].idxmax()
            j = i
            trough_date, trough_val = None, None
            while j < len(px):
                if px.iloc[j] >= cummax:
                    break
                if trough_val is None or px.iloc[j] < trough_val:
                    trough_val, trough_date = float(px.iloc[j]), idx[j]
                j += 1
            depth = trough_val / cummax - 1.0
            if depth <= -min_dd / 100 and trough_date is not None:
                st = episode_stats(px, peak_date, px_m)
                rows.append(st)
            # skip past the episode end
            i = j
        else:
            i += 1
    return pd.DataFrame(rows)


mining = {}
for asset, sym, thr in [("NDX", "ndx", 10.0), ("TAIEX", "twii", 15.0), ("NVDA", "nvda", 20.0)]:
    px_c, px_a = load_yahoo(sym)
    eps = mine_episodes(px_c, thr)
    eps.insert(0, "asset", asset)
    eps.to_csv(OUT / f"analogs_mined_{sym}.csv", index=False)
    mining[asset] = (eps, px_c, px_a)

# ---------------------------------------------------------------- conditional stats
shiller_cape = shiller["cape"].dropna()

def conditional(px_c: pd.Series, px_a: pd.Series, eps: pd.DataFrame,
                depths=(10, 15, 20, 25, 30)) -> dict:
    """For each depth d: pool first touches of -d% across episodes; compute eventual
    max DD after touch, months from touch to trough (close series), forward returns
    6m/1y/2y from touch (adjusted close = total return)."""
    out = {}
    for d in depths:
        recs = []
        for _, e in eps.iterrows():
            peak = pd.Timestamp(e.peak_date)
            trough = pd.Timestamp(e.trough_date)
            post = px_c.loc[peak:trough]
            dd = post / post.cummax() - 1.0
            hit = dd[dd <= -d / 100]
            if hit.empty:
                continue
            touch = hit.index[0]
            # eventual max dd after touch (within episode)
            ev_dd = float(dd.loc[touch:].min()) * 100
            m2t = (trough - touch).days / 30.44
            # forward returns from touch (beyond episode trough is fine: use full series)
            base = float(px_a.asof(touch))
            fwd = {}
            for lbl, mo in [("fwd_6m", 6), ("fwd_1y", 12), ("fwd_2y", 24)]:
                v = px_a.asof(touch + pd.DateOffset(months=mo))
                if pd.notna(v) and touch + pd.DateOffset(months=mo) <= px_a.index[-1]:
                    fwd[lbl] = round((float(v) / base - 1) * 100, 1)
            recs.append({
                "peak": e.peak_date, "touch": str(touch.date()),
                "eventual_max_dd": round(ev_dd, 1), "months_to_trough": round(m2t, 1),
                "cape_at_episode_start": float(shiller_cape.asof(peak)) if pd.notna(shiller_cape.asof(peak)) else None,
                **fwd})
        if recs:
            df = pd.DataFrame(recs)
            out[d] = {
                "n_episodes": len(df),
                "n_with_forward_1y": int(df["fwd_1y"].notna().sum()) if "fwd_1y" in df else 0,
                "median_eventual_max_dd": float(df["eventual_max_dd"].median()),
                "mean_eventual_max_dd": round(float(df["eventual_max_dd"].mean()), 1),
                "p10_eventual_max_dd": float(df["eventual_max_dd"].quantile(0.10)),
                "median_months_to_trough": float(df["months_to_trough"].median()),
                "median_fwd_1y": float(df["fwd_1y"].median()) if "fwd_1y" in df and df["fwd_1y"].notna().any() else None,
                "detail": recs,
            }
    return out


cond = {}
for asset in ("NDX", "TAIEX", "NVDA"):
    eps, px_c, px_a = mining[asset]
    cond[asset] = conditional(px_c, px_a, eps)

# regime conditioning for NDX: episodes starting with CAPE > 35
high_cape = {}
for d in (10, 20):
    recs = []
    for r in cond["NDX"][d]["detail"]:
        if r["cape_at_episode_start"] and r["cape_at_episode_start"] > 35:
            recs.append(r)
    high_cape[d] = recs

cond["NDX_high_cape"] = {"n_episodes_10pct": len(high_cape[10]), "detail_10pct": high_cape[10],
                         "n_episodes_20pct": len(high_cape[20]), "detail_20pct": high_cape[20]}

(OUT / "analogs_conditional.json").write_text(
    json.dumps({"as_of": AS_OF, "conditional": cond}, indent=2, ensure_ascii=False))

# ---------------------------------------------------------------- charts
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

paths = pd.DataFrame(paths_rows)
plt.rcParams["font.size"] = 10

# chart 1: aligned drawdown paths
fig, ax = plt.subplots(figsize=(11, 6.5))
styles = {"NDX 2000": ("tab:red", 2.2), "SPX 2000": ("tab:red", 1.0, "--"),
          "SPX 1929 (monthly)": ("black", 1.6), "SPX 1973": ("tab:orange", 1.4),
          "SPX 2007": ("tab:purple", 1.4), "NDX 2021": ("tab:blue", 1.6),
          "TAIEX 2000": ("tab:green", 1.4), "Nikkei 1989": ("tab:brown", 1.6),
          "CSCO 2000 (stock)": ("tab:gray", 1.2, ":"), "NDX 2026 (live)": ("tab:red", 3.0),
          "TAIEX 2026 (live)": ("tab:green", 3.0), "NVDA 2026 (live)": ("black", 3.0)}
for ep, grp in paths.groupby("episode"):
    st = styles.get(ep, ("gray", 1.0))
    ls = st[2] if len(st) > 2 else "-"
    ax.plot(grp.months_from_peak, grp.drawdown_pct, color=st[0], lw=st[1], ls=ls,
            label=ep, alpha=0.9)
ax.axhline(-40, color="k", lw=0.6, ls="--")
ax.text(48.2, -40, "-40%", fontsize=9, va="center")
ax.set_xlabel("months from peak"); ax.set_ylabel("drawdown from peak (%)")
ax.set_title("Crash analogs: drawdown aligned at peak (thick lines = 2026 live)")
ax.legend(fontsize=8, ncol=2, loc="lower left")
ax.grid(alpha=0.25); ax.set_ylim(-95, 5)
fig.tight_layout(); fig.savefig(FIGS / "aligned_paths.png", dpi=150); plt.close(fig)

# chart 2: NDX conditional eventual depth vs current position
fig, ax = plt.subplots(figsize=(9, 5.5))
nd = cond["NDX"]
xs, med, p10, ns = [], [], [], []
for d, v in nd.items():
    if isinstance(d, int):
        xs.append(d); med.append(v["median_eventual_max_dd"])
        p10.append(v["p10_eventual_max_dd"]); ns.append(v["n_episodes"])
ax.plot(xs, med, "o-", label="median eventual max DD")
ax.plot(xs, p10, "s--", label="deep tail (10th pct) eventual max DD")
cur_dd = abs(float(named_df.loc[named_df.episode == "NDX 2026 (live)", "max_dd"].iloc[0]))
ax.axvline(cur_dd, color="tab:red", lw=1.5)
ax.text(cur_dd + 0.4, -25, f"NDX now ({-cur_dd:.1f}%)", color="tab:red", fontsize=9)
for x, m, n in zip(xs, med, ns):
    ax.annotate(f"n={n}", (x, m), textcoords="offset points", xytext=(0, 8), fontsize=8, ha="center")
ax.set_xlabel("drawdown depth when measured (%)")
ax.set_ylabel("eventual max drawdown (%)")
ax.set_title("NDX 1985-2026: given a correction of depth X, how deep does it eventually get?")
ax.legend(); ax.grid(alpha=0.25)
fig.tight_layout(); fig.savefig(FIGS / "ndx_conditional.png", dpi=150); plt.close(fig)

# ---------------------------------------------------------------- print summary
print("=== named episodes ===")
print(named_df.to_string(index=False))

print("\n=== mined episodes (count) ===")
for a, (df, _, _) in mining.items():
    print(f"  {a}: {len(df)} episodes >= threshold; max dd {df.max_dd.min():.1f}% .. {df.max_dd.max():.1f}%")

print("\n=== conditional stats (median eventual max DD after touching depth d) ===")
for asset in ("NDX", "TAIEX", "NVDA"):
    print(f"  [{asset}]")
    for d, v in cond[asset].items():
        if isinstance(d, int):
            f1 = f" 1y fwd {v['median_fwd_1y']:+.1f}%" if v["median_fwd_1y"] is not None else ""
            print(f"    at -{d:>2}%: n={v['n_episodes']:>2}  median eventual {v['median_eventual_max_dd']:>6.1f}%  "
                  f"p10(deep) {v['p10_eventual_max_dd']:>6.1f}%  median m2t {v['median_months_to_trough']:>4.1f}m{f1}")

print("\n=== NDX episodes starting with CAPE>35 ===")
for r in high_cape[10]:
    print(f"  peak {r['peak']}  CAPE {r['cape_at_episode_start']:.1f}  eventual {r['eventual_max_dd']}%  1y fwd {r.get('fwd_1y')}%")
