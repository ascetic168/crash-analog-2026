# -*- coding: utf-8 -*-
"""Follow-up statistical layer for the 2026-11-21 update report.

Same LPPL machinery as build_stats_layer.py (11/8 original, preserved
unchanged), re-run with data through 2026-11-20, plus:

  1. NORMALIZED CHARTS — every LPPL chart is drawn in "% from the episode's
     own peak close" (drawdown space) instead of absolute index levels.
     Rationale: different historical eras have completely different index
     levels (NDX 1999 peaked ~4,700; NDX 2026 peaked ~31,000), so absolute
     axes cannot be compared across eras; distance-from-peak makes them
     directly comparable. The 1999 validation chart and the 2026 live chart
     now share identical y-axis units and limits.

  2. GSY basket drawdown check — has the AI-infrastructure basket crossed
     the -40% GSY crash threshold as of 2026-11-20?

Outputs -> ../output_update/ (original ../output/ is frozen evidence).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize_scalar

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
DL = DATA / "downloads"
OUT = HERE.parent / "output_update"
FIGS = OUT / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

AS_OF = "2026-11-20"
PEAK = "2026-10-06"

# ================================================================ 1) GSY basket
BASKET = {
    "ai_infra": ["NVDA", "AMD", "AVGO", "TSM", "MU", "MRVL", "SMCI", "ORCL"],
    "hyperscaler": ["MSFT", "META", "AMZN"],
    "full_ai": ["NVDA", "AMD", "AVGO", "TSM", "MU", "MRVL", "SMCI", "ORCL",
                "MSFT", "META", "AMZN", "PLTR", "INTC"],
}


def load_close(sym: str) -> pd.Series:
    df = pd.read_csv(DL / f"yahoo_{sym.lower()}.csv", parse_dates=["date"])
    return df.set_index("date")["close"].sort_index()


def basket_stats(symbols: list[str], peak_date: str) -> dict:
    """Equal-$ basket: run-up at the 10/06 peak (same as the 11/8 report) and
    the drawdown of the basket from its own peak through AS_OF."""
    start = (pd.Timestamp(peak_date) - pd.DateOffset(years=2))
    norm = {}
    for s in symbols:
        px = load_close(s)
        if px.index[0] > start:
            continue
        norm[s] = px / px.asof(start)
    df = pd.DataFrame(norm).dropna(how="all").ffill()
    bkt = df.mean(axis=1, skipna=True).dropna()
    seg = bkt.loc[peak_date:]
    b_peak = float(bkt.asof(pd.Timestamp(peak_date)))
    b_now = float(bkt.iloc[-1])
    b_min = float(seg.min())
    b2y = float(bkt.asof(pd.Timestamp(peak_date)) / bkt.asof(start) - 1)
    return {"ret_2y_at_peak_pct": round(100 * b2y, 1),
            "basket_peak_date": str(bkt.loc[:peak_date].idxmax().date()),
            "basket_dd_from_1006_peak_pct": round(100 * (b_now / b_peak - 1), 1),
            "basket_dd_max_since_peak_pct": round(100 * (b_min / b_peak - 1), 1),
            "basket_dd_latest_date": str(seg.idxmin().date()),
            "crossed_minus40": bool(b_min / b_peak - 1 <= -0.40),
            "n_names": len(norm)}


gsy_update = {k: basket_stats(v, PEAK) for k, v in BASKET.items()}

# ================================================================ 2) LPPL core (same as original)
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
    if abs(f["B"]) < 0.05 or f["B"] > 0:
        return False
    return f["rmse"] <= pure_power_rmse(t, y) * 0.98


def lppl_windows(sym: str, windows: list[tuple[str, str]], label: str) -> list[dict]:
    px = load_close(sym)
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
    px = load_close(sym)
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
    horizon = pd.Timestamp(recs[-1]["end"]) + pd.Timedelta(days=tc_target_days)
    conf = float(((tcs >= pd.Timestamp(recs[-1]["end"])) & (tcs <= horizon)).mean())
    return {"n_windows": n_ends, "n_qualifying": len(recs),
            "confidence_within_6m": round(conf, 2),
            "tc_counts": {k: int(v) for k, v in tcs.strftime("%Y-%m").value_counts().sort_index().items()},
            "detail": recs}


results = {"as_of": AS_OF, "gsy_basket_update": gsy_update}

# --- validation: NDX 1997-2000 (tc known ex post: 2000-03-27 close peak)
results["lppl_validation_ndx1999"] = lppl_windows("ndx", [
    ("1997-01-01", "1999-03-31"),
    ("1997-01-01", "1999-06-30"),
    ("1997-01-01", "1999-09-30"),
    ("1997-01-01", "1999-12-31"),
    ("1997-01-01", "2000-03-27"),
], "NDX 1997-2000 validation (true peak 2000-03-27)")

# --- application: live windows through AS_OF
results["lppl_ndx_2026"] = lppl_windows("ndx", [
    ("2023-01-03", PEAK),
    ("2023-01-03", AS_OF),
    ("2024-06-01", AS_OF),
], "NDX 2026")

results["lppl_nvda_2026"] = lppl_windows("nvda", [
    ("2022-10-14", AS_OF),
    ("2024-06-01", AS_OF),
], "NVDA 2026")

results["lppls_confidence"] = {
    "NDX": lppls_confidence("ndx", "2023-01-03"),
    "NVDA": lppls_confidence("nvda", "2023-06-01"),
    "TAIEX": lppls_confidence("twii", "2023-01-03"),
}

results["lppl_twii_2026"] = lppl_windows("twii", [
    ("2023-01-03", AS_OF),
    ("2024-06-01", AS_OF),
], "TAIEX 2026")

# ================================================================ charts (normalized: % from peak)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# CJK-capable font for the Chinese chart titles; unicode_minus keeps the minus sign
matplotlib.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


def plot_fit_norm(sym: str, lo: str, hi: str, fit: dict, fname: str, title: str,
                  peak_date: str, ylim: tuple[float, float] | None = None,
                  ax: plt.Axes | None = None, show_labels: bool = True):
    """Data + LPPL fit both drawn as % from the episode's own peak close."""
    px = load_close(sym)
    seg = px.loc[lo:hi].dropna()
    t1 = seg.index[0]
    t = ((seg.index - t1).days / 365.25).values
    p_peak = float(px.asof(pd.Timestamp(peak_date)))

    tau = np.clip(fit["tc"] - t, 1e-4, None)
    p = tau ** fit["m"]
    model = fit["A"] + fit["B"] * p + fit["C1"] * p * np.cos(fit["w"] * np.log(tau)) + \
        fit["C2"] * p * np.sin(fit["w"] * np.log(tau))
    t_ext = np.linspace(t[0], fit["tc"] - 0.01, 500)
    tau_e = fit["tc"] - t_ext
    pe = tau_e ** fit["m"]
    model_ext = fit["A"] + fit["B"] * pe + fit["C1"] * pe * np.cos(fit["w"] * np.log(tau_e)) + \
        fit["C2"] * pe * np.sin(fit["w"] * np.log(tau_e))
    tc_date = t1 + pd.Timedelta(days=fit["tc"] * 365.25)
    dates_ext = pd.to_datetime([t1 + pd.Timedelta(days=x * 365.25) for x in t_ext])

    data_dd = (seg.values / p_peak - 1) * 100
    fit_dd = (np.exp(model_ext) / p_peak - 1) * 100

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(seg.index, data_dd, "k-", lw=1.0, label=f"{sym.upper()} 距峰頂 %" if show_labels else None)
    ax.plot(dates_ext, fit_dd, "r-", lw=1.4, label="LPPL 擬合" if show_labels else None)
    ax.axvline(tc_date, color="tab:orange", ls="--", lw=1.2,
               label=f"tc = {tc_date:%Y-%m-%d}" if show_labels else None)
    ax.axvline(seg.index[-1], color="gray", ls=":", lw=1.0,
               label="資料末端" if show_labels else None)
    ax.axhline(0, color="k", lw=0.5, alpha=0.5)
    ax.axhline(-40, color="tab:red", lw=0.6, ls="--", alpha=0.7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.set_ylabel("距自身峰頂 (%)")
    ax.set_title(title, fontsize=11)
    ax.grid(alpha=0.25)
    if ylim:
        ax.set_ylim(*ylim)
    if show_labels:
        ax.legend(fontsize=8, loc="lower right")
    if standalone:
        fig.tight_layout(); fig.savefig(FIGS / fname, dpi=150); plt.close(fig)


# shared y-limits so the 1999 and 2026 charts are visually comparable
YLIM = (-100, 12)

# 1) validation, 1997-2000, normalized to the TRUE peak 2000-03-27
plot_fit_norm("ndx", "1997-01-01", "2000-03-27",
              results["lppl_validation_ndx1999"][4]["best_qualifying_fit"]
              or results["lppl_validation_ndx1999"][4]["best_fit"],
              "lppl_ndx1999_norm.png",
              "LPPL 驗證：NDX 1997–2000（縱軸＝距 2000-03-27 峰頂 %；橘虛線＝模型估計 tc）",
              peak_date="2000-03-27", ylim=YLIM)

# 2) live NDX, normalized to the 2026-10-06 peak (same y-limits -> comparable)
bf_ndx = results["lppl_ndx_2026"][1]["best_qualifying_fit"] or results["lppl_ndx_2026"][1]["best_fit"]
plot_fit_norm("ndx", "2023-01-03", AS_OF, bf_ndx,
              "lppl_ndx2026_norm.png",
              "LPPL 應用：NDX 2023–2026（縱軸＝距 2026-10-06 峰頂 %，與 1999 圖同刻度）",
              peak_date=PEAK, ylim=YLIM)

# 3) live NVDA
bf_nvda = results["lppl_nvda_2026"][0]["best_qualifying_fit"] or results["lppl_nvda_2026"][0]["best_fit"]
plot_fit_norm("nvda", "2022-10-14", AS_OF, bf_nvda,
              "lppl_nvda2026_norm.png",
              "LPPL 應用：NVDA 2022–2026（縱軸＝距 2026-10-06 峰頂 %）",
              peak_date=PEAK, ylim=YLIM)

# 4) side-by-side comparable panel: 1999 validation vs 2026 live, shared y
fig, axes = plt.subplots(1, 2, figsize=(15, 5.8), sharey=True)
bf99 = results["lppl_validation_ndx1999"][4]["best_qualifying_fit"] or \
    results["lppl_validation_ndx1999"][4]["best_fit"]
plot_fit_norm("ndx", "1997-01-01", "2000-03-27", bf99,
              None, "NDX 1997–2000（事後驗證；峰頂 2000-03-27）",
              peak_date="2000-03-27", ylim=YLIM, ax=axes[0])
plot_fit_norm("ndx", "2023-01-03", AS_OF, bf_ndx,
              None, "NDX 2023–2026（進行中；峰頂 2026-10-06）",
              peak_date=PEAK, ylim=YLIM, ax=axes[1])
fig.suptitle("同一把尺：距各自峰頂的 %——1999 驗證 vs 2026 進行中（紅虛線＝-40% 崩盤線）", fontsize=12)
fig.tight_layout(); fig.savefig(FIGS / "lppl_compare_norm.png", dpi=150); plt.close(fig)

# ================================================================ save
def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return float(o)
    return o


(OUT / "stats_layer_update.json").write_text(
    json.dumps(_clean(results), indent=2, ensure_ascii=False))

print("=== GSY basket update (through %s) ===" % AS_OF)
for k, v in gsy_update.items():
    print(f"  {k:<12} 2y@peak {v['ret_2y_at_peak_pct']:>7.1f}%  dd@{PEAK} {v['basket_dd_from_1006_peak_pct']:>6.1f}%  "
          f"max dd {v['basket_dd_max_since_peak_pct']:>6.1f}% ({v['basket_dd_latest_date']})  crossed-40%: {v['crossed_minus40']}")

print("\n=== LPPLS confidence (rolling windows, through %s) ===" % AS_OF)
for k, v in results["lppls_confidence"].items():
    print(f"  {k}: qual {v['n_qualifying']}/{v['n_windows']}  conf<=6m {v.get('confidence_within_6m')}  tc by month: {v.get('tc_counts')}")

for key in ("lppl_validation_ndx1999", "lppl_ndx_2026", "lppl_nvda_2026", "lppl_twii_2026"):
    print(f"\n=== LPPL: {key} ===")
    for w in results[key]:
        bf = w["best_fit"]
        bqw = w["best_qualifying_fit"]
        tc_date = pd.Timestamp(w["start"]) + pd.Timedelta(days=bf["tc"] * 365.25)
        tcq = (pd.Timestamp(w["start"]) + pd.Timedelta(days=bqw["tc"] * 365.25)).date() if bqw else None
        print(f"  {w['start']} -> {w['end']}  qual={w['n_qualifying']:<3} tc_best={tc_date.date()} tc_qual={tcq}")
        if bqw:
            print(f"      qualifying: m={bqw['m']:.2f} w={bqw['w']:.2f} B={bqw['B']:.3f} rmse={bqw['rmse']:.4f}")
