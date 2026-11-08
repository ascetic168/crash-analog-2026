# -*- coding: utf-8 -*-
"""Export the dashboard template as a standalone, offline-capable HTML file
(d3 embedded, self-contained light theme). Output: quant/dashboard/index.html
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUANT = HERE.parent
REPO = QUANT.parent
TEMPLATE = REPO / "pdf_build_quant" / "dashboard_template.html"
DATAJS = QUANT / "output" / "dashboard_data.json"
D3 = QUANT / "data" / "downloads" / "_d3.min.js"
OUT = QUANT / "dashboard" / "index.html"
D3_URL = "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"

if not D3.exists():
    import requests
    D3.parent.mkdir(parents=True, exist_ok=True)
    _r = requests.get(D3_URL, timeout=60)
    _r.raise_for_status()
    D3.write_bytes(_r.content)
    print(f"cached d3 -> {D3} ({len(_r.content):,} bytes)")

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
body{margin:0 auto;padding:20px;max-width:1100px;background:var(--background);color:var(--foreground);
     font-family:"Microsoft JhengHei","PingFang TC",sans-serif;font-size:14px;line-height:1.5}
h1{font-size:20px;font-weight:500;margin:0 0 4px}
h3{font-size:16px;font-weight:500;margin:14px 0 8px}
.muted{color:var(--muted-foreground);font-size:12px;margin:0 0 14px}
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
.table th{text-align:left;font-weight:500;border-bottom:1px solid var(--border);padding:5px 7px;color:var(--muted-foreground)}
.table td{border-bottom:1px solid var(--border);padding:5px 7px;vertical-align:top}
.text-nowrap{white-space:nowrap}
footer{margin-top:18px;color:var(--muted-foreground);font-size:12px}
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
"""

frag = TEMPLATE.read_text(encoding="utf-8")
# substitute the /*__DATA__*/ token with the bundled dashboard data
data = json.loads(DATAJS.read_text(encoding="utf-8"))
data_s = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
frag = frag.replace("const DATA = /*__DATA__*/{};", "const DATA = " + data_s + ";")
# embed d3 inline for offline use
d3js = D3.read_text(encoding="utf-8")
frag = frag.replace('<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>',
                    "<script>" + d3js + "</script>")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>崩盤類比儀表板 · Crash Analog Dashboard</title>
<style>{THEME}</style>
</head><body>
<h1 data-i18n="doc_h1">崩盤類比儀表板</h1>
<p class="muted" data-i18n="doc_subtitle">2026 年 AI 行情 vs 1929/1973/1987/2000/2007/2021 · 資料截至 2026-11-06 · 作者 Charlie Chu · 數字可由 quant/ 管線重現</p>
{frag}
<footer data-i18n="doc_footer">以四層量化管線（資料 → 指標 → 類比 → 統計）產出 · 非投資建議</footer>
<script>{TABS_JS}</script>
</body></html>""", encoding="utf-8")
print(f"standalone dashboard: {OUT} ({OUT.stat().st_size:,} bytes)")
