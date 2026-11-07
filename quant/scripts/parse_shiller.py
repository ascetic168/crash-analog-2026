# -*- coding: utf-8 -*-
"""Parse Shiller ie_data.xls into a clean monthly CSV and sanity-check key rows.

ie_data.xls layout (sheet 'Data'):
  row 1: title, row 3-4: column headers, data starts row 8 (index 7)
  cols: Date | P | D | E | CPI | Date Fraction | Rate GS10 | Real P | Real D |
        Real E | CAPE | (returns...) | TR PI | Real TR PI | Real TR Scaled | CAPE Yield
  Date column is like 1871.01 (float) or 2026.10.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
xls_path = DATA / "downloads" / "ie_data.xls"
out_path = DATA / "shiller_monthly.csv"

raw = pd.read_excel(xls_path, sheet_name="Data", header=None)

# positional layout (verified against 2000.01 row):
# 0 Date | 1 P | 2 D | 3 E | 4 CPI | 5 Fraction | 6 Rate GS10 |
# 7 Real Price | 8 Real Dividend | 9 Real TR Price | 10 Real TR Earnings |
# 11 Scaled Earnings | 12 CAPE
hdr_idx = 7
df = raw.iloc[hdr_idx + 1 :, :13].copy()
df.columns = ["d", "price", "dividend", "earnings", "cpi", "frac", "gs10",
              "real_price", "real_div", "real_tr_price", "real_tr_e", "scaled_e", "cape"]
df["d"] = pd.to_numeric(df["d"], errors="coerce")
df = df.dropna(subset=["d"])
for c in df.columns[1:]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# build a proper date: 1871.01 -> 1871-01 (mid-month convention: use month start)
year = df["d"].astype(int)
month = ((df["d"] - year) * 100 + 0.5).astype(int).clip(1, 12)
df["date"] = pd.to_datetime(dict(year=year, month=month, day=1))

df = df.sort_values("date").reset_index(drop=True)

# real earnings = nominal E scaled by CPI base (latest CPI in file), Shiller convention
cpi_base = df["cpi"].dropna().iloc[-1]
df["real_earnings"] = df["earnings"] * cpi_base / df["cpi"]
# my own CAPE cross-check: price / 10y MA of real earnings
df["re_ma10"] = df["real_earnings"].rolling(120).mean()
df["cape_own"] = df["price"] / df["re_ma10"]

out = df[["date", "price", "dividend", "earnings", "cpi", "gs10",
          "real_price", "real_earnings", "cape", "cape_own"]]
out.to_csv(out_path, index=False)

print(f"\nsaved {out_path} rows={len(out)}")
print("\n== last 6 months ==")
print(out.tail(6).to_string(index=False))

print("\n== key historical CAPE peaks ==")
for label, lo, hi in [("1929 peak", "1929-01-01", "1930-01-01"),
                      ("1973 peak", "1972-06-01", "1973-03-01"),
                      ("2000 peak", "1999-06-01", "2000-06-01"),
                      ("2007 peak", "2007-01-01", "2007-12-01"),
                      ("2021 peak", "2021-09-01", "2022-01-01")]:
    sub = out[(out.date >= lo) & (out.date <= hi)]
    if len(sub):
        row = sub.loc[sub.cape.idxmax()]
        print(f"{label}: {row.date:%Y-%m} CAPE={row.cape:.2f} price={row.price:.2f} gs10={row.gs10:.2f}")

cur = out.iloc[-1]
print(f"\nlatest: {cur.date:%Y-%m} CAPE={cur.cape:.2f} price={cur.price:.2f} gs10={cur.gs10:.2f}")
ecy = 100 / cur.cape
print(f"trailing CAPE earnings yield = {ecy:.2f}% vs GS10 {cur.gs10:.2f}% -> nominal ECY = {ecy - cur.gs10:.2f}%")
