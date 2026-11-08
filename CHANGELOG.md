# Changelog

All notable changes to the 經濟循環 (economic cycles) workspace.

Format based on [Keep a Changelog](https://keepachangelog.com/); versioning: patch-only bumps
(0.1.x) unless a minor bump is agreed with the owner.

## [0.1.0] - 2026-11-08

### Added — quant pipeline scaffold + data layer
- `quant/scripts/download_data.py`: reproducible downloader for all public data used by the
  quantitative pipeline:
  - Shiller `ie_data.xls` (current copy from shillerdata.com CDN; the `econ.yale.edu` copy is
    stale, ends 2023-09)
  - FRED CSV endpoint: NASDAQCOM (full daily 1971-), GDP, NCBCEL (nonfinancial corporate equity
    market value, quarterly), brokers' customer receivables (margin proxy), GS10, CPILFESL
  - Yahoo chart API (explicit `period1/period2`; anonymous `range=max` silently truncates):
    ^GSPC, ^DJI, ^NDX, ^TWII, ^N225 daily plus NVDA/CSCO/MSFT/AMD/AVGO/TSM/MU/MRVL/SMCI/PLTR/
    ORCL/CRWV/META/AMZN/INTC (dot-com + AI basket)
- `quant/scripts/parse_shiller.py`: positional parser for `ie_data.xls` → `shiller_monthly.csv`;
  cross-validated file CAPE against self-computed CAPE (2000-01 = 43.77 matches published value)
- Project venv (`quant/.venv`, pandas/numpy/scipy/matplotlib/xlrd/openpyxl)

### Notes
- FRED anonymous CSV access serves licensed daily indices (SP500/DJIA) with only ~10 years of
  history; NASDAQCOM is unaffected. Yahoo silently truncates pre-1970 daily data, so pre-1970
  analogs (1929) use Shiller monthly series.
- stooq is blocked by JavaScript bot verification; Yahoo chart API is used instead.

## [0.1.1] - 2026-11-08

### Added — metrics layer (`quant/scripts/build_metrics.py`)
- Current objective readings vs the eve of five crashes (1929/1973/1987/2000/2007/2021):
  - CAPE 40.71 (2026-10) = 99th percentile since 1871; nominal ECY −2.78% = 3rd percentile
  - Z.1 nonfinancial equity MV / GDP = 2.55 (2026Q2) = record since 1945 (vs 1.63 in 2000Q1,
    2.19 in 2021Q4); Z.1 margin receivables / GDP = 2.28% = 98th percentile but below the 2000
    peak (2.65%)
- GSY run-up variables at peaks: NDX 2026 +55.8%/2y (below the 100% bubble threshold; 2000 was
  +288%), TAIEX 2026 +123% (passes threshold), NVDA +92%, CSCO 2000 +592%
- Live drawdowns from the common 2026-10-06 peak: NDX −13.6%, TAIEX −20.3%, NVDA −22.0%,
  SPX −5.7%
- Output: `quant/output/metrics_current.json`

## [0.1.4] - 2026-11-08

### Added — integrated inference report (output layer)
- `量化類比推論報告_20261108.md`: synthesis of all four layers into a
  drawdown x timing probability matrix:
  - scenarios A-D with transparent probability weights (20-25% / 45-55% /
    15-25% / 5-10%) each traceable to data-stream provenance
  - direct quantitative statements: P(NDX >= -30% in 12m) ~ 55-70%,
    P(NDX >= -40% in 24m) ~ 40-60%, P(TAIEX <= 32,000) ~ 55-70%, UBS'
    22,000 equals the measured deep tail (p10 = -56.0%)
  - timing distribution from LPPL clusters (NDX critical point triggered
    2026-10-06; NVDA 2026-11; TAIEX 2027-01)
  - sensitivity table (NVDA earnings, depreciation accounting, OpenAI
    revenue, credit spreads, Fed path) with pp-level effects
  - comparison against Klement/Grantham/Hussman/Slok/Dalio/UBS/Huang and
    full limitations section

## [0.1.6] - 2026-11-08

### Added — interactive dashboard
- `quant/scripts/bundle_dashboard_data.py`: condenses all pipeline outputs into
  `quant/output/dashboard_data.json` (13 KB) for the inline visualization
- inline dashboard fragment (crash-analog-dashboard.html, session visualization
  directory, authored per the visualize skill): 4 stat cards + 4 tab panels
  - 崩盤軌跡對齊: D3 line chart, per-episode toggle chips, cross-series hover
    tooltip, paths truncated at peak-recovery (post-recovery gains no longer
    escape the frame)
  - 條件化統計: three small multiples (median + deep tail p10 + current marker)
  - LPPL 臨界時點: tc monthly clusters per asset + 1999 validation table
  - 情境機率: A-D probability range bars + scenario table
- preview tooling: `pdf_build_quant/dashboard_template.html` (literal fragment
  source with data token) + `preview/make_preview.py` (light-theme wrapper for
  headless screenshots)
- visual gate: 3 rounds of visual-judge, all four panels pass

## [0.1.7] - 2026-11-08

### Changed — coherent scenario posterior (fixes the sum-to-1 critique)
- `quant/scripts/build_scenario_posterior.py`: replaces the report's old
  independently-guessed scenario ranges (which summed to 85-115%) with a
  coherent construction:
  - mutually exclusive & exhaustive partition by NDX eventual max drawdown
    (E1 > -15 / E2 -15~-25 / E3 -25~-40 / E4 <= -40; E4 boundary = GSY
    crash definition)
  - three evidence streams each give a normalized vector: empirical
    frequencies (n=15 all episodes, n=4 high-CAPE subset), GSY-implied
    (sector 0.65 x dilution 0.75), explicit weights 0.45/0.25/0.30
  - pooled point vector sums to 1.000 exactly (in-code assertion)
  - uncertainty = Dirichlet(k=24) marginals; reported intervals are 80%
    quantiles of the SAME joint distribution (any draw sums to 1)
  - honest stream disagreement surfaced: pure empirical P(E4)=6.7% vs pure
    GSY 48.8%, baseline 23.9%; sensitivity table spans the choices
  - TAIEX empirical (n=5, live excluded): 5/5 deepened past -25%;
    P(terminal <= -25%) = 97.3% [84.9, 99.9] (Jeffreys-smoothed)
  - NVDA empirical (n=16): P(terminal <= -25%) = 82.6% [68.3, 92.4]
  - timing restated as a normalized partition (50/32.5/17.5)
- report: new section 5.0 (method), 5.1-5.4 rewritten on the posterior,
  summary line updated, old A-D labels mapped to E1-E4 everywhere
- PDF rebuilt (19 pages), section-5 pages pass visual-judge
- dashboard scenario panel now renders the posterior (interval bars +
  median ticks + coherent table); passes visual-judge

## [0.1.10] - 2026-11-08

### Changed — author attribution
- report markdown front matter: 作者 Charlie Chu（charliechu1688@gmail.com）
- PDF cover meta block and PDF metadata author field updated accordingly

## [0.1.11] - 2026-11-08

### Changed — front matter layout + PDF protection
- report front matter: each metadata line (報告日期/資料截至/方法/白話結論)
  is now its own paragraph; author line removed from page 3 (cover keeps it)
- final PDF is now encrypted with qpdf (AES-256, R=6): printing, copying and
  modification disabled; password protected; the encryption step is part of
  build_pdf.py so rebuilds stay protected

## [0.1.13] - 2026-11-08

### Changed — PDF owner-lock (no password to read)
- final PDF encryption switched from password-to-open to owner-lock:
  opens freely, copy/extract/print/modify still disabled (AES-256, R=6)
  per publishing decision

### Added — public GitHub repo
- published https://github.com/ascetic168/crash-analog-2026 (fresh, clean
  initial commit; private history stays local)
