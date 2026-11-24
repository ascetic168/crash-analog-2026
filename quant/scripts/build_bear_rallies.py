# -*- coding: utf-8 -*-
"""Big-up-day event study inside the dot-com bear (owner question 2026-11-24).

Question asked on 2026-11-24, after the NDX rose +6.9% (NVDA +31.5%) in one
session and TAIEX gapped about +9%: did the 2000-2002 dot-com cycle also have
days when the market surged inside an ongoing decline — when, how big, and
what happened afterwards?

Layers (close-to-close; depths in percent-from-peak like the reports):
  1. big up days: every session in a bear window whose 1-day gain clears a
     threshold. For each: the reference low (lowest close of the prior 20
     sessions), the first later close below it ("new low"), how much further
     the rally ran before that new low, and fixed-horizon forward returns
  2. rally episodes: zig-zag swings of >= 10% between the closing peak and the
     closing trough, with the big up days that sit inside each swing
  3. cross-history base rates: the same day-level conditioning applied to the
     full history of each series (is a big up day in a deep drawdown a bottom
     signal?) — counted per cluster, since big up days come in runs
  4. leader stock: Cisco's big up days in its own 2000-2002 bear, plus NVDA's
     largest one-day gains on record (where does 2026-11-23 rank?)

Prices come from the Yahoo chart API (same endpoint as download_data.py) and
are cached in ../data/bear_rallies/ (gitignored). The TAIEX row for the current
day is an intraday quote if the script runs during the Taiwan session — it is
flagged as such in current_snapshot.json.

Usage: python build_bear_rallies.py [--refresh]
"""
import argparse
import csv
import datetime as dt
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from pandas.tseries.holiday import USFederalHolidayCalendar  # noqa: E402

HERE = Path(__file__).resolve().parent
DL = HERE.parent / "data" / "bear_rallies"
OUT = HERE.parent / "output_rallies"
FIGS = OUT / "figs"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# label -> yahoo symbol; indices are compared on raw closes (as in the reports),
# stocks on the split-adjusted close so that old splits do not read as rallies
SERIES = {"NDX": "^NDX", "IXIC": "^IXIC", "SPX": "^GSPC", "TAIEX": "^TWII",
          "NVDA": "NVDA", "CSCO": "CSCO"}
STOCKS = {"NVDA", "CSCO"}

# bear windows: label -> series, peak search window, big-day threshold (%)
BEARS = {
    "NDX 2000-02": ("NDX", ("2000-01-01", "2000-05-31"), 5.0),
    "TAIEX 2000-01": ("TAIEX", ("1999-06-01", "2000-05-31"), 3.5),
    "CSCO 2000-02": ("CSCO", ("2000-01-01", "2000-05-31"), 10.0),
}
BASE_RATE_THR = {"NDX": 5.0, "IXIC": 4.0, "SPX": 4.0, "TAIEX": 3.5}
MIN_DD = 15.0              # "deep drawdown" floor for the base rates
REF_LOOKBACK = 20          # sessions defining the pre-rally reference low
HORIZONS = (5, 20, 60, 120, 250)
CLUSTER_GAP = 10           # a big up day more than this many sessions after the previous one,
                           # or after a lower low has printed, starts a new cluster
ZIGZAG_THETA = 10.0        # % reversal that ends a rally episode

# CJK-capable font for the chart text; unicode_minus keeps the minus sign
matplotlib.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 10


# ---------------------------------------------------------------- data
def fetch(symbol: str, dest: Path) -> None:
    """Full daily history from the Yahoo chart API -> date,adjclose,close CSV."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1=0&period2={int(time.time())}&interval=1d&events=history"
    )
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    close = result["indicators"]["quote"][0]["close"]
    adj = result["indicators"]["adjclose"][0]["adjclose"]
    with dest.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "adjclose", "close"])
        for t, a, c in zip(result["timestamp"], adj, close):
            if a is None or c is None:
                continue
            day = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
            w.writerow([day, a, c])
    time.sleep(1.0)


def load_series(refresh: bool) -> dict[str, pd.DataFrame]:
    """label -> DataFrame indexed by date with raw and adjusted closes."""
    DL.mkdir(parents=True, exist_ok=True)
    out = {}
    for label, symbol in SERIES.items():
        dest = DL / f"yahoo_{symbol.strip('^').lower()}.csv"
        if refresh or not dest.exists():
            print(f"GET {symbol}")
            fetch(symbol, dest)
        df = pd.read_csv(dest, parse_dates=["date"]).drop_duplicates("date", keep="last")
        out[label] = df.set_index("date").sort_index()
    return out


def prep(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Price, 1-day %, trailing-5-day % (before the day) and drawdown from the
    trailing 36-month closing high (inside a bear this is the bear's own peak)."""
    px = df["adjclose" if label in STOCKS else "close"].astype(float).dropna()
    r = px.pct_change() * 100
    dd = (px / px.rolling(756, min_periods=1).max() - 1) * 100
    return pd.DataFrame({"close": px, "up_pct": r, "prev5_pct": r.rolling(5).sum().shift(1), "dd": dd})


