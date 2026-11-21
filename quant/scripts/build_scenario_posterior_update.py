# -*- coding: utf-8 -*-
"""Follow-up scenario posterior for the 2026-11-21 update report.

Same Dirichlet-over-partition method as build_scenario_posterior.py (11/8
original, preserved unchanged), re-conditioned on the new evidence:

  - E1 (terminal depth never below -15%) is OBSOLETE: NDX closed below the
    -15% line on 2026-11-19 and sits at -19.8% (2026-11-20). The partition
    becomes three-way over E2/E3/E4, renormalized.
  - f1' empirical: NDX episodes that had touched -20% (n=8, all historical;
    the live episode is at -19.84% close, i.e. exactly this cohort's entry
    condition) — outcome distribution over E2/E3/E4.
  - f2' high-CAPE subset of that cohort (n=4).
  - f3' GSY-implied, updated from "prior" to "partly realized": the
    AI-infrastructure basket actually crossed the GSY -40% crash line on
    2026-11-20 (-41.3%), and the key-man tail risk materialized
    (Huang resignation 11/12). The remaining question is conditional:
    given a sector crash in progress, how deep does the INDEX go?
    Historical precedents (sector crash in progress): 2000 -> E4,
    2021-22 -> E3, 1973 -> E4. Baseline f3' = (E2, E3, E4) = (.15, .35, .50).
  - TAIEX / NVDA empirical updates use the -25% touch cohorts (both assets
    crossed -25% in November), live episode excluded from frequencies.
  - Timing: derived from the touch->trough distributions of the relevant
    cohorts + LPPL anchors, mapped to calendar quarters from 2026-11-20.

Outputs -> ../output_update/scenario_posterior_update.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta as Beta

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "output_update"

BOUNDS = ["E2", "E3", "E4"]  # E1 is dead: -15% was crossed on 2026-11-19

cond = json.loads((OUT / "analogs_conditional.json").read_text(encoding="utf-8"))["conditional"]
live = json.loads((OUT / "live_snapshot.json").read_text(encoding="utf-8"))["live"]

LIVE_PEAK = "2026-10-06"


def freq_from_detail(detail, bounds=BOUNDS):
    rows = [r for r in detail if r["peak"] != LIVE_PEAK]
    n = len(rows)
    v = {k: 0.0 for k in bounds}
    for r in rows:
        dd = r["eventual_max_dd"]
        if dd > -25:
            v["E2"] += 1
        elif dd > -40:
            v["E3"] += 1
        else:
            v["E4"] += 1
    return {k: v[k] / n for k in bounds}, n


# ---------------------------------------------------------------- NDX three-way
f1, n1 = freq_from_detail(cond["NDX"]["20"]["detail"])          # touched -20% cohort
hi = [r for r in cond["NDX"]["20"]["detail"]
      if r.get("cape_at_episode_start") and r["cape_at_episode_start"] > 35
      and r["peak"] != LIVE_PEAK]
f2, n2 = freq_from_detail(hi)

# GSY realized -> conditional distribution of index depth given sector crash in progress
# precedents: 2000-03 -> E4 (-82.9%), 2021-11 -> E3 (-35.6%), 1973-01 -> E4 (-48.2%)
f3 = {"E2": 0.15, "E3": 0.35, "E4": 0.50}
f3_low = {"E2": 0.25, "E3": 0.40, "E4": 0.35}   # soft variant: sector crash stays contained
assert abs(sum(f3.values()) - 1) < 1e-9 and abs(sum(f3_low.values()) - 1) < 1e-9

W1, W2, W3 = 0.45, 0.25, 0.30
pooled = {k: W1 * f1[k] + W2 * f2[k] + W3 * f3[k] for k in BOUNDS}
s = sum(pooled.values())
pooled = {k: pooled[k] / s for k in BOUNDS}

K = 24
alpha = {k: K * pooled[k] for k in BOUNDS}
marg = {}
for k in BOUNDS:
    a = alpha[k]
    marg[k] = {"point": round(pooled[k], 4),
               "median": round(float(Beta.ppf(0.50, a, K - a)), 4),
               "q10": round(float(Beta.ppf(0.10, a, K - a)), 4),
               "q90": round(float(Beta.ppf(0.90, a, K - a)), 4)}

a34 = alpha["E3"] + alpha["E4"]
agg = {"p_terminal_le25": {
    "point": round(pooled["E3"] + pooled["E4"], 4),
    "median": round(float(Beta.ppf(0.50, a34, K - a34)), 4),
    "q10": round(float(Beta.ppf(0.10, a34, K - a34)), 4),
    "q90": round(float(Beta.ppf(0.90, a34, K - a34)), 4)}}

# ---------------------------------------------------------------- TAIEX / NVDA (-25% cohorts)
f_taiex, n_taiex = freq_from_detail(cond["TAIEX"]["25"]["detail"])
f_nvda, n_nvda = freq_from_detail(cond["NVDA"]["25"]["detail"])


def _bq(f, k, q):
    a = k * f + 0.5
    b = k * (1 - f) + 0.5
    return round(float(Beta.ppf(q, a, b)), 4)


k_tw = n_taiex + 3  # Jeffreys smoothing sample weight (small n, as original)
marg_taiex = {k: {"point": round(f_taiex[k], 4), "median": _bq(f_taiex[k], k_tw, 0.5),
                  "q10": _bq(f_taiex[k], k_tw, 0.10), "q90": _bq(f_taiex[k], k_tw, 0.90)}
              for k in BOUNDS}
agg["taiex_p_terminal_le40"] = {
    "point": round(f_taiex["E4"], 4),
    "median": _bq(f_taiex["E4"], k_tw, 0.5),
    "q10": _bq(f_taiex["E4"], k_tw, 0.10),
    "q90": _bq(f_taiex["E4"], k_tw, 0.90)}
agg["nvda_p_terminal_le40"] = {
    "point": round(f_nvda["E4"], 4),
    "median": _bq(f_nvda["E4"], n_nvda, 0.5),
    "q10": _bq(f_nvda["E4"], n_nvda, 0.10),
    "q90": _bq(f_nvda["E4"], n_nvda, 0.90)}

# ---------------------------------------------------------------- sensitivity
def pool_with(w3, w1=0.45, w2=None, f3v=None):
    w2 = (1 - w1 - w3) if w2 is None else w2
    f3v = f3v if f3v is not None else f3
    v = {k: w1 * f1[k] + w2 * f2[k] + w3 * f3v[k] for k in BOUNDS}
    s = sum(v.values())
    return {k: v[k] / s for k in BOUNDS}


sens = {
    "pure_empirical (w1=1)": pool_with(0.0, w1=1.0, w2=0.0),
    "baseline (w3=0.30)": pooled,
    "half_GSY (w3=0.15)": pool_with(0.15),
    "GSY_soft (f3'=soft)": pool_with(0.30, f3v=f3_low),
    "pure_GSY (w3=1)": pool_with(1.0, w1=0.0, w2=0.0),
}

# ---------------------------------------------------------------- timing (empirical + LPPL)
def cohort_months(key, depth):
    rows = [r for r in cond[key][str(depth)]["detail"] if r["peak"] != LIVE_PEAK]
    return [float(r["months_to_trough"]) for r in rows]


touch_date = pd.Timestamp(live["NDX"]["last_date"])
cohorts = {
    "NDX_touch20": cohort_months("NDX", 20),
    "TAIEX_touch25": cohort_months("TAIEX", 25),
    "NVDA_touch25": cohort_months("NVDA", 25),
}
pool_m = sorted(cohorts["NDX_touch20"] + cohorts["TAIEX_touch25"] + cohorts["NVDA_touch25"])
qs = {q: float(np.quantile(pool_m, q)) for q in (0.25, 0.50, 0.75)}
cal = {q: str((touch_date + pd.DateOffset(days=int(m * 30.44))).date()) for q, m in qs.items()}

timing = {"2026-12（觸及後~1 個月內，對應 pool 中位數）": 0.40,
          "2027Q1（LPPL TAIEX tc 叢集＋慢崩尾）": 0.40,
          "2027Q2 之後（E 型築底拉長）": 0.20}
assert abs(sum(timing.values()) - 1) < 1e-9

result = {
    "as_of": "2026-11-20",
    "partition_note": "E1 已於 2026-11-19 出局（NDX 收盤首次低於 -15%）；分割改為 E2/E3/E4 三元。",
    "live_conditions": {k: {"drawdown_pct": v["drawdown_pct"],
                            "first_close_at_or_below": v["first_close_at_or_below"]}
                        for k, v in live.items()},
    "streams": {f"f1_NDX_touch20_n{n1}": f1, f"f2_highCAPE_touch20_n{n2}": f2,
                "f3_GSY_realized": f3, "f3_soft_variant": f3_low},
    "weights": {"f1": W1, "f2": W2, "f3": W3},
    "dirichlet_k": K,
    "posterior": marg,
    "p_sums_to_one": round(sum(pooled.values()), 12),
    "taiex": {"f_touch25": f_taiex, "n": n_taiex, "marginal": marg_taiex},
    "nvda": {"f_touch25": f_nvda, "n": n_nvda},
    "aggregates": agg,
    "sensitivity": sens,
    "timing": {"partition": timing,
               "cohort_touch_to_trough_months": cohorts,
               "pooled_quantiles_months": qs,
               "mapped_calendar": cal},
}
(OUT / "scenario_posterior_update.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print("=== live conditions (close basis) ===")
for k, v in live.items():
    print(f"  {k:6} dd {v['drawdown_pct']:>7.2f}%  crossings: {v['first_close_at_or_below']}")

print("\n=== streams (each must sum to 1 over E2/E3/E4) ===")
for name, f in result["streams"].items():
    print(f"  {name}: " + "  ".join(f"{k}={f[k]:.3f}" for k in BOUNDS),
          f"  sum={sum(f.values()):.3f}")
print(f"\nweights: f1={W1} f2={W2} f3={W3}")
print("pooled point vector:", {k: round(v, 3) for k, v in pooled.items()},
      " sum =", round(sum(pooled.values()), 10))
print(f"\nDirichlet k={K} -> marginal (median [q10, q90]):")
for k in BOUNDS:
    m = marg[k]
    print(f"  {k}: {m['median']:.3f}  [{m['q10']:.3f}, {m['q90']:.3f}]")
print("\nsensitivity (E4 / E3+e4):")
for name, vec in sens.items():
    print(f"  {name}: E4={vec['E4']:.3f}  P(<=-25%)={vec['E3'] + vec['E4']:.3f}")
print(f"\nTAIEX -25% cohort (n={n_taiex}):", {k: round(v, 3) for k, v in f_taiex.items()})
print(f"NVDA  -25% cohort (n={n_nvda}):", {k: round(v, 3) for k, v in f_nvda.items()})
print("\ntiming:", json.dumps(timing, ensure_ascii=False))
print("cohort m2t:", {k: [round(x, 1) for x in v] for k, v in cohorts.items()})
print("pooled quantiles (months):", {k: round(v, 2) for k, v in qs.items()}, "->", cal)
print("\naggregates:")
for k, v in agg.items():
    print(f"  {k}: {v['point']:.3f}  median {v['median']:.3f}  [{v['q10']:.3f}, {v['q90']:.3f}]")
