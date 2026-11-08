# -*- coding: utf-8 -*-
"""Scenario posterior: turn the report's scenario weights into a coherent,
reproducible probability distribution.

Method
------
1. Partition (mutually exclusive, collectively exhaustive) by NDX eventual max
   drawdown over the next 24 months:
     E1  > -15%   (no further deepening; "melt-up then crash later")
     E2  -15 ~ -25%   (shallow correction, 1998/2024-07/2025-02 type)
     E3  -25 ~ -40%   (deep correction, 2021/1987 type)
     E4  <= -40%      (terminal crash, 2000 type)
   The boundary -40% matches the GSY crash definition, so P(E4) is directly
   comparable with the GSY-implied statement.

2. Three evidence streams, each giving a point vector on the partition:
   f1  empirical frequencies, all NDX episodes touching -15% (n=15)
   f2  empirical frequencies, high-CAPE (>35) subset of those (n=4)
   f3  GSY-implied: P(sector -40%+) x dilution delta, remainder split by
       analog shape; LPPL (critical time = now) caps E1
   Weights w1/w2/w3 are explicit assumptions; sensitivity table spans them.

3. Pool: p = normalize(w1*f1 + w2*f2 + w3*f3)  -> sums to 1 exactly.

4. Uncertainty: Dirichlet alpha = k * p (k = effective evidence weight).
   Each component's marginal is Beta(alpha_i, k - alpha_i); report median and
   10%/90% quantiles. These marginals derive from ONE joint distribution on
   the simplex - coherent by construction (any single draw sums to 1).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta as Beta

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "output"

BOUNDS = ["E1", "E2", "E3", "E4"]  # order: shallow -> deep

# ---------------------------------------------------------------- streams
cond = json.loads((OUT / "analogs_conditional.json").read_text(encoding="utf-8"))["conditional"]


def freq_from_detail(detail, live_date="2026-10-06"):
    """Frequency vector over the partition from episode detail rows."""
    rows = [r for r in detail if r["peak"] != live_date]  # exclude the ongoing live episode
    n = len(rows)
    v = {k: 0.0 for k in BOUNDS}
    for r in rows:
        dd = r["eventual_max_dd"]
        if dd > -15:
            v["E1"] += 1
        elif dd > -25:
            v["E2"] += 1
        elif dd > -40:
            v["E3"] += 1
        else:
            v["E4"] += 1
    return {k: v[k] / n for k in BOUNDS}, n


f1, n1 = freq_from_detail(cond["NDX"]["15"]["detail"])
hi = [r for r in cond["NDX"]["15"]["detail"]
      if r.get("cape_at_episode_start") and r["cape_at_episode_start"] > 35
      and r["peak"] != "2026-10-06"]
f2, n2 = freq_from_detail(hi)

# GSY-implied vector: P(sector -40%+) in [0.5, 0.8] (GSY 2019 conditional probs)
# x index dilution delta in [0.6, 0.9] -> P(E4) mid 0.65*0.75 = 0.49
# remainder split per analog shape (E3 ~= 60% of non-E4 deep mass, E2 next, E1 capped by LPPL)
P_SECTOR_MID, DELTA_MID = 0.65, 0.75
f3 = {
    "E1": 0.08,                                   # LPPL: critical time is now -> melt-up unlikely
    "E2": 0.25,
    "E4": P_SECTOR_MID * DELTA_MID,               # 0.4875
}
f3["E3"] = 1.0 - f3["E1"] - f3["E2"] - f3["E4"]  # exact remainder -> sums to 1
assert abs(sum(f3.values()) - 1) < 1e-9

W1, W2, W3 = 0.45, 0.25, 0.30
pooled = {k: W1 * f1[k] + W2 * f2[k] + W3 * f3[k] for k in BOUNDS}
s = sum(pooled.values())
pooled = {k: pooled[k] / s for k in BOUNDS}

K = 24  # effective evidence weight for the Dirichlet
alpha = {k: K * pooled[k] for k in BOUNDS}
marg = {}
for k in BOUNDS:
    a = alpha[k]
    marg[k] = {
        "point": round(pooled[k], 4),
        "median": round(float(Beta.ppf(0.50, a, K - a)), 4),
        "q10": round(float(Beta.ppf(0.10, a, K - a)), 4),
        "q90": round(float(Beta.ppf(0.90, a, K - a)), 4),
    }

# ---------------------------------------------------------------- aggregates
# P(E3 u E4) = P(terminal <= -25%) follows Beta(a3+a4, k-a3-a4) exactly
a34 = alpha["E3"] + alpha["E4"]
agg = {
    "p_terminal_le25": {  # NDX
        "point": round(pooled["E3"] + pooled["E4"], 4),
        "median": round(float(Beta.ppf(0.50, a34, K - a34)), 4),
        "q10": round(float(Beta.ppf(0.10, a34, K - a34)), 4),
        "q90": round(float(Beta.ppf(0.90, a34, K - a34)), 4),
    },
}

# ---------------------------------------------------------------- TAIEX / NVDA empirical
f_taiex, n_taiex = freq_from_detail(cond["TAIEX"]["20"]["detail"])
f_nvda, n_nvda = freq_from_detail(cond["NVDA"]["20"]["detail"])
# no sector regression for TW: empirical only, k = sample size (weak)
def _bq(f, k, q):
    """Beta quantile with Jeffreys smoothing (avoids alpha=0 / beta=0 degeneracy)."""
    a = k * f + 0.5
    b = k * (1 - f) + 0.5
    return round(float(Beta.ppf(q, a, b)), 4)

marg_taiex = {k: {"point": round(f_taiex[k], 4),
                  "median": _bq(f_taiex[k], 8, 0.5),
                  "q10": _bq(f_taiex[k], 8, 0.10),
                  "q90": _bq(f_taiex[k], 8, 0.90)}
             for k in BOUNDS}
agg["taiex_p_terminal_le25"] = {
    "point": round(f_taiex["E3"] + f_taiex["E4"], 4),
    "median": _bq(f_taiex["E3"] + f_taiex["E4"], 8, 0.5),
    "q10": _bq(f_taiex["E3"] + f_taiex["E4"], 8, 0.10),
    "q90": _bq(f_taiex["E3"] + f_taiex["E4"], 8, 0.90),
}
a_n34 = 16 * (f_nvda["E3"] + f_nvda["E4"])
agg["nvda_p_terminal_le25"] = {
    "point": round(f_nvda["E3"] + f_nvda["E4"], 4),
    "median": round(float(Beta.ppf(0.50, a_n34, 16 - a_n34)), 4),
    "q10": round(float(Beta.ppf(0.10, a_n34, 16 - a_n34)), 4),
    "q90": round(float(Beta.ppf(0.90, a_n34, 16 - a_n34)), 4),
}

# ---------------------------------------------------------------- sensitivity
def pool_with(w3, w1=0.45, w2=None):
    w2 = (1 - w1 - w3) if w2 is None else w2
    v = {k: w1 * f1[k] + w2 * f2[k] + w3 * f3[k] for k in BOUNDS}
    s = sum(v.values())
    return {k: v[k] / s for k in BOUNDS}

sens = {
    "pure_empirical (w3=0)": pool_with(0.0, w1=1.0, w2=0.0),
    "pure_GSY (w3=1)": pool_with(1.0, w1=0.0, w2=0.0),
    "half_GSY (w3=0.15)": pool_with(0.15),
    "baseline (w3=0.30)": pooled,
    "GSY_low (sector 0.50, delta 0.60)": None,  # computed below
}
g_low = {"E1": 0.08, "E2": 0.25, "E4": 0.50 * 0.60}
g_low["E3"] = 1.0 - g_low["E1"] - g_low["E2"] - g_low["E4"]
v = {k: W1 * f1[k] + W2 * f2[k] + W3 * g_low[k] for k in BOUNDS}
sens["GSY_low (sector 0.50, delta 0.60)"] = {k: v[k] / sum(v.values()) for k in BOUNDS}
for name, vec in sens.items():
    vec = {k: round(x, 4) for k, x in vec.items()}

# ---------------------------------------------------------------- timing (coherent)
timing = {"2026Q4": 0.50, "2027H1": 0.325, "2027H2+": 0.175}
assert abs(sum(timing.values()) - 1) < 1e-9

result = {
    "partition": {
        "E1": "NDX 未來 24 個月終點深度 > -15%（不再加深；先漲後再回檔不破線仍計入此類）",
        "E2": "-15% ~ -25%（淺修正：1998/2024-07/2025-02 型）",
        "E3": "-25% ~ -40%（深度修正：2021/1987 型）",
        "E4": "<= -40%（終結性崩盤：2000 型；與 GSY 崩盤定義同界）",
    },
    "streams": {"f1_empirical_n%d" % n1: f1, "f2_highCAPE_n%d" % n2: f2,
                "f3_GSY_implied": f3},
    "weights": {"f1": W1, "f2": W2, "f3": W3},
    "dirichlet_k": K,
    "posterior": marg,
    "p_sums_to_one": round(sum(pooled.values()), 12),
    "taiex": {"f": f_taiex, "n": n_taiex, "marginal": marg_taiex},
    "nvda": {"f": f_nvda, "n": n_nvda},
    "aggregates": agg,
    "sensitivity": sens,
    "timing": timing,
    "implied_p_ndx_ge40": round(marg["E4"]["median"], 4),
}
(OUT / "scenario_posterior.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print("=== streams (must each sum to 1) ===")
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
print("\nsensitivity (E4 across weight choices):")
for name, vec in sens.items():
    print(f"  {name}: E4={vec['E4']:.3f}  E2={vec['E2']:.3f}  E3={vec['E3']:.3f}")
print("\nTAIEX empirical (n=%d):" % n_taiex,
      {k: round(v, 3) for k, v in f_taiex.items()})
print("NVDA empirical (n=%d):" % n_nvda,
      {k: round(v, 3) for k, v in f_nvda.items()})
print("timing partition:", timing)
print("")
print("aggregates:")
for k, v in agg.items():
    print(f"  {k}: {v['point']:.3f}  median {v['median']:.3f}  [{v['q10']:.3f}, {v['q90']:.3f}]")
