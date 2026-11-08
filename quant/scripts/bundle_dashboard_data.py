# -*- coding: utf-8 -*-
"""Bundle the dashboard dataset from quant/output artifacts into one JSON."""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "output"
DEST = OUT / "dashboard_data.json"

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
stats = json.loads((OUT / "stats_layer.json").read_text(encoding="utf-8"))
gsy = {}
for k, v in stats["gsy_basket"].items():
    gsy[k] = {"ret2y": v["ret_2y_pct"], "slope8m": v["slope_8m"],
              "passes": v["passes_100pct"], "n": v["n_names"]}
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

# coherent scenario posterior
post = json.loads((OUT / "scenario_posterior.json").read_text(encoding="utf-8"))
data["scenarios"] = {
    "partition": post["partition"],
    "ndx": [{"key": k, "m": post["posterior"][k]["median"], "lo": post["posterior"][k]["q10"],
             "hi": post["posterior"][k]["q90"], "pt": post["posterior"][k]["point"]}
            for k in ("E1", "E2", "E3", "E4")],
    "taiex": [{"key": k, "m": post["taiex"]["marginal"][k]["median"], "lo": post["taiex"]["marginal"][k]["q10"],
               "hi": post["taiex"]["marginal"][k]["q90"], "pt": post["taiex"]["marginal"][k]["point"]}
              for k in ("E1", "E2", "E3", "E4")],
    "nvda": [{"key": k, "m": post["nvda"]["f"][k], "lo": None, "hi": None, "pt": post["nvda"]["f"][k]}
             for k in ("E1", "E2", "E3", "E4")],
    "timing": post["timing"],
    "sens": [{"name": n, "e4": v["E4"]} for n, v in post["sensitivity"].items()],
    "k": post["dirichlet_k"],
}

# metrics snapshot
met = json.loads((OUT / "metrics_current.json").read_text(encoding="utf-8"))
data["live"] = met["live_drawdowns"]
data["cape_now"] = met["cape"]["now"]
data["cape_pct"] = met["cape"]["percentile_since_1871"]
data["mv_gdp_now"] = met["mv_gdp"]["now_nonfin_mv_gdp"]
data["mv_gdp_pct"] = met["mv_gdp"]["percentile_since_1945"]
data["ecy_now"] = met["cape"]["peaks"]["2026-10 (now)"]["ecy_nom"]
data["margin_gdp"] = met["mv_gdp"]["margin_gdp_now"]
data["cape_eves"] = {k: v["cape"] for k, v in met["cape"]["peaks"].items()}

DEST.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"dashboard data: {DEST} ({DEST.stat().st_size:,} bytes)")
print("episodes:", list(data["paths"].keys()))
