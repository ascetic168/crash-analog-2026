# -*- coding: utf-8 -*-
"""Statistical layer: GSY (Bubbles-for-Fama) variables for the AI sector basket
and LPPL (log-periodic power law) fits with an out-of-sample validation on the
1999 NDX bubble.

GSY (Greenwood-Shleifer-You 2019, JFE) crash-prediction variables, computed
objectively where free data allow:
  1. run-up   : 2-year return of the sector basket at its recent peak
  2. slope    : share of the run-up realised in the last 8 months (acceleration)
  3. valuation: CAPE expansion over the same window (market-level proxy) +
                cited sector multiples (Slok/Goldman) - documented separately
  4. issuance : 2026 IPO pipeline ~12% of GDP vs 1999 ~6% (cited: Hussman)
  5. profitability: cited (NVDA revenue +106% y/y) - GSY find HIGH profitability
                growth RAISES crash probability

LPPL: ln P(t) = A + B tau^m + C tau^m cos(w ln tau + phi), tau = tc - t.
Fitting recipe (standard): for each (m, w) cell on a grid inside the LPPLS
admissible ranges, the model is linear in (A, B, C1, C2) and nonlinear only in
tc -> minimize SSE over tc with a 1-D bounded optimizer. Refine the best cells
with least_squares over all 7 parameters (bounded to admissible ranges).
Qualification: 0.1<=m<=0.9, 4.2<=w<=10.5, B<0 (super-exponential), |B|>=0.05,
and LPPL RMSE at least 2% better than the best pure power law A+B tau^m.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize_scalar

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
DL = DATA / "downloads"
OUT = HERE.parent / "output"
FIGS = OUT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

# ================================================================ 1) GSY basket
BASKET = {  # AI/tech sector basket, dot-com analogs included
    "ai_infra": ["NVDA", "AMD", "AVGO", "TSM", "MU", "MRVL", "SMCI", "ORCL"],
    "hyperscaler": ["MSFT", "META", "AMZN"],
    "full_ai": ["NVDA", "AMD", "AVGO", "TSM", "MU", "MRVL", "SMCI", "ORCL",
                "MSFT", "META", "AMZN", "PLTR", "INTC"],
    "dotcom_1999_cisco": ["CSCO"],  # reference
}


def load_close(sym: str) -> pd.Series:
    df = pd.read_csv(DL / f"yahoo_{sym.lower()}.csv", parse_dates=["date"])
    return df.set_index("date")["close"].sort_index()


def basket_stats(symbols: list[str], peak_date: str) -> dict:
    """Equal-$ basket (buy each name at window start), 2y return and 8m slope
    measured on unadjusted closes at the basket's peak close date."""
    start = (pd.Timestamp(peak_date) - pd.DateOffset(years=2))
    start8 = (pd.Timestamp(peak_date) - pd.DateOffset(months=8))
    norm = {}
    for s in symbols:
        px = load_close(s)
        if px.index[0] > start:   # skip names without full 2y history
            continue
        norm[s] = px.loc[start:peak_date] / px.asof(start)
    df = pd.DataFrame(norm).dropna(how="all").ffill()
    bkt = df.mean(axis=1, skipna=True).dropna()
    peak = bkt.idxmax()
    b2y = float(bkt.iloc[-1] / bkt.iloc[0] - 1)
    slope = ((bkt.asof(peak) - bkt.asof(start8)) / (bkt.asof(peak) - bkt.iloc[0])
             if bkt.iloc[0] < bkt.asof(peak) else np.nan)
    return {"peak_basket_date": str(peak.date()), "ret_2y_pct": round(100 * b2y, 1),
            "slope_8m": round(float(slope), 3), "passes_100pct": bool(b2y >= 1.0),
            "n_names": len(norm), "names": sorted(norm)}


gsy_basket = {k: basket_stats(v, "2026-10-06") for k, v in BASKET.items()}

# ================================================================ 2) LPPL
def _ols(t: np.ndarray, y: np.ndarray, tc: float, m: float, w: float):
    tau = tc - t
    if tau.min() <= 1e-4:
        return None
    p = tau ** m
    X = np.column_stack([np.ones_like(t), p, p * np.cos(w * np.log(tau)), p * np.sin(w * np.log(tau))])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    return coef, float(resid @ resid)


