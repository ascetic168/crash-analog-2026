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
