# Changelog

All notable changes to the 經濟循環 (economic cycles) workspace.

Format based on [Keep a Changelog](https://keepachangelog.com/); versioning: patch-only bumps
(0.1.x) unless a minor bump is agreed with the owner.

## [0.1.25] - 2026-11-22

### Changed — 11/21 follow-up report: trough forecast stated explicitly (front & back)
- owner feedback: the conclusions were still too veiled; the "when does this bust
  bottom out, with what probabilities" statement now leads the report and is echoed
  at the end:
  - new front section「核心預測（先讀這節）」right after the front matter: one-sentence
    verdict + trough-timing table (2026-12 40% / 2027Q1 40% / later 20%, median
    2026-12-20) + depth table (NVDA ≤−40% locked; TAIEX 60% in-band / 40% breaks
    −40%; NDX E2/E3/E4 33.9/39.2/26.9, aggregate P(≤−25%) 66.1% [53.6–78.1]) +
    the trigger list that would move these probabilities
  - new final section「十、結語：把預測說清楚」: the three testable statements
    (timing, depth, falsifiability) + next scheduled update (~2027-02)
  - dashboard link paragraph now states the dashboard is updated to the 11-20
    snapshot (matches 0.1.26)
- TAIEX interval corrections to match the pipeline arithmetic exactly:
  E3 band interval [37.8%, 79.0%] (was 78.9 in the new front table), E4 lower bound
  21.1% in §5.2 aggregate row (was 21.0) — dashboard and report now agree
- PDF rebuilt (22 pages, 11 bookmarks, TOC re-numbered, cover summary adds the
  80% Dec-2026–Q1-2027 trough window); visual-judge pass on the six affected pages

## [0.1.24] - 2026-11-21

### Added — follow-up report: 11/12–11/20 priced against the frozen 11/8 forecast
- **量化類比推論更新報告_20261121** (.md/.pdf, 19 pages, same design system):
  independent follow-up to the frozen 11/8 report (per the 0.1.22/0.1.23
  immutability policy; fulfils the 11/8 appendix promise "probabilities to be
  re-estimated after the 11/17 NVDA earnings")
  - event log 11/10–11/20: policy rebound peaked after 3 sessions (11/9–11/11);
    Huang resignation 11/12 (key-man tail realized at the top grade, NVDA
    closed below the −30% line that day); "perfect earnings sold" 11/17–11/20
    (rev +103% y/y beat, stock −19.2% in 3 sessions; NDX −5.6% and TAIEX
    −6.23% on 11/20; FSC tightened short limits again)
  - honest scorecard: 10/11 directional calls from the frozen 11/8 report hit;
    one trigger-table direction was wrong (strong earnings = shallow path) and
    the table is rewritten per GSY's profits-peak signature
  - updated posterior: NDX E1 (>−15%) dead since 11/19 → three-way partition
    E2 33.9% / E3 39.2% / E4 26.9%; P(NDX terminal ≤−25%) 47.6% → **66.1%**
    [53.6, 78.1]; TAIEX ≤−25% realized 11/20 (now −27.7%); NVDA −47.5% has
    factually locked its terminal ≤−40% (median path −49.7%, tail −79.9%);
    AI-infra basket −41.3% crossed the GSY −40% crash line (the 11/8
    "50–80% within 2y" statement realized in 6 weeks); trough timing:
    2026-12 40% / 2027Q1 40% / later 20% (pooled touch→trough median 1.0m,
    LPPL NVDA cluster 13/18 on 2026-11)
- **charts switched from absolute index levels to percent-from-peak**
  (owner directive: different eras have incomparable peak levels; % from own
  peak is the cross-era common ruler):
  - LPPL figures re-normalized (距自身峰頂 %), incl. new side-by-side
    `lppl_compare_norm.png` (1999 validation vs 2026 live, shared y-axis)
  - scenario/conditional tables in the update report are %-only — no index
    point conversions anywhere (the 11/8 report's §5.1 point table stays as
    the frozen historical record)
  - aligned-paths live lines now stop at the actual latest close instead of
    carrying the last value forward to the full horizon (the flat extension
    read as a forecast, which it was not)
- update pipeline (method-identical to the frozen originals; outputs to
  `quant/output_update/`, originals never overwritten):
  `build_analogs_update.py` (incl. `live_snapshot.json` first-close-crossing
  dates), `build_stats_layer_update.py` (GSY basket drawdown check + LPPL
  refits + normalized charts), `build_scenario_posterior_update.py`
  (three-way Dirichlet posterior + cohort-based timing quantiles)
- `pdf_build_quant/build_pdf_update.py` + `report_style_update.html` (adds
  `tr { break-inside: avoid }` so table rows no longer split across pages);
  cover uses ASCII hyphens (msjh.ttc lacks U+2212 glyphs) — 19 pages,
  9 bookmarks, TOC page numbers 17/17, AES-256 owner-lock
- QA: visual-judge full 19-page pass after repairs (cover minus tofu +
  kicker clipping; two TOC page numbers missing; E3 table row split across
  pages 11→12)

## [0.1.23] - 2026-11-21

### Added — historical evidence boundary frozen before the follow-up report
- policy extension of 0.1.22 to the flagship report: the 11/8 quantitative
  analog report and all published briefs are now treated as immutable
  historical evidence; the 11/12–11/20 developments (Huang resignation,
  NVDA earnings, renewed crash) get a separate follow-up report
- committed the pending 11/9 snapshot so the record is complete:
  - 量化類比推論報告_20261108.md §九 event-log appendix (dated 11/9;
   正文數字不動，資料仍截至 11/6)
  - AI股市泡沫名家觀點與結論 (.md/.pdf, 11/7)
  - 美股收盤報告_20261106 (.html/.pdf)
- tagged `freeze-20261109`: everything at or before this tag is the
  pre-event foresight record; the follow-up report cites this boundary

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

## [0.1.18] - 2026-11-09

### Fixed — report front matter: URL layout + wording
- the two links (GitHub repo / live dashboard) each get their own paragraph
  and their own line; URLs no longer share a line or wrap mid-string
  (new a.url-sm style at 10.5pt — the 63-char dashboard URL did not fit
  the ~352pt text column at 12pt)
- wording corrected: the download claim now sits on the GitHub repo line
  only (the online dashboard is view-only)
- section 8 dashboard bullet: URL moved to its own indented line
- PDF rebuilt, visual-judge pass (front matter + section 8); synced to
  the public repo

## [0.1.19] - 2026-11-09

### Added — trilingual dashboard (繁體中文 / 简体中文 / English)
- every visible string (h1, subtitle, intro, per-chart guides, KPI cards,
  tabs, chart labels, hover tooltips, tables, glossary, footer) moved into
  an I18N dictionary (162 keys × 3 languages); t()/tf() lookups with
  fallback to Traditional Chinese
- language switcher: three pills at the top right; setLang re-renders all
  charts, tables and static text; document lang attribute and <title> follow
- initial language precedence: saved choice (localStorage "cad-lang") >
  browser language (navigator.language: zh-TW/HK/MO → Hant, zh-CN/SG →
  Hans, en* → English, anything else → Hant) > Traditional Chinese
- English uses compact scenario chart labels to fit the label column;
  per-language short labels below 420px viewport

### Fixed — x-axis title collision (pre-existing)
- paths + conditional charts: the x-axis title was drawn at the same
  baseline and position as the last tick label (double-printed glyphs);
  the title now sits on its own line below the ticks (bottom margins
  34→46 / 30→40)
- QA: detection/switch/persistence verified in-browser across tabs and
  languages; 390px EN shows no overflow; visual-judge pass on 6 shots;
  synced to the public repo

## [0.1.20] - 2026-11-10

### Added — US closing brief 2026-11-09 (daily report series)
- 美股收盤報告_20261109.html/.pdf: the Jensen Huang matter priced for the
  first time — NVDA -4.27% (open -6.45%, morning low -8.79%, recovered
  intraday; YTD turned negative at -4.2%; -25.3% off the 10/6 peak;
  SOX -31.4% off its 6/22 record) inside a broad oil-led rebound
  (crude ~-4%: S&P +2.35%, Nasdaq +2.74%, Dow +1,104 pts, SOX +6.85%,
  VIX -22.3% back under 20 at 19.92; 10Y flat 4.86%)
- narrative anchored to the 11/8 board statement (independent
  investigation, "no reason to believe" secrets compromised) and the
  台股收盤報告 2026-11-09 watchlist item "US open is the first test";
  Taiwan linkage section for the Tue 11/10 open (TSM ADR +3.51%,
  supply-chain catch-up risk, gap 39,701–40,347 as the failure line)
- pipeline: fetch_close.py now records meta regularMarketTime (stale-data
  guard); new generator html_build/gen_report_20261109.py; thousands
  separator in the quote-table change column; stage-table range column
  no-wrap — visual-judge 7/7 pass, 2-page repair re-check pass
- series context: daily closing briefs stay untracked like their two
  predecessors (美股 2026-11-06, 台股 2026-11-09); only the CHANGELOG and
  this issue's files are committed

## [0.1.21] - 2026-11-10

> **Superseded by [0.1.22]**: this entry revised the published 台股收盤報告_20261109 in
> place — against the owner's policy that published daily briefs are immutable.
> 0.1.22 restores the TW brief to its exact 11/9 published state and moves the
> stabilization-fund findings to the standalone 國安基金動向_20261109.

### Changed — stabilization-fund verification: TW brief revised, US brief linkage updated
- 台股收盤報告_20261109 → **11/10 修訂版** (9 pages): the pending
  11/9-evening verification is resolved with TWSE/TAIFEX data + news:
  - hypothesis「自營商買超異常放大＝護盤鐵證」**否證**: T86 shows
    自營商(自行買賣) net -4.3萬張 (台積電/聯電/0050 all net-sold)
  - fingerprint relocated: 八大公股買超 102.3億元 (連八買, concentrated in
    large ETFs per media), 投信 +313.1億 (連20買), 五大壽險 +214.9億 —
    domestic three-way ≈630億 vs 外資 -900.5億 (連八賣, Nov cumulative
    7,957.1億): the +4.94% rally was domestic + short-restriction squeeze,
    NOT institutional, NOT foreign
  - TAIFEX TXF: 外資淨空 101,771口 (+1,841) = record high — no covering
    evidence; new 表2 資金流向驗證 (7 rows), stage table renumbered 表3
  - 成交值 8,770億 confirmed by FMTQIK (below crash-day 9,871–13,211億);
    margin-leverage warning (only ~12% cleared vs -24% drawdown)
  - sections 五/七 updated with the US-close result (NVDA -4.27%,
    SOX +6.85% — risk ring-fenced to the single stock)
- 美股收盤報告_20261109: section 五 bullet 3 replaced by the verified
  flow data; sources line extended
- pipeline: html_build/tw_institutional_verify.py (T86 per-stock
  aggregation stocks-only, FMTQIK market stats, MI_MIB probe) + TAIFEX
  futContractsDateDown CSV fetch (TXF by investor type 11/02–11/09);
  both TWSE endpoints need relaxed TLS (their cert chain lacks SKI)
- QA: visual-judge full 10-page pass with 2 fails repaired (表2/表3
  number collision → renumber; footer stranded on near-blank p10 →
  sources/footer tightened, 9 pages) + 2-page re-check pass; US brief
  3-page re-check pass
- repo: 台股 brief now tracked (was untracked); both revised briefs
  committed; 美股 2026-11-06 briefs remain untracked

## [0.1.22] - 2026-11-10

### Fixed/Added — published briefs are immutable: TW brief restored, findings moved to a standalone report
- **policy (owner directive)**: once published, daily briefs are historical
  documents and must never be edited afterwards; follow-up verification is
  published as a separate standalone report
- **台股收盤報告_20261109 restored to its exact 11/9 published state**:
  tw_gen_report.py reverted to the original generator (verified: rewritten
  file was byte-equal to the 11/9 version at 20,459 bytes) and regenerated
  against the untouched 13:44 data snapshots (tw_mis_close.json /
  tw_yahoo_intraday.json); script re-CRLF'd so the template string matches
  the published output — HTML restored at exactly 27,456 bytes and PDF
  reprinted at exactly 521,549 bytes (both byte-size equal to the
  published originals; Edge print-to-pdf is deterministic for identical
  input)
- **國安基金動向_20261109** (new standalone brief, 7 pages, same design
  system): the full 11/9 stabilization-fund verification from the reverted
  revision — flow-verification table (外資現貨 -900.5億/台指期淨空
  101,771口新高/投信 +313.1億/自營商 -312.1億/公股 +102.3億/壽險 +214.9億),
  hypothesis denial (self-operated discretionary accounts net -4.3萬張),
  fingerprint relocation (state-bank ETF buying, 分點口徑 caveat),
  TXF net-short trajectory chart + table (11/2–11/9), turnover calendar,
  scenario-matrix implications, watchlist, honest boundaries
- 美股收盤報告_20261109: cross-references updated to point at the new
  standalone report (was pointing at the reverted TW revision)
- QA: NAF brief visual-judge 7-page pass (1 repair: last x-axis date
  label 11/9 was clipped → per-label text-anchor); US brief us-7/us-6
  citation re-check pass; restoration verified by marker grep (original
  strings present, revision strings absent) + byte sizes
- lesson codified in the NAF footer: 發布後的每日收盤報告為歷史文件、
  不作事後修改——後續查證一律獨立成篇