def cell_sse(t, y, m, w, tc_hi):
    """Best SSE for a fixed (m, w) over tc in [t_end + 0.02, tc_hi]."""
    lo = t[-1] + 0.02

    def sse(tc):
        r = _ols(t, y, tc, m, w)
        return r[1] if r else 1e9

    res = minimize_scalar(sse, bounds=(lo, tc_hi), method="bounded",
                          options={"xatol": 1e-4})
    coef, s = _ols(t, y, res.x, m, w)
    return {"tc": float(res.x), "m": float(m), "w": float(w),
            "coef": [float(c) for c in coef], "sse": float(s)}


def lppl_fit_window(t: np.ndarray, y: np.ndarray, tc_hi: float = 1.5) -> list[dict]:
    """Fit over the admissible (m, w) grid; refine top cells; return all fits."""
    cells = []
    for m in np.arange(0.10, 0.901, 0.025):
        for w in np.arange(4.2, 10.51, 0.3):
            cells.append(cell_sse(t, y, m, w, tc_hi))
    cells.sort(key=lambda c: c["sse"])
    refined = []
    for c in cells[:15]:
        A, B, C1, C2 = c["coef"]

        def resid(params):
            A, B, C1, C2, tc_, m_, w_ = params
            tau = tc_ - t
            if tau.min() <= 1e-4:
                return np.full_like(t, 1e6)
            p = tau ** m_
            model = A + B * p + C1 * p * np.cos(w_ * np.log(tau)) + C2 * p * np.sin(w_ * np.log(tau))
            return y - model

        p0 = [A, B, C1, C2, c["tc"], c["m"], c["w"]]
        try:
            res = least_squares(resid, p0, method="trf",
                                bounds=([-np.inf, -np.inf, -np.inf, -np.inf, t[-1] + 0.01, 0.10, 4.2],
                                        [np.inf, np.inf, np.inf, np.inf, tc_hi, 0.90, 10.5]))
            A, B, C1, C2, tc_, m_, w_ = res.x
            rmse = float(np.sqrt(np.mean(res.fun ** 2)))
        except Exception:
            A, B, C1, C2, tc_, m_, w_ = p0
            rmse = float(np.sqrt(c["sse"] / len(t)))
        refined.append({"A": float(A), "B": float(B), "C1": float(C1), "C2": float(C2),
                        "tc": float(tc_), "m": float(m_), "w": float(w_), "rmse": rmse})
    return refined


def pure_power_rmse(t: np.ndarray, y: np.ndarray, tc_hi: float | None = None) -> float:
    tc_hi = tc_hi if tc_hi is not None else t[-1] + 1.5
    lo = t[-1] + 0.02

    def sse_pair(tc, m):
        tau = tc - t
        p = tau ** m
        X = np.column_stack([np.ones_like(t), p])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ coef
        return float(r @ r)

    best = np.inf
    for m in np.arange(0.10, 0.901, 0.05):
        res = minimize_scalar(lambda tc: sse_pair(tc, m), bounds=(lo, tc_hi),
                              method="bounded", options={"xatol": 1e-4})
        best = min(best, res.fun)
    return float(np.sqrt(best / len(t)))


def qualifies(f: dict, t: np.ndarray, y: np.ndarray) -> bool:
    if abs(f["B"]) < 0.05 or f["B"] > 0:      # need meaningful super-exponential growth
        return False
    return f["rmse"] <= pure_power_rmse(t, y) * 0.98


def lppl_windows(sym: str, windows: list[tuple[str, str]], label: str) -> list[dict]:
    df = pd.read_csv(DL / f"yahoo_{sym.lower()}.csv", parse_dates=["date"])
    px = df.set_index("date")["close"].sort_index()
    out = []
    for lo, hi in windows:
        seg = px.loc[lo:hi].dropna()
        t1, t2 = seg.index[0], seg.index[-1]
        t = ((seg.index - t1).days / 365.25).values
        y = np.log(seg.values)
        fits = lppl_fit_window(t, y, tc_hi=t[-1] + 1.5)
        qual = [f for f in fits if qualifies(f, t, y)]
        tc_dates = [t1 + pd.Timedelta(days=f["tc"] * 365.25) for f in qual]
        tc_sorted = sorted(str(d.date()) for d in tc_dates)
        out.append({
            "symbol": sym, "label": label, "start": str(t1.date()), "end": str(t2.date()),
            "n_days": len(seg), "n_qualifying": len(qual),
            "tc_qualifying_dates": tc_sorted,
            "tc_median": str(pd.Series(pd.to_datetime(tc_dates)).median().date()) if tc_dates else None,
            "best_fit": sorted(fits, key=lambda f: f["rmse"])[0],
            "best_qualifying_fit": sorted(qual, key=lambda f: f["rmse"])[0] if qual else None,
        })
    return out