def find_bear(px: pd.Series, peak_window: tuple[str, str]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Closing peak inside the search window; trough = lowest close of the next 36 months."""
    peak = px.loc[peak_window[0]:peak_window[1]].idxmax()
    return peak, px.loc[peak:peak + pd.DateOffset(months=36)].idxmin()


# ---------------------------------------------------------------- 1. big up days
def event_table(df: pd.DataFrame, thr: float) -> pd.DataFrame:
    """Every session with a 1-day gain >= thr, with the aftermath of each.

    reference low = lowest close of the prior REF_LOOKBACK sessions;
    new low      = first later close below the reference low;
    extra        = further gain from the big day's close to the highest close
                   reached before that new low (NaN when the new low is next day).
    """
    close = df["close"]
    idx = df.index
    n = len(df)
    rows = []
    for i in range(REF_LOOKBACK, n):
        if df["up_pct"].iloc[i] < thr:
            continue
        c0 = close.iloc[i]
        ref_low = close.iloc[i - REF_LOOKBACK:i].min()
        after = close.iloc[i + 1:]
        below = after[after < ref_low]
        has_new_low = len(below) > 0
        new_low_day = below.index[0] if has_new_low else pd.NaT
        run = after.loc[:new_low_day].iloc[:-1] if has_new_low else after
        row = {
            "date": idx[i],
            "close": c0,
            "up_pct": df["up_pct"].iloc[i],
            "prev5_pct": df["prev5_pct"].iloc[i],
            "dd_prev": df["dd"].iloc[i - 1],
            "dd_post": df["dd"].iloc[i],
            "ref_low": ref_low,
            "extra_pct": (run.max() / c0 - 1) * 100 if len(run) else np.nan,
            "extra_peak_date": run.idxmax() if len(run) else pd.NaT,
            "new_low_date": new_low_day,
            "td_to_new_low": len(run) + 1 if has_new_low else np.nan,
            "new_low_dd": df["dd"].loc[new_low_day] if has_new_low else np.nan,
        }
        for h in HORIZONS:
            row[f"fwd_{h}"] = (close.iloc[i + h] / c0 - 1) * 100 if i + h < n else np.nan
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    pos = pd.Series(np.arange(n), index=idx)
    gaps = pos[out["date"]].diff().to_numpy()      # out is RangeIndex-aligned: no label alignment
    # a run continues only while no lower low prints between two big days
    lower_low = (out["ref_low"].diff() < -1e-9).to_numpy()
    out["first_of_cluster"] = np.isnan(gaps) | (gaps > CLUSTER_GAP) | lower_low
    return out


def between(events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Events strictly after `start` and before `end`."""
    if events.empty:
        return events
    return events[(events["date"] > start) & (events["date"] < end)].copy()


# ---------------------------------------------------------------- 2. zig-zag episodes
def zigzag_rallies(px: pd.Series, theta_pct: float) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Rally legs (low -> high) of at least theta_pct on closing prices.

    `px` must already be cut to [peak .. trough]: the peak is the first point
    and the trough the last, so every leg is a rally inside the bear.
    """
    vals = px.to_numpy()
    thr = theta_pct / 100
    pivots = []            # (position, kind) confirmed so far
    mode, ext = "low", 0   # next pivot to confirm; running extreme since the last one
    for i in range(1, len(vals)):
        v = vals[i]
        if mode == "low":
            if v < vals[ext]:
                ext = i
            elif v >= vals[ext] * (1 + thr):
                pivots.append((ext, "low"))
                mode, ext = "high", i
        elif v > vals[ext]:
            ext = i
        elif v <= vals[ext] * (1 - thr):
            pivots.append((ext, "high"))
            mode, ext = "low", i
    if not pivots or pivots[-1][0] != ext:
        pivots.append((ext, mode))
    return [(px.index[a], px.index[b])
            for (a, ka), (b, kb) in zip(pivots, pivots[1:]) if ka == "low" and kb == "high"]


def episode_table(px: pd.Series, peak: pd.Timestamp, trough: pd.Timestamp,
                  events: pd.DataFrame) -> pd.DataFrame:
    """One row per zig-zag leg: size, the big up days inside it, and the first
    close below the leg's low after its high (NaT = the bear's own bottom)."""
    seg = px.loc[peak:trough]
    rows = []
    for low_day, high_day in zigzag_rallies(seg, ZIGZAG_THETA):
        low, high = float(px.loc[low_day]), float(px.loc[high_day])
        after = px.loc[high_day:].iloc[1:]
        below = after[after < low]
        new_low_day = below.index[0] if len(below) else pd.NaT
        inside = events[(events["date"] >= low_day) & (events["date"] <= high_day)]
        top = inside.sort_values("up_pct").iloc[-1] if len(inside) else None
        rows.append({
            "low_date": low_day, "low_close": low, "low_dd": (low / float(px.loc[peak]) - 1) * 100,
            "high_date": high_day, "high_close": high, "high_dd": (high / float(px.loc[peak]) - 1) * 100,
            "gain_pct": (high / low - 1) * 100,
            "td_low_to_high": int(seg.index.get_loc(high_day) - seg.index.get_loc(low_day)),
            "n_big_days": int(len(inside)),
            "biggest_day": top["date"] if top is not None else pd.NaT,
            "biggest_day_pct": float(top["up_pct"]) if top is not None else np.nan,
            "new_low_date": new_low_day,
            "td_high_to_new_low": int(px.index.get_loc(new_low_day) - px.index.get_loc(high_day))
            if not pd.isna(new_low_day) else np.nan,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 3. base rates
def depth_bucket(dd_prev: float) -> str:
    if dd_prev >= -25:
        return "15-25%"
    if dd_prev >= -40:
        return "25-40%"
    return "40%+"


def base_rates(df: pd.DataFrame, thr: float) -> tuple[dict, pd.DataFrame]:
    """Day-level base rate on the full series: drawdown >= MIN_DD on the eve and
    a 1-day gain >= thr. Counted per cluster (first big up day of a run) so that
    one rally is not counted five times. Also returns the cluster list."""
    ev = event_table(df, thr)
    if ev.empty:
        return {"n_days": 0, "n_clusters": 0, "by_depth": {}}, ev
    ev = ev[ev["dd_prev"] <= -MIN_DD].copy()
    ev["depth"] = ev["dd_prev"].map(depth_bucket)
    cl = ev[ev["first_of_cluster"]].copy()
    out = {"n_days": int(len(ev)), "n_clusters": int(len(cl)), "by_depth": {}}
    groups = [("all", cl)] + [(b, g) for b, g in cl.groupby("depth", sort=True)]
    for name, sub in groups:
        if len(sub) == 0:
            continue
        row = {"n": int(len(sub))}
        # a horizon counts only when it is fully observed (the live event is excluded)
        for h in (20, 60, 120, 250):
            valid = sub[f"fwd_{h}"].notna()
            hit = valid & sub["td_to_new_low"].notna() & (sub["td_to_new_low"] <= h)
            row[f"n_{h}d"] = int(valid.sum())
            row[f"p_new_low_{h}d"] = round(float(hit.sum() / valid.sum()) * 100, 1) if valid.sum() else None
        for h in (60, 250):
            v = sub[f"fwd_{h}"].dropna()
            row[f"median_fwd_{h}d"] = round(float(v.median()), 1) if len(v) else None
        out["by_depth"][name] = row
    return out, cl


def cluster_table(df: pd.DataFrame, bear_events: pd.DataFrame) -> pd.DataFrame:
    """One row per run of big up days inside the bear (see CLUSTER_GAP), measured
    from the first big day: how far the rally ran and when the pre-rally low broke."""
    if bear_events.empty:
        return bear_events
    close = df["close"]
    rows = []
    for _, g in bear_events.groupby(bear_events["first_of_cluster"].cumsum()):
        first = g.iloc[0]
        after = close.loc[first["date"]:].iloc[1:]
        below = after[after < first["ref_low"]]
        new_low_day = below.index[0] if len(below) else pd.NaT
        run = after.loc[:new_low_day].iloc[:-1] if len(below) else after
        top = g.loc[g["up_pct"].idxmax()]
        rows.append({
            "first_date": first["date"], "first_up_pct": first["up_pct"],
            "dd_eve_pct": first["dd_prev"], "n_big_days": int(len(g)),
            "biggest_date": top["date"], "biggest_pct": top["up_pct"],
            "peak_date": run.idxmax() if len(run) else pd.NaT,
            "extra_pct": (run.max() / first["close"] - 1) * 100 if len(run) else np.nan,
            "new_low_date": new_low_day,
            "td_to_new_low": len(run) + 1 if len(below) else np.nan,
            "new_low_dd": df["dd"].loc[new_low_day] if len(below) else np.nan,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- figures
def fig_marked(px: pd.Series, events: pd.DataFrame, peak: pd.Timestamp, trough: pd.Timestamp,
               thr: float, label_thr: float, window: tuple[str, str], zoom: tuple[str, str],
               ticks: tuple, title: str, dest: Path) -> None:
    """Top: the whole cycle for context. Bottom: the bear window zoomed in with
    every big up day marked; the days >= label_thr are numbered and listed at right.
    Figures are sized to the report's A4 text width (~6.9 in) so that the small
    fonts stay legible on paper instead of being shrunk at page layout."""
    win, zin = px.loc[window[0]:window[1]], px.loc[zoom[0]:zoom[1]]
    big = events[events["date"] < trough].sort_values("date")
    fig, (ax, az) = plt.subplots(2, 1, figsize=(6.9, 5.6), gridspec_kw={"height_ratios": [1, 1.5]})
    fig.subplots_adjust(right=0.70, hspace=0.13, top=0.925, bottom=0.075, left=0.085)
    for a, seg in ((ax, win), (az, zin)):
        a.axvspan(peak, trough, color="#ededed", zorder=0)
        a.plot(seg.index, seg.to_numpy(), color="#333333", lw=0.7, zorder=2)
        a.set_yscale("log")
        a.set_yticks([t for t in ticks if float(seg.min()) * 0.9 <= t <= float(seg.max()) * 1.15])
        a.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        a.tick_params(labelsize=7)
        a.grid(axis="y", color="#dddddd", lw=0.5)
    ax.annotate("", xy=(pd.Timestamp(zoom[0]), 0.93), xytext=(pd.Timestamp(zoom[1]), 0.93),
                xycoords=("data", "axes fraction"), textcoords=("data", "axes fraction"),
                arrowprops=dict(arrowstyle="<->", color="#1f77b4", lw=0.6))
    ax.text(pd.Timestamp(zoom[0]), 0.955, "下圖放大範圍", transform=ax.get_xaxis_transform(),
            fontsize=7, color="#1f77b4", va="bottom")
    ax.scatter(big["date"], big["close"], marker="^", s=12 + big["up_pct"] * 2.6,
               c=big["up_pct"], cmap="YlOrRd", vmin=thr, vmax=max(float(big["up_pct"].max()), 2 * thr),
               edgecolor="black", linewidth=0.3, zorder=5)
    lab = big[big["up_pct"] >= label_thr].reset_index(drop=True)
    prev = None
    for k, row in lab.iterrows():        # labels close together in time alternate above/below
        near = prev is not None and (row["date"] - prev).days <= 25
        az.annotate(str(k + 1), (row["date"], row["close"]), textcoords="offset points",
                    xytext=(4, -12) if near else (4, 8), fontsize=7, fontweight="bold",
                    color="#8b0000", zorder=6)
        prev = row["date"]
    pk, tr = float(px.loc[peak]), float(px.loc[trough])
    # the full day list lives in the table right below the figure in the report;
    # the in-figure box only carries the legend so its text stays legible on paper
    box = "\n".join(
        [f"峰頂 {peak.date()}",
         f"{pk:,.2f}",
         f"谷底 {trough.date()}",
         f"{tr:,.2f}（{(tr / pk - 1) * 100:.1f}%）",
         "",
         f"三角＝漲幅 {thr:g}% 以上",
         f"（{len(big)} 個交易日）",
         f"編號＝漲幅 {label_thr:g}% 以上",
         f"（{len(lab)} 天）"])
    fig.text(0.72, 0.985, box, va="top", ha="left", fontsize=7.5)
    fig.suptitle(title, fontsize=9.5, x=0.36, y=0.985)
    fig.savefig(dest, dpi=220)
    plt.close(fig)
    plt.close(fig)


def fig_fan(px: pd.Series, events: pd.DataFrame, dest: Path, span: int = 120) -> None:
    """Forward paths after each big up day (>= 6%), percent from the big day's close."""
    paths, names = [], []
    for _, row in events.iterrows():
        i = px.index.get_loc(row["date"])
        seg = px.iloc[i:i + span + 1]
        if len(seg) == span + 1:
            paths.append((seg.to_numpy() / float(row["close"]) - 1) * 100)
            names.append(row["date"])
    if not paths:
        return
    arr = np.vstack(paths)
    x = np.arange(arr.shape[1])
    fig, ax = plt.subplots(figsize=(6.9, 3.9))
    fig.subplots_adjust(left=0.09, right=0.985, top=0.9, bottom=0.14)
    ax.axhline(0, color="black", lw=0.5)
    for p in arr:
        ax.plot(x, p, color="#8aa0b8", lw=0.5, alpha=0.45)
    ax.plot(x, np.median(arr, axis=0), color="black", lw=1.3, label=f"中位數（n={len(arr)}）")
    ax.fill_between(x, np.percentile(arr, 25, axis=0), np.percentile(arr, 75, axis=0),
                    color="#bbbbbb", alpha=0.35, label="25–75% 區間")
    for d, color in [("2000-05-30", "#1f77b4"), ("2001-01-03", "#d62728"),
                     ("2001-04-05", "#2ca02c"), ("2002-05-08", "#9467bd")]:
        if pd.Timestamp(d) in names:
            ax.plot(x, arr[names.index(pd.Timestamp(d))], color=color, lw=1.0, label=d)
    ax.set_xlabel("大漲日之後的交易日數（大漲日收盤＝0）", fontsize=7.5)
    ax.set_ylabel("距大漲日收盤 %", fontsize=7.5)
    ax.set_title(f"NDX 崩盤期 {len(arr)} 個單日漲幅 6% 以上的交易日，之後 {span} 個交易日的走勢", fontsize=9)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=6.8, loc="lower left")
    ax.grid(color="#e3e3e3", lw=0.5)
    fig.savefig(dest, dpi=220)
    plt.close(fig)