- contents: pipeline scripts, raw data (~9MB), all computed outputs,
  standalone dashboard (d3 embedded), owner-locked report PDF,
  bilingual README, MIT license
- GitHub Pages enabled from /docs: dashboard live URL
- author attribution: Charlie Chu (charliechu1688@gmail.com) on cover,
  front matter, PDF metadata, public commits

## [0.1.14] - 2026-11-08

### Added — repo links in the report
- front matter and section 8 now link to the public repo and the live
  dashboard (readers can view/download online); PDF re-encrypted and
  synced to the public repo

## [0.1.15] - 2026-11-09

### Added — beginner-friendly dashboard layer
- template: plain-language intro card (what the page answers + how to use it);
  collapsible "這張圖怎麼看？" guide above each of the 4 chart panels, open by
  default (how to read the chart, where the market stands now, one-line takeaway)
- new 5th tab 名詞解釋: plain-Chinese glossary, 4 groups / 19 terms (CAPE, ECY,
  p10 deep tail, LPPL/tc, Dirichlet posterior, E1–E4, …)
- KPI cards get ⓘ hover tooltips; panels 2–4 dormant data-tooltip marks are now
  wired to a delegated pointer handler (bug fix: hover tooltips actually display)
- KPI stat-card values now filled from bundled data at render time so the cards
  always agree with the charts (fixes stale hardcoded NDX −14.7% / NVDA −24.1%
  vs pipeline data −13.6% / −22.0%)

### Changed — export chain
- export_dashboard.py reads the in-repo template (pdf_build_quant/
  dashboard_template.html) and substitutes /*__DATA__*/ with quant/output/
  dashboard_data.json; drops the out-of-repo .zcode fragment dependency
  (regression gate: re-export byte-identical to 0.1.14 output before edits)
- QA: all 5 tabs browser-verified (render, tooltips, guide collapse, legacy
  panel-1 hover, 390px narrow layout) + visual-judge 5/5 pass; synced to the
  public repo docs/

## [0.1.16] - 2026-11-09

### Changed — E1 scenario label made unambiguous
- E1 display label 「不再加深（先漲後崩）」→「不再加深（回檔不破 −15%）」 across the
  dashboard (chart label, scenario table, panel guide, glossary) and the report
  (scenario matrix + label-history note); the definition is unchanged: NDX eventual
  max drawdown over the next 24 months never deeper than −15%
- dashboard: narrow screens (<420px) switch to a short on-chart label to avoid
  overflow; the panel guide and glossary spell out the full definition
- build_scenario_posterior.py partition note updated; data chain regenerated
  (scenario_posterior.json / dashboard_data.json) — verified numerically identical
  except the note string
- report PDF rebuilt (pandoc → Edge → merge → qpdf owner-lock, 20 pages);
  dashboard + data + template + PDF synced to the public repo

## [0.1.17] - 2026-11-09

### Fixed — dashboard URL in the report
- front matter and §8 linked readers to the site root, which serves the README
  landing page, not the dashboard; both now point directly to
  https://ascetic168.github.io/crash-analog-2026/quant/dashboard/ (verified live)
- report PDF rebuilt and re-locked (AES-256 owner-lock); synced to the public repo
