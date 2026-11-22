# -*- coding: utf-8 -*-
"""Bundle the dashboard dataset from quant/output_update artifacts into one JSON
(update-pipeline variant of bundle_dashboard_data.py; original quant/output untouched).
Reads the three-way posterior (E2/E3/E4), the live snapshot through 2026-11-20,
and reuses the frozen valuation layer (metrics_current.json — Shiller/Z.1 unchanged).
"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "output_update"
ORIG = HERE.parent / "output"
DEST = OUT / "dashboard_data_update.json"

data = {}

# aligned paths (long format -> {episode: [[m, dd], ...]})
paths = pd.read_csv(OUT / "analogs_paths.csv")
data["paths"] = {ep: grp[["months_from_peak", "drawdown_pct"]].round(1).values.tolist()
                 for ep, grp in paths.groupby("episode")}

# named episodes
data["named"] = pd.read_csv(OUT / "analogs_named.csv").to_dict("records")

# conditional stats (drop verbose detail lists)
cond = json.loads((OUT / "analogs_conditional.json").read_text(encoding="utf-8"))["conditional"]
cond_slim = {}
for asset, v in cond.items():
    if asset == "NDX_high_cape":
        cond_slim[asset] = {"n10": v["n_episodes_10pct"], "n20": v["n_episodes_20pct"]}
        continue
    cond_slim[asset] = {}
    for d, s in v.items():
        if str(d).isdigit():
            cond_slim[asset][str(d)] = {k: s[k] for k in
                                        ("n_episodes", "median_eventual_max_dd",
                                         "p10_eventual_max_dd", "median_months_to_trough",
                                         "median_fwd_1y") if k in s}
data["conditional"] = cond_slim

# stats layer: GSY baskets + LPPLS confidence + validation tcs
stats = json.loads((OUT / "stats_layer_update.json").read_text(encoding="utf-8"))
gsy = {}
for k, v in stats["gsy_basket_update"].items():
    gsy[k] = {"ret2y": v["ret_2y_at_peak_pct"], "dd": v["basket_dd_from_1006_peak_pct"],
              "crossed40": v["crossed_minus40"], "n": v["n_names"]}
data["gsy"] = gsy

lpc = {}
for k, v in stats["lppls_confidence"].items():
    lpc[k] = {"qual": v["n_qualifying"], "windows": v["n_windows"],
              "conf": v.get("confidence_within_6m"), "counts": v.get("tc_counts", {})}
data["lppls"] = lpc

data["lppl_validation"] = [
    {"end": w["end"], "tc": w.get("tc_median"), "qual": w["n_qualifying"]}
    for w in stats["lppl_validation_ndx1999"]
]

# coherent scenario posterior (three-way: E1 eliminated on 2026-11-19)
post = json.loads((OUT / "scenario_posterior_update.json").read_text(encoding="utf-8"))


def _row(d):
    # percentages pre-scaled and rounded here (Python rounding == the report's),
    # so the JS side displays the exact same numbers without float re-multiplication
    return {"m": round(d["median"] * 100, 1), "lo": round(d["q10"] * 100, 1),
            "hi": round(d["q90"] * 100, 1), "pt": round(d["point"] * 100, 1)}


def _agg(d):
    return {"pt": round(d["point"] * 100, 1), "lo": round(d["q10"] * 100, 1),
            "hi": round(d["q90"] * 100, 1)}


_timing_vals = list(post["timing"]["partition"].values())
data["scenarios"] = {
    "k": post["dirichlet_k"],
    "ndx": [{"key": k, **_row(post["posterior"][k])} for k in ("E2", "E3", "E4")],
    "ndx_le25": _agg(post["aggregates"]["p_terminal_le25"]),
    "taiex": [{"key": k, **_row(post["taiex"]["marginal"][k])} for k in ("E2", "E3", "E4")],
    "nvda": {"locked": True,
             "median_end": -49.7, "p10_end": -79.9,
             "f_e4": post["nvda"]["f_touch25"]["E4"]},
    "timing": {"a": _timing_vals[0], "b": _timing_vals[1], "c": _timing_vals[2]},
}

# live drawdowns through 2026-11-20 (from the update pipeline's snapshot)
snap = json.loads((OUT / "live_snapshot.json").read_text(encoding="utf-8"))
data["live"] = snap["live"]
data["as_of"] = snap["as_of"]

# valuation metrics snapshot (unchanged layer: Shiller to 2026-10, Z.1 to 2026Q2)
met = json.loads((ORIG / "metrics_current.json").read_text(encoding="utf-8"))
data["cape_now"] = met["cape"]["now"]
data["cape_pct"] = met["cape"]["percentile_since_1871"]
data["mv_gdp_now"] = met["mv_gdp"]["now_nonfin_mv_gdp"]
data["mv_gdp_pct"] = met["mv_gdp"]["percentile_since_1945"]
data["ecy_now"] = met["cape"]["peaks"]["2026-10 (now)"]["ecy_nom"]
data["margin_gdp"] = met["mv_gdp"]["margin_gdp_now"]
data["cape_eves"] = {k: v["cape"] for k, v in met["cape"]["peaks"].items()}

DEST.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"dashboard data (update): {DEST} ({DEST.stat().st_size:,} bytes)")
print("episodes:", list(data["paths"].keys()))
print("live:", {k: v["drawdown_pct"] for k, v in data["live"].items()})
print("timing:", data["scenarios"]["timing"], "| ndx:", [(r["key"], round(r["pt"], 3)) for r in data["scenarios"]["ndx"]])