# ---------------------------------------------------------------- output helpers
def to_csv(df: pd.DataFrame, dest: Path) -> None:
    out = df.copy()
    for c in out.columns:
        if str(out[c].dtype).startswith(("datetime", "datetimetz")):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
        elif str(out[c].dtype) == "float64":
            out[c] = out[c].round(2)
    out.to_csv(dest, index=False)


def fmt_day(v) -> str:
    return "" if pd.isna(v) else str(pd.Timestamp(v).date())


def pct(x: float) -> str:
    """Signed percent with the typographic minus the reports use."""
    return f"{x:+.1f}%".replace("-", "−")


def md_table(dest: Path, header: list[str], rows: list[list[str]]) -> None:
    """Markdown table for the report, so that its numbers are never hand-copied."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def md_clusters(dest: Path, clu: pd.DataFrame) -> None:
    """Report table: one row per run of big up days inside a bear, measured from
    the first big day."""
    # short headers: in the PDF build every header stays on one line, and a
    # 8-column table has to fit the A4 text width
    header = ["#", "首漲日", "單日", "前一日距峰頂", "波內最大單日", "反彈高點（再漲）",
              "破底日", "撐了（交易日）"]
    rows = []
    for k, r in enumerate(clu.itertuples(index=False)):
        peak = (f"{fmt_day(r.peak_date)}（{pct(r.extra_pct)}）" if pd.notna(r.extra_pct)
                else "無（當日即是高點）")
        rows.append([
            str(k + 1), fmt_day(r.first_date), pct(r.first_up_pct), pct(r.dd_eve_pct),
            "同左" if r.n_big_days == 1 else f"{fmt_day(r.biggest_date)} {pct(r.biggest_pct)}",
            peak, fmt_day(r.new_low_date), str(int(r.td_to_new_low)),
        ])
    md_table(dest, header, rows)


def md_episodes(dest: Path, epi: pd.DataFrame) -> None:
    """Report table: one row per zig-zag rally (low -> high) of the bear."""
    rows = []
    for k, r in enumerate(epi.itertuples(index=False)):
        rows.append([
            str(k + 1), f"{fmt_day(r.low_date)}（{pct(r.low_dd)}）", f"{fmt_day(r.high_date)}（{pct(r.high_dd)}）",
            pct(r.gain_pct), str(int(r.td_low_to_high)), str(int(r.n_big_days)),
            "未再破底（谷底）" if pd.isna(r.new_low_date) else fmt_day(r.new_low_date),
            "" if pd.isna(r.td_high_to_new_low) else str(int(r.td_high_to_new_low)),
        ])
    md_table(dest, ["#", "起漲日（低點）", "反彈高點", "幅度", "交易日", "大漲日",
                    "跌破起漲點", "高點到破底"], rows)


def md_big_days(dest: Path, ev: pd.DataFrame, limit: int | None = None) -> None:
    """Report table: single big up days with their aftermath."""
    rows = []
    sub = ev if limit is None else ev.head(limit)
    for r in sub.itertuples(index=False):
        rows.append([
            fmt_day(r.date), pct(r.up_pct), pct(r.prev5_pct), pct(r.dd_prev),
            pct(r.extra_pct) if pd.notna(r.extra_pct) else "—",
            "未再破底" if pd.isna(r.new_low_date) else fmt_day(r.new_low_date),
            "" if pd.isna(r.td_to_new_low) else str(int(r.td_to_new_low)),
        ])
    md_table(dest, ["日期", "單日", "前 5 日", "前一日距峰頂", "之後再漲", "破底日", "撐了（交易日）"], rows)


def md_base_rates(dest: Path, summary_brs: dict, dfs: dict[str, pd.DataFrame]) -> None:
    """Report table: P(new low) and forward returns after the first big up day of
    a cluster, per series and per drawdown depth on the eve."""
    names = {"all": "全部", "15-25%": "−15～−25%", "25-40%": "−25～−40%", "40%+": "−40% 以下"}
    series_label = {"NDX": '<span class="nw">NDX ≥5%</span>',
                    "IXIC": '<span class="nw">綜合指數 ≥4%</span>',
                    "SPX": '<span class="nw">S&P 500 ≥4%</span>',
                    "TAIEX": '<span class="nw">加權指數 ≥3.5%</span>'}

    def plain(v: float | None) -> str:
        return "—" if v is None else f"{v:.0f}%"

    def signed(v: float | None) -> str:
        return "—" if v is None else pct(v)

    rows = []
    for series, br in summary_brs.items():
        for bucket, r in br["by_depth"].items():
            rows.append([
                f"{series_label[series]}，{dfs[series].index[0].year} 年起", names[bucket], str(r["n_250d"]),
                plain(r["p_new_low_20d"]), plain(r["p_new_low_60d"]), plain(r["p_new_low_120d"]),
                plain(r["p_new_low_250d"]), signed(r["median_fwd_60d"]), signed(r["median_fwd_250d"]),
            ])
    md_table(dest, ["系列", "前一日距高點", "波數", "20 日內", "60 日內",
                    "120 日內", "250 日內", "60 日後", "250 日後"], rows)


def md_depth_list(dest: Path, clusters: pd.DataFrame, series: str, lo: float, hi: float) -> None:
    """Report table: past first-of-cluster big up days at a given drawdown depth."""
    sub = clusters[(clusters["series"] == series) & (clusters["dd_prev"] <= lo) & (clusters["dd_prev"] > hi)]
    rows = []
    for r in sub.itertuples(index=False):
        broken = pd.notna(r.new_low_date)
        rows.append([
            fmt_day(r.date), pct(r.up_pct), pct(r.dd_prev),
            f"{fmt_day(r.new_low_date)}破底（{int(r.td_to_new_low)} 個交易日）" if broken
            else ("資料不足" if pd.isna(r.fwd_250) else "未再破底"),
            "" if pd.isna(r.fwd_60) else pct(r.fwd_60),
            "" if pd.isna(r.fwd_250) else pct(r.fwd_250),
        ])
    md_table(dest, ["日期", "單日", "前一日距高點", "之後", "60 日後", "250 日後"], rows)


def show(df: pd.DataFrame, cols: list[str]) -> str:
    """Compact console table: dates as ISO, floats to one decimal."""
    if df.empty:
        return "(none)\n"
    lines = []
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if str(df[c].dtype).startswith(("datetime", "datetimetz")):
                cells.append(f"{fmt_day(v):>10}")
            elif pd.isna(v):
                cells.append(f"{'':>10}")
            elif isinstance(v, (float, np.floating)):
                cells.append(f"{v:>10.1f}")
            else:
                cells.append(f"{str(v):>10}")
        lines.append(" ".join(cells))
    return " ".join(f"{c[:10]:>10}" for c in cols) + "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download prices first")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    raw = load_series(args.refresh)
    dfs = {k: prep(v, k) for k, v in raw.items()}
    log = []

    # ---- current snapshot (raw closes, same convention as the reports) -----
    now = dt.datetime.now()
    snap = {}
    for label in ("NDX", "IXIC", "SPX", "TAIEX", "NVDA"):
        s = raw[label]["close"].astype(float).dropna()
        last = s.index[-1]
        pk = s.loc["2026"].idxmax()
        recent = s.iloc[-6:]
        low_day = recent.idxmin()
        low = float(recent.min())
        before = s.iloc[max(0, s.index.get_loc(low_day) - 5)]
        snap[label] = {
            "last_date": str(last.date()),
            "last_close": round(float(s.iloc[-1]), 2),
            "intraday": bool(label == "TAIEX" and last.date() == now.date()
                             and now.time() < dt.time(13, 45)),
            "low_date": str(low_day.date()),
            "rally_from_low_pct": round((float(s.iloc[-1]) / low - 1) * 100, 2),
            "week_before_low_pct": round((low / float(before) - 1) * 100, 2),
            "peak_date": str(pk.date()),
            "peak_close": round(float(s.loc[pk]), 2),
            "dd_low_pct": round((low / float(s.loc[pk]) - 1) * 100, 2),
            "dd_last_pct": round((float(s.iloc[-1]) / float(s.loc[pk]) - 1) * 100, 2),
        }
    (OUT / "current_snapshot.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- bear windows -------------------------------------------------------
    summary = {"snapshot": snap, "bears": {}, "base_rates": {}, "current": {}}
    state = {}
    for label, (series, peak_window, thr) in BEARS.items():
        df = dfs[series]
        peak, trough = find_bear(df["close"], peak_window)
        ev = event_table(df, thr)
        # keep the year after the trough too: the first big up day that is NOT
        # followed by a new low is the bottom signal this study is looking for
        win = between(ev, peak, trough + pd.DateOffset(months=12))
        win["in_bear"] = win["date"] < trough
        if series == "NDX":       # the Composite figure is the one news reports cite
            ixic = dfs["IXIC"]["close"]
            win["ixic_same_day_pct"] = (ixic.reindex(win["date"]).to_numpy()
                                        / ixic.shift(1).reindex(win["date"]).to_numpy() - 1) * 100
        key = label.split()[0].lower()
        to_csv(win, OUT / f"{key}_big_up_days.csv")
        bear = win[win["in_bear"]]
        clu = cluster_table(df, bear)
        to_csv(clu, OUT / f"{key}_clusters.csv")
        epi = episode_table(df["close"], peak, trough, win)
        to_csv(epi, OUT / f"{key}_rally_episodes.csv")
        state[key] = (df, win, peak, trough)
        if series == "NDX":
            md_clusters(OUT / "ndx_clusters.md", clu)
            md_episodes(OUT / "ndx_episodes.md", epi)
        elif series == "TAIEX":
            md_clusters(OUT / "taiex_clusters.md", clu)
            md_episodes(OUT / "taiex_episodes.md", epi)
        else:
            md_big_days(OUT / "csco_big_up_days.md", bear)
        bottom_days = win[~win["in_bear"]]
        summary["bears"][label] = {
            "series": series, "threshold_pct": thr,
            "peak_date": str(peak.date()), "peak_close": round(float(df["close"].loc[peak]), 2),
            "trough_date": str(trough.date()), "trough_close": round(float(df["close"].loc[trough]), 2),
            "trough_dd_pct": round(float(df["dd"].loc[trough]), 2),
            "n_big_days_in_bear": int(len(bear)),
            "n_followed_by_new_low": int(bear["new_low_date"].notna().sum()),
            "n_clusters_in_bear": int(bear["first_of_cluster"].sum()),
            "median_extra_pct": round(float(bear["extra_pct"].median()), 2),
            "median_td_to_new_low": float(bear["td_to_new_low"].median()),
            "median_cluster_extra_pct": round(float(clu["extra_pct"].median()), 2),
            "median_cluster_td_to_new_low": float(clu["td_to_new_low"].median()),
            "n_clusters_broken_within_20d": int((clu["td_to_new_low"] <= 20).sum()),
            "n_clusters_broken_within_60d": int((clu["td_to_new_low"] <= 60).sum()),
            "n_clusters_broken_within_120d": int((clu["td_to_new_low"] <= 120).sum()),
            "max_cluster_gain_pct": round(float((clu["extra_pct"] + clu["first_up_pct"]).max()), 2),
            "max_extra_pct": round(float(bear["extra_pct"].max()), 2),
            "n_episodes_ge_10pct": int(len(epi)),
            "n_episodes_broken": int(epi["new_low_date"].notna().sum()),
            "first_big_day_after_trough": fmt_day(bottom_days["date"].iloc[0]) if len(bottom_days) else None,
            "first_big_day_after_trough_up_pct": round(float(bottom_days["up_pct"].iloc[0]), 2)
            if len(bottom_days) else None,
            # size alone does not mark the bottom: how many FAILED days rose more?
            "n_failed_days_with_larger_gain_than_bottom_day":
                int((bear["up_pct"] > bottom_days["up_pct"].iloc[0]).sum()) if len(bottom_days) else None,
            "largest_big_day": fmt_day(bear.loc[bear["up_pct"].idxmax(), "date"]),
            "largest_big_day_pct": round(float(bear["up_pct"].max()), 2),
        }
        log.append(f"\n=== {label}: big up days (>= {thr:g}%) ===\n")
        log.append(show(win, ["date", "close", "up_pct", "prev5_pct", "dd_prev", "dd_post", "extra_pct",
                              "td_to_new_low", "new_low_date", "new_low_dd", "fwd_5", "fwd_20", "fwd_60",
                              "fwd_250", "in_bear"]))
        log.append(f"\n=== {label}: clusters of big up days (measured from the first big day) ===\n")
        log.append(show(clu, ["first_date", "first_up_pct", "dd_eve_pct", "n_big_days", "biggest_date",
                              "biggest_pct", "peak_date", "extra_pct", "new_low_date", "td_to_new_low",
                              "new_low_dd"]))
        log.append(f"\n=== {label}: rally episodes (zig-zag >= {ZIGZAG_THETA:g}%) ===\n")
        log.append(show(epi, ["low_date", "low_dd", "high_date", "high_dd", "gain_pct", "td_low_to_high",
                              "n_big_days", "biggest_day", "biggest_day_pct", "new_low_date",
                              "td_high_to_new_low"]))

    ndx_df, ndx_win, ndx_peak, ndx_trough = state["ndx"]
    fig_marked(ndx_df["close"], ndx_win, ndx_peak, ndx_trough, 5.0, 8.0,
               ("1999-01-01", "2003-12-31"), ("1999-11-01", "2003-04-30"),
               (1000, 1500, 2000, 3000, 4000, 5000), "NDX 2000–2002 崩盤期：跌勢中的大漲",
               FIGS / "ndx_dotcom_big_up_days.png")
    fig_fan(ndx_df["close"], ndx_win[ndx_win["in_bear"] & (ndx_win["up_pct"] >= 6.0)],
            FIGS / "ndx_dotcom_forward_paths.png")
    tw_df, tw_win, tw_peak, tw_trough = state["taiex"]
    fig_marked(tw_df["close"], tw_win, tw_peak, tw_trough, 3.5, 4.5,
               ("1999-01-01", "2002-12-31"), ("1999-11-01", "2002-04-30"),
               (4000, 5000, 6000, 8000, 10000), "加權指數 2000–2001 崩盤期：跌勢中的大漲",
               FIGS / "taiex_dotcom_big_up_days.png")

    # ---- robustness: does the answer depend on the big-day threshold? --------
    rob_rows, fwd_rows = [], []
    for label, (series, peak_window, _) in BEARS.items():
        df = dfs[series]
        peak, trough = find_bear(df["close"], peak_window)
        for thr in (3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
            ev = between(event_table(df, thr), peak, trough)
            if ev.empty:
                continue
            cl = cluster_table(df, ev)
            td = cl["td_to_new_low"]
            rob_rows.append([
                label.replace(" ", " "), f"{thr:g}%", str(len(ev)), str(int(ev["new_low_date"].notna().sum())), str(len(cl)),
                str(int(cl["new_low_date"].notna().sum())), str(int((td > 20).sum())), str(int((td > 60).sum())),
                str(int((td > 120).sum())),
            ])
    md_table(OUT / "robustness.md", ["標的", "門檻", "大漲日", "其中再破底", "波數",
                                     "其中再破底", "撐逾 20 日", "撐逾 60 日", "撐逾 120 日"], rob_rows)
    ndx_bear = ndx_win[ndx_win["in_bear"]]
    for name, sub in [("全部大漲日", ndx_bear), ("每波的第一個大漲日", ndx_bear[ndx_bear["first_of_cluster"]])]:
        q = sub[["fwd_5", "fwd_20", "fwd_60", "fwd_120", "fwd_250"]].quantile([0.25, 0.5, 0.75])
        for qq, lab in [(0.25, "25 分位"), (0.5, "中位數"), (0.75, "75 分位")]:
            fwd_rows.append([f'<span class="nw">{name}</span>', lab] + [pct(v) for v in q.loc[qq]])
    md_table(OUT / "ndx_forward_returns.md",
             ["樣本", "統計量", "5 日後", "20 日後", "60 日後", "120 日後", "250 日後"], fwd_rows)

    # calendar dates of the live rally's checkpoints (US holiday calendar)
    us_cal = pd.offsets.CustomBusinessDay(calendar=USFederalHolidayCalendar())
    last_ndx = dfs["NDX"].index[-1]
    summary["checkpoints"] = {f"ndx_plus_{h}td": str((last_ndx + h * us_cal).date()) for h in (20, 60, 120)}

    # ---- cross-history base rates ------------------------------------------
    cluster_rows = []
    for series in ("NDX", "IXIC", "SPX", "TAIEX"):
        br, cl = base_rates(dfs[series], BASE_RATE_THR[series])
        summary["base_rates"][series] = br
        log.append(f"\n=== base rates {series} (dd <= {MIN_DD:g}% on the eve, day >= {BASE_RATE_THR[series]:g}%) ===\n")
        log.append(json.dumps(br, ensure_ascii=False, indent=1) + "\n")
        if not cl.empty:
            cl = cl.assign(series=series)
            cluster_rows.append(cl)
            log.append(show(cl, ["date", "up_pct", "prev5_pct", "dd_prev", "dd_post", "extra_pct",
                                 "td_to_new_low", "new_low_date", "new_low_dd", "fwd_60", "fwd_250"]))
    clusters = pd.concat(cluster_rows, ignore_index=True)
    cols = ["series", "date", "up_pct", "prev5_pct", "dd_prev", "dd_post", "extra_pct", "extra_peak_date",
            "new_low_date", "td_to_new_low", "new_low_dd", "fwd_5", "fwd_20", "fwd_60", "fwd_120", "fwd_250"]
    to_csv(clusters[cols], OUT / "base_rate_clusters.csv")
    md_base_rates(OUT / "base_rates.md", summary["base_rates"], dfs)
    for series in ("NDX", "IXIC", "SPX"):
        md_depth_list(OUT / f"depth_15_25_{series.lower()}.md", clusters, series, -MIN_DD, -25.0)

    # ---- where does the live rally sit in this framework? -------------------
    live_thr = dict(BASE_RATE_THR, NVDA=10.0)
    for series, thr in live_thr.items():
        ev = event_table(dfs[series], thr)
        last_day = dfs[series].index[-1]
        row = ev[ev["date"] == last_day]
        if row.empty:
            summary["current"][series] = {"date": str(last_day.date()), "is_big_day": False}
            continue
        first = ev[(ev["date"] <= last_day) & ev["first_of_cluster"]].iloc[-1]
        r = row.iloc[0]
        summary["current"][series] = {
            "date": str(last_day.date()), "is_big_day": True,
            "up_pct": round(float(r["up_pct"]), 2),
            "prev5_pct": round(float(r["prev5_pct"]), 2),
            "dd_eve_pct": round(float(r["dd_prev"]), 2),
            "dd_post_pct": round(float(r["dd_post"]), 2),
            "depth_bucket": depth_bucket(float(r["dd_prev"])),
            "deep_enough_for_base_rate": bool(r["dd_prev"] <= -MIN_DD),
            "first_of_cluster": bool(r["first_of_cluster"]),
            "cluster_first_date": fmt_day(first["date"]),
            "cluster_first_up_pct": round(float(first["up_pct"]), 2),
        }
    log.append("\n=== current event in the event-study framework ===\n")
    log.append(json.dumps(summary["current"], ensure_ascii=False, indent=1) + "\n")

    # ---- leader stock: NVDA's largest one-day gains on record ---------------
    nvda_ev = event_table(dfs["NVDA"], 8.0).sort_values("up_pct", ascending=False)
    to_csv(nvda_ev.head(15), OUT / "nvda_largest_up_days.csv")
    log.append("\n=== NVDA largest one-day gains on record (>= 8%) ===\n")
    log.append(show(nvda_ev.head(15), ["date", "close", "up_pct", "prev5_pct", "dd_prev", "extra_pct",
                                       "td_to_new_low", "new_low_date", "fwd_60", "fwd_250"]))

    text = json.dumps({"snapshot": snap, "bears": summary["bears"]}, ensure_ascii=False, indent=1) + "\n"
    text += "".join(log)
    (OUT / "console.txt").write_text(text, encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
