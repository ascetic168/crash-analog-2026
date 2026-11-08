# crash-analog-2026 · 量化崩盤類比管線

以四層量化管線（**資料 → 指標 → 類比 → 統計**）比較 2026 年 AI 行情與 1929/1973/1987/2000/2007/2021 六次歷史崩盤，
產出跌幅 × 時點的機率分布。全部數字來自公開資料，可由本 repo 的程式碼完整重現。

A four-layer quantitative pipeline (data → indicators → analogs → statistics) comparing the
2026 AI market with six historical crashes. Every number is reproducible from public data.

**作者 / Author**: Charlie Chu (charliechu1688@gmail.com)

---

## repo 內容 / Contents

| 路徑 | 內容 |
|---|---|
| `quant/scripts/` | 全部管線程式碼（Python，pandas/numpy/scipy/matplotlib） |
| `quant/data/downloads/` | 原始資料：Shiller `ie_data.xls`、FRED CSV、Yahoo Finance 日 K |
| `quant/data/shiller_monthly.csv` | Shiller xls 解析後的乾淨月資料 |
| `quant/output/` | 全部計算產物：指標 JSON、類比 episodes CSV、LPPL/GSY 統計 JSON、圖表 PNG |
| `quant/dashboard/index.html` | 互動儀表板（d3 已內嵌，離線可用；瀏覽器直接開啟） |
| `docs/index.html` | 同上（GitHub Pages 用） |
| `量化類比推論報告_20261108.pdf` | 整合報告（**owner-locked**：可自由閱讀，複製/列印受保護限制） |

## 核心產物 / Key outputs

- `quant/output/metrics_current.json` — CAPE / ECY / 市值 GDP 比 / GSY 暴漲變數的現值 vs 五次崩盤前夕
- `quant/output/analogs_*.csv|json` — 13 個歷史崩盤 episode（按距峰月數對齊）＋條件化前向統計
- `quant/output/stats_layer.json` — GSY 產業籃子檢定＋LPPL 對數週期冪律擬合（含 1999 年 NDX 驗證）
- `quant/output/scenario_posterior.json` — 情境機率的 coherent 後驗（Dirichlet，點機率合計 1.000）

## 重現步驟 / Reproduce

```bash
python -m venv quant/.venv
quant/.venv/Scripts/pip install pandas numpy scipy matplotlib openpyxl xlrd requests
quant/.venv/Scripts/python quant/scripts/download_data.py        # 1. 下載全部原始資料
quant/.venv/Scripts/python quant/scripts/parse_shiller.py        # 2. 解析 Shiller xls
quant/.venv/Scripts/python quant/scripts/build_metrics.py        # 3. 指標層
quant/.venv/Scripts/python quant/scripts/build_analogs.py        # 4. 類比層
quant/.venv/Scripts/python quant/scripts/build_stats_layer.py    # 5. GSY + LPPL（含 1999 驗證）
quant/.venv/Scripts/python quant/scripts/build_scenario_posterior.py  # 6. 情境後驗
quant/.venv/Scripts/python quant/scripts/bundle_dashboard_data.py     # 7. 儀表板資料
```

（Windows 路徑分隔符；Linux/macOS 將 `quant/.venv/Scripts/` 換為 `quant/.venv/bin/`。）

## 方法要點 / Method notes

- **指標層**：CAPE 40.71（1871 年起 99 百分位）、Z.1 非金融市值/GDP 2.55（1945 年起最高）、名目 ECY −2.78%
- **類比層**：以「觸及 −X% 深度」為條件的經驗前向分布（NDX n=35、TAIEX n=8、NVDA n=17）
- **統計層**：GSY（Greenwood–Shleifer–You 2019）產業籃子檢定（AI 基礎設施籃子兩年 +223.8%）；
  LPPL 對數週期冪律擬合先以 1999 年 NDX 驗證（tc 誤差帶 ±3–6 個月）再應用於 2026
- **情境後驗**：互斥窮盡分割（E1–E4）＋三條證據流明示權重混合＋Dirichlet(k=24) 邊際區間；
  證據流對深尾的分歧（6.7% vs 48.8%）如實呈現於敏感度表

## 資料來源 / Data sources

- [Robert Shiller, *Irrational Exuberance* data](https://shillerdata.com/)（ie_data.xls）
- [FRED](https://fred.stlouisfed.org/)：NASDAQCOM, GDP, NCBCEL, BOGZ1FL663067003Q, GS10, CPILFESL
- [Yahoo Finance](https://finance.yahoo.com/)：^GSPC, ^DJI, ^NDX, ^TWII, ^N225 及 13 檔個股日 K

以上第三方資料之授權與使用條款依各來源規定；本 repo 程式碼以 MIT 授權釋出（見 `LICENSE`）。

## 免責聲明 / Disclaimer

本 repo 為學術性研究重現，**非投資建議**。歷史類比不保證未來重演；所有機率皆為模型化推論，
含明示的假設與小樣本限制（詳見報告第 7 節）。
