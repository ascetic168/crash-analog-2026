# -*- coding: utf-8 -*-
"""Download all public data used by the quant pipeline.

Sources:
  - FRED CSV endpoint (fredgraph.csv): indices & macro series, no API key needed
  - Shiller ie_data.xls: monthly CAPE / P/E10 / GS10 since 1871
  - stooq daily CSV: NDX/Nikkei/TAIEX/NVDA/CSCO etc.

Usage: python download_data.py [OUTDIR]
Downloads land in OUTDIR (default ../data/downloads relative to this script).
"""
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUTDIR = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "downloads"
OUTDIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

FRED_SERIES = {
    # daily indices (licensed: FRED gives full history for NASDAQCOM only; SP500/DJIA are 10y-limited)
    "NASDAQCOM": "NASDAQ Composite daily (1971-)",
    # quarterly macro
    "GDP": "US nominal GDP, SAAR (quarterly)",
    "A261RC1Q027SBEA": "US nominal Gross Value Added, SAAR (quarterly, legacy id)",
    "A261RC1": "US nominal Gross Value Added (annual)",
    "NCBCEL": "Z.1: market value of equities of nonfinancial corporate business, level (quarterly, $M, 1945-)",
    "BOGZ1FL663067003Q": "Z.1: security brokers' receivables due from customers (margin-related, quarterly, $M)",
    # monthly yields / inflation
    "GS10": "10-Year Treasury yield (monthly, 1953-)",
    "CPILFESL": "CPI less food & energy (monthly)",
}

# Yahoo Finance chart API: full daily history, no API key, UA header required
YAHOO_SYMBOLS = {
    "^GSPC": "S&P 500 daily (1927-)",
    "^DJI": "Dow Jones Industrial daily (1896-)",
    "^NDX": "NASDAQ-100 daily (1985-)",
    "^TWII": "TAIEX daily (Taiwan Weighted Index)",
    "^N225": "Nikkei 225 daily",
    "NVDA": "NVIDIA daily (1999 IPO-)",
    "CSCO": "Cisco daily (1990 IPO-)",
    "MSFT": "Microsoft daily (1986 IPO-)",
    # AI basket for GSY sector-level tests (2000 dot-com analog names included)
    "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC ADR", "MU": "Micron",
    "MRVL": "Marvell", "SMCI": "Supermicro", "PLTR": "Palantir",
    "ORCL": "Oracle", "CRWV": "CoreWeave (2025 IPO)", "META": "Meta",
    "AMZN": "Amazon", "INTC": "Intel",
}


def fetch(url: str, dest: Path) -> Path:
    print(f"GET {url}")
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"  -> {dest.name}: {len(r.content):,} bytes")
    return dest


def fetch_yahoo(symbol: str, dest: Path) -> Path:
    """Download full daily history from Yahoo chart API and save date,adjclose CSV."""
    # range=max is capped to ~1y for anonymous clients; explicit period1/period2 gives full history
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1=0&period2={int(time.time())}&interval=1d&events=history"
    )
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    result = data["chart"]["result"][0]
    ts = result["timestamp"]
    adj = result["indicators"]["adjclose"][0]["adjclose"]
    quote = result["indicators"]["quote"][0]
    close = quote["close"]
    import csv
    rows = 0
    with dest.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "adjclose", "close"])
        for t, a, c in zip(ts, adj, close):
            if a is None and c is None:
                continue
            import datetime as _dt
            d = _dt.datetime.fromtimestamp(t, _dt.timezone.utc).strftime("%Y-%m-%d")
            w.writerow([d, a, c])
            rows += 1
    print(f"  -> {dest.name}: {rows} rows, {dest.stat().st_size:,} bytes")
    return dest


def main() -> None:
    ok, failed = [], []
    for series_id, desc in FRED_SERIES.items():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        try:
            fetch(url, OUTDIR / f"fred_{series_id}.csv")
            ok.append(series_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED {series_id}: {exc}")
            failed.append(series_id)
        time.sleep(0.5)

    for symbol, desc in YAHOO_SYMBOLS.items():
        fname = symbol.strip("^").lower().replace("^", "_")
        try:
            fetch_yahoo(symbol, OUTDIR / f"yahoo_{fname}.csv")
            ok.append(symbol)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED {symbol}: {exc}")
            failed.append(symbol)
        time.sleep(1.0)

    # Shiller's long-term dataset (old .xls format); current host is shillerdata.com (WSOL blob CDN)
    shiller_urls = [
        "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/1449043e-a1ed-4e2e-8e9c-7b9a2a064493/ie_data.xls",
        "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
    ]
    for url in shiller_urls:
        try:
            fetch(url, OUTDIR / "ie_data.xls")
            ok.append("ie_data.xls")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED shiller: {exc}")
            failed.append("ie_data.xls")

    print("\n=== summary ===")
    print("ok    :", ", ".join(ok))
    print("failed:", ", ".join(failed) if failed else "(none)")


if __name__ == "__main__":
    main()
