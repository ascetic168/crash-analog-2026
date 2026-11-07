# -*- coding: utf-8 -*-
"""Preview-only wrapper for the dashboard fragment (not the deliverable):
local d3, approximate light-theme tokens, minimal tab switching, hash-based
tab selection so Edge headless can screenshot each panel.

The real fragment keeps the canonical CDN d3 tag and relies on the host theme.
"""
import re
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent  # pdf_build_quant
FRAG = Path(r"C:\Users\charl\.zcode\v2\visualizations\b3dec255754e2cb0904fe24c83211394d9d3bdc7372c0cd180660d21c51b23f7\crash-analog-dashboard.html")
OUT = BUILD / "preview" / "wrapped.html"

frag = FRAG.read_text(encoding="utf-8")
# local d3 for offline preview
frag = frag.replace("https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js", "d3.min.js")

THEME = """
:root{
  --background:#ffffff; --foreground:#1a1d1f;
  --card:#f6f7f8; --card-foreground:#1a1d1f;
  --muted:#eceff0; --muted-foreground:#5d666a;
  --border:#d6dde1; --popover:#ffffff; --popover-foreground:#1a1d1f;
  --destructive:#c2334a;
  --viz-series-1:#578095; --viz-series-2:#a22c40; --viz-series-3:#4d7f4e;
  --viz-series-4:#8a6d3b; --viz-series-5:#7a5296; --viz-series-6:#3d7a8c;
}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--background);color:var(--foreground);
     font-family:"Microsoft JhengHei",sans-serif;font-size:14px;line-height:1.5}
h3{font-size:16px;font-weight:500;margin:14px 0 8px}
.card{background:var(--card);color:var(--card-foreground);border-radius:10px;padding:12px 14px}
.viz-stat{display:flex;flex-direction:column;gap:3px}
.viz-stat-value{font-size:26px;font-weight:500;line-height:1.2}
.viz-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:14px}
.viz-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.nav.nav-pills{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 12px}
.nav-link{border:1px solid var(--border);background:var(--card);color:var(--foreground);
          border-radius:999px;padding:5px 14px;font:inherit;cursor:pointer}
.nav-link.active,.nav-link[aria-selected="true"]{background:var(--foreground);color:var(--background);border-color:var(--foreground)}
.text-small{font-size:12px}
.text-muted{color:var(--muted-foreground)}
.tabular-nums{font-variant-numeric:tabular-nums}
.tooltip{position:absolute;z-index:10;pointer-events:none;background:var(--popover);color:var(--popover-foreground);
         border:1px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.12);max-width:230px}
.table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
.table th{text-align:left;border-bottom:1px solid var(--border);padding:5px 7px;color:var(--muted-foreground);font-weight:400}
.table td{border-bottom:1px solid var(--border);padding:5px 7px;vertical-align:top}
.text-nowrap{white-space:nowrap}
"""

TABS_JS = """
document.addEventListener("click", (ev) => {
  const btn = ev.target.closest('.nav-link[role="tab"]');
  if (!btn) return;
  document.querySelectorAll('.nav-link[role="tab"]').forEach(b => {
    b.classList.toggle("active", b === btn);
    b.setAttribute("aria-selected", b === btn ? "true" : "false");
  });
  document.querySelectorAll('[role="tabpanel"]').forEach(p => {
    p.hidden = p.id !== btn.getAttribute("aria-controls");
  });
});
const hMap = { paths: "cad-tab-paths", cond: "cad-tab-cond", lppl: "cad-tab-lppl", scen: "cad-tab-scen" };
const h = location.hash.replace("#", "");
if (hMap[h]) setTimeout(() => document.getElementById(hMap[h]).click(), 120);
"""

wrapped = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<title>crash-analog-dashboard preview</title>
<style>{THEME}</style>
</head><body>
{frag}
<script>{TABS_JS}</script>
</body></html>"""

OUT.write_text(wrapped, encoding="utf-8")
print("preview wrapper:", OUT, f"{OUT.stat().st_size:,} bytes")