def lppls_confidence(sym: str, start: str, n_ends: int = 18, step_days: int = 7,
                     tc_target_days: int = 190) -> dict:
    """LPPLS-style confidence indicator: fit on many overlapping windows (ends
    stepped back from today), collect the best qualifying tc per window, and
    report the tc distribution within tc_target_days after each window end."""
    df = pd.read_csv(DL / f"yahoo_{sym.lower()}.csv", parse_dates=["date"])
    px = df.set_index("date")["close"].sort_index()
    last = px.index[-1]
    ends = [last - pd.Timedelta(days=step_days * k) for k in range(n_ends)]
    recs = []
    for e in ends:
        seg = px.loc[start:e].dropna()
        if len(seg) < 250:
            continue
        t1 = seg.index[0]
        t = ((seg.index - t1).days / 365.25).values
        y = np.log(seg.values)
        fits = lppl_fit_window(t, y, tc_hi=t[-1] + 1.2)
        qual = [f for f in fits if qualifies(f, t, y)]
        if not qual:
            continue
        best = sorted(qual, key=lambda f: f["rmse"])[0]
        recs.append({
            "end": str(e.date()),
            "tc_date": str((t1 + pd.Timedelta(days=best["tc"] * 365.25)).date()),
            "m": round(best["m"], 3), "w": round(best["w"], 3), "B": round(best["B"], 3),
            "rmse": round(best["rmse"], 5),
            "tc_ahead_days": int(((t1 + pd.Timedelta(days=best["tc"] * 365.25)) - e).days)})
    if not recs:
        return {"n_windows": 0, "n_qualifying": 0, "tc_dates": []}
    tcs = pd.to_datetime([r["tc_date"] for r in recs])
    # confidence = share of qualifying fits whose tc lands within the target horizon
    horizon = pd.Timestamp(recs[-1]["end"]) + pd.Timedelta(days=tc_target_days)
    conf = float(((tcs >= pd.Timestamp(recs[-1]["end"])) & (tcs <= horizon)).mean())
    return {"n_windows": n_ends, "n_qualifying": len(recs),
            "confidence_within_6m": round(conf, 2),
            "tc_counts": {k: int(v) for k, v in tcs.strftime("%Y-%m").value_counts().sort_index().items()},
            "detail": recs}


results = {"gsy_basket": gsy_basket}

# --- validation: NDX 1997-2000 (tc known ex post: 2000-03-27 close peak)
results["lppl_validation_ndx1999"] = lppl_windows("ndx", [
    ("1997-01-01", "1999-03-31"),
    ("1997-01-01", "1999-06-30"),
    ("1997-01-01", "1999-09-30"),
    ("1997-01-01", "1999-12-31"),
    ("1997-01-01", "2000-03-27"),  # hindsight full window
], "NDX 1997-2000 validation (true peak 2000-03-27)")

# --- application: current situation
results["lppl_ndx_2026"] = lppl_windows("ndx", [
    ("2023-01-03", "2026-10-06"),  # up to the peak (peak date known ex post)
    ("2023-01-03", "2026-11-06"),  # live
    ("2024-06-01", "2026-11-06"),
], "NDX 2026")

results["lppl_nvda_2026"] = lppl_windows("nvda", [
    ("2022-10-14", "2026-11-06"),  # from the 2022 bottom
    ("2024-06-01", "2026-11-06"),
], "NVDA 2026")

results["lppls_confidence"] = {
    "NDX": lppls_confidence("ndx", "2023-01-03"),
    "NVDA": lppls_confidence("nvda", "2023-06-01"),
    "TAIEX": lppls_confidence("twii", "2023-01-03"),
}

results["lppl_twii_2026"] = lppl_windows("twii", [
    ("2023-01-03", "2026-11-06"),
    ("2024-06-01", "2026-11-06"),
], "TAIEX 2026")

# ================================================================ charts
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_fit(sym: str, lo: str, hi: str, fit: dict, fname: str, title: str):
    df = pd.read_csv(DL / f"yahoo_{sym.lower()}.csv", parse_dates=["date"])
    px = df.set_index("date")["close"].sort_index()
    seg = px.loc[lo:hi].dropna()
    t1 = seg.index[0]
    t = ((seg.index - t1).days / 365.25).values
    tau = np.clip(fit["tc"] - t, 1e-4, None)
    p = tau ** fit["m"]
    model = fit["A"] + fit["B"] * p + fit["C1"] * p * np.cos(fit["w"] * np.log(tau)) + \
        fit["C2"] * p * np.sin(fit["w"] * np.log(tau))
    t_ext = np.linspace(t[0], fit["tc"] - 0.01, 500)  # stop before the singularity
    tau_e = fit["tc"] - t_ext
    pe = tau_e ** fit["m"]
    model_ext = fit["A"] + fit["B"] * pe + fit["C1"] * pe * np.cos(fit["w"] * np.log(tau_e)) + \
        fit["C2"] * pe * np.sin(fit["w"] * np.log(tau_e))
    tc_date = t1 + pd.Timedelta(days=fit["tc"] * 365.25)
    dates_ext = pd.to_datetime([t1 + pd.Timedelta(days=x * 365.25) for x in t_ext])
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(seg.index, seg.values, "k-", lw=1.0, label=f"{sym} close")
    ax.plot(dates_ext, np.exp(model_ext), "r-", lw=1.4, label="LPPL fit")
    ax.axvline(tc_date, color="tab:orange", ls="--", lw=1.2, label=f"tc = {tc_date:%Y-%m-%d}")
    ax.axvline(seg.index[-1], color="gray", ls=":", lw=1.0, label="data end")
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.set_title(title)
    ax.legend(fontsize=8); ax.grid(alpha=0.25, which="both")
    fig.tight_layout(); fig.savefig(FIGS / fname, dpi=150); plt.close(fig)


plot_fit("ndx", "1997-01-01", "2000-03-27",
         results["lppl_validation_ndx1999"][4]["best_qualifying_fit"]
         or results["lppl_validation_ndx1999"][4]["best_fit"],
         "lppl_ndx1999.png", "LPPL validation on NDX 1997-2000 (true crash 2000-03-27)")
plot_fit("ndx", "2023-01-03", "2026-11-06",
         results["lppl_ndx_2026"][1]["best_qualifying_fit"] or results["lppl_ndx_2026"][1]["best_fit"],
         "lppl_ndx2026.png", "LPPL fit: NDX 2023-2026 (live)")
plot_fit("nvda", "2022-10-14", "2026-11-06",
         results["lppl_nvda_2026"][0]["best_qualifying_fit"] or results["lppl_nvda_2026"][0]["best_fit"],
         "lppl_nvda2026.png", "LPPL fit: NVDA 2022-2026 (live)")

# ================================================================ save
def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return float(o)
    return o

(OUT / "stats_layer.json").write_text(json.dumps(_clean(results), indent=2, ensure_ascii=False))

print("=== LPPLS confidence (rolling windows) ===")
for k, v in results["lppls_confidence"].items():
    print(f"  {k}: qual {v['n_qualifying']}/{v['n_windows']}  conf<=6m {v.get('confidence_within_6m')}  tc by month: {v.get('tc_counts')}")

print("=== GSY basket run-ups (equal-$, measured at 2026-10-06) ===")
for k, v in gsy_basket.items():
    print(f"  {k:<20} 2y={v['ret_2y_pct']:>7.1f}%  slope8m={v['slope_8m']:>5.2f}  >=100%: {v['passes_100pct']}  n={v['n_names']}")

for key in ("lppl_validation_ndx1999", "lppl_ndx_2026", "lppl_nvda_2026", "lppl_twii_2026"):
    print(f"\n=== LPPL: {key} ===")
    for w in results[key]:
        bf = w["best_fit"]
        bqw = w["best_qualifying_fit"]
        tc_date = pd.Timestamp(w["start"]) + pd.Timedelta(days=bf["tc"] * 365.25)
        tcq = (pd.Timestamp(w["start"]) + pd.Timedelta(days=bqw["tc"] * 365.25)).date() if bqw else None
        print(f"  {w['start']} -> {w['end']}  qual={w['n_qualifying']:<3} tc_best={tc_date.date()} tc_qual={tcq}")
        print(f"      best:      m={bf['m']:.2f} w={bf['w']:.2f} B={bf['B']:.3f} rmse={bf['rmse']:.4f}")
        if bqw:
            print(f"      qualifying: tc={tcq} m={bqw['m']:.2f} w={bqw['w']:.2f} B={bqw['B']:.3f} rmse={bqw['rmse']:.4f}")
