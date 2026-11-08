# -*- coding: utf-8 -*-
"""Build the quantitative analog report PDF:
markdown -> pandoc HTML (styled) -> Edge headless print-to-pdf ->
cover via PDF skill template -> merge with bookmarks + page numbers.

Two-pass: pass A locates section pages, injects TOC page numbers, pass B
re-renders before merging. Run with SYSTEM python (reportlab/pymupdf).
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BUILD)
PDF_SKILL = r"C:\Users\charl\.zcode\cli\plugins\cache\zcode-plugins-official\pdf\0.2.2\skills\pdf"
PANDOC = r"C:\Users\charl\AppData\Local\Pandoc\pandoc"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

sys.path.insert(0, os.path.join(PDF_SKILL, "scripts"))

MD = os.path.join(ROOT, "量化類比推論報告_20261108.md")
STYLE = os.path.join(BUILD, "report_style.html")
BODY_HTML = os.path.join(BUILD, "body.html")
BODY_PDF = os.path.join(BUILD, "body.pdf")
COVER_PDF = os.path.join(BUILD, "cover.pdf")
FINAL = os.path.join(ROOT, "量化類比推論報告_20261108.pdf")

TITLE = "量化類比推論報告：以數學方法比較 2026 年 AI 泡沫與歷史崩盤"
SUBJECT = "四層量化管線（資料/指標/類比/統計）之整合推論"

# (bookmark title, short search key) — long headings may wrap, breaking full-string search
H1S = [
    ("一、方法論總覽", "一、方法論"),
    ("二、指標層：現在 vs 五次崩盤前夕", "二、指標層"),
    ("三、類比層：歷史軌跡對齊與條件化分布", "三、類比層"),
    ("四、統計層：GSY 崩盤機率變數與 LPPL 臨界時點", "四、統計層"),
    ("五、整合推論：跌幅 × 時點的機率矩陣", "五、整合推論"),
    ("六、與名家觀點的數字對照", "六、與名家"),
    ("七、限制與誠實聲明", "七、限制"),
    ("八、資料與程式碼", "八、資料"),
]
H2S = [
    ("2.1 估值指標（Shiller 月資料，1871 年起）", "2.1 估值指標"),
    ("2.2 廣度與槓桿（Z.1 季資料，1945 年起）", "2.2 廣度與槓桿"),
    ("2.3 GSY 暴漲變數（指數層級）", "2.3 GSY 暴漲"),
    ("2.4 現況快照（2026-11-06 收盤，距共同峰頂 2026-10-06 剛好一個月）", "2.4 現況快照"),
    ("3.1 歷史崩盤 episode 對照（十個歷史案例，已對照史實驗證）", "3.1 歷史崩盤"),
    ("3.2 條件化前向統計（本節是「量化類比」的核心）", "3.2 條件化前向"),
    ("4.1 GSY 產業籃子（等權、以 2026-10-06 為觀測點）", "4.1 GSY 產業"),
    ("4.2 LPPL 對數週期冪律（方法先驗證，再應用）", "4.2 LPPL 對數"),
    ("5.1 情境矩陣（NDX 終點深度分割，點機率合計 100%）", "5.1 情境矩陣"),
    ("5.2 時點分布（歸一的時間分割，合計 100%）", "5.2 時點分布"),
    ("5.3 對關鍵數字的直接量化陳述（依 5.1 後驗更新）", "5.3 對關鍵數字"),
    ("5.4 敏感度分析（哪些假設會翻轉結論）", "5.4 敏感度分析"),
]


def pandoc_md() -> None:
    subprocess.run([
        PANDOC, MD,
        "-f", "markdown+raw_html",
        "-t", "html5",
        "-s",
        "--toc", "--toc-depth=2",
        "--include-in-header", STYLE,
        "--metadata", f"title={TITLE}",
        "-o", BODY_HTML,
    ], check=True, cwd=ROOT)


def fix_image_srcs() -> None:
    """Rewrite relative fig paths to absolute file:// URIs so Edge can load them."""
    html = Path(BODY_HTML).read_text(encoding="utf-8")
    def repl(m):
        return f'src="{(Path(ROOT) / m.group(1)).as_uri()}"'
    html = re.sub(r'src="(quant/output/figs/[^"]+)"', repl, html)
    Path(BODY_HTML).write_text(html, encoding="utf-8")


def edge_print(out_pdf: str) -> None:
    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            EDGE,
            "--headless", "--disable-gpu",
            "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={profile}",
            "--no-pdf-header-footer",
            "--virtual-time-budget=10000",
            f"--print-to-pdf={out_pdf}",
            "file:///" + BODY_HTML.replace("\\", "/"),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def find_pages(bod) -> dict[str, int]:
    """Map heading search keys to 1-based merged page numbers (skip TOC page 0)."""
    pages = {}
    for title, key in H1S + H2S:
        for pno in range(1, len(bod)):
            if bod[pno].search_for(key):
                # merged numbering: cover(0) + body pno -> 1-based page = pno + 2
                pages[title] = pno + 2
                break
    # the document title heading itself (first TOC entry)
    for pno in range(1, len(bod)):
        if bod[pno].search_for("量化類比推論報告"):
            pages[TITLE] = pno + 2
            break
    return pages


def inject_toc_pages(pages: dict[str, int]) -> None:
    """Append <span class="tocpg">N</span> after each matching TOC anchor.
    Pandoc wraps anchor text across lines, so compare with whitespace stripped."""
    html = Path(BODY_HTML).read_text(encoding="utf-8")
    m = re.search(r'<nav id="TOC".*?</nav>', html, re.S)
    if not m:
        print("WARNING: no TOC nav found")
        return
    nav = m.group(0)
    inv = {re.sub(r"\s+", "", t): p for t, p in pages.items()}
    count = 0

    def repl(mm):
        nonlocal count
        key = re.sub(r"\s+", "", mm.group(2))
        if key in inv:
            count += 1
            return mm.group(1) + mm.group(2) + mm.group(3) + f'<span class="tocpg">{inv[key]}</span>'
        return mm.group(0)

    nav2 = re.sub(r'(<a href="#[^"]*"[^>]*>)(.*?)(</a>)', repl, nav, flags=re.S)
    html = html.replace(m.group(0), nav2)
    Path(BODY_HTML).write_text(html, encoding="utf-8")
    print(f"TOC page numbers injected: {count}")


def stamp_page_numbers(doc, skip_first: int = 1) -> None:
    """Footer '第 N 頁 · 共 M 頁' on every page after the cover."""
    total = len(doc)
    for i in range(skip_first, total):
        page = doc[i]
        w, h = page.rect.width, page.rect.height
        text = f"第 {i + 1} 頁 · 共 {total} 頁"
        tw = pymupdf.get_text_length(text, fontname="china-t", fontsize=8)
        page.insert_text((w - 46 - tw, h - 30), text,
                         fontname="china-t", fontsize=8, color=(0.46, 0.49, 0.50))


# ─────────────────────────────────────────────── pass A: locate sections
pandoc_md()
fix_image_srcs()
edge_print(BODY_PDF)
import pymupdf  # noqa: E402
bod_a = pymupdf.open(BODY_PDF)
pages = find_pages(bod_a)
bod_a.close()
print("section pages:", {k[:6]: v for k, v in pages.items()})

# ─────────────────────────────────────────────── pass B: TOC numbers + re-render
inject_toc_pages(pages)
edge_print(BODY_PDF)

# ─────────────────────────────────────────────── cover + merge
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402

pdfmetrics.registerFont(TTFont("JhengHei", "C:/Windows/Fonts/msjh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("JhengHeiBold", "C:/Windows/Fonts/msjhbd.ttc", subfontIndex=0))

from cover_render import render_cover  # noqa: E402

cover_content = {
    "kicker": "QUANTITATIVE ANALOG REPORT · 量化類比推論",
    "hero": "量化類比推論",
    "summary": "以四層量化管線（資料 → 指標 → 類比 → 統計）比較 2026 年 AI 行情與 1929/1973/1987/2000/2007/2021 "
               "六次歷史崩盤：CAPE 40.71、非金融市值/GDP 史上最高、AI 基礎設施籃子兩年 +224%，"
               "LPPL 臨界時點與 GSY 崩盤機率變數的整合推論，以及跌幅 × 時點的機率矩陣。",
    "meta": "作者：Charlie Chu（charliechu1688@gmail.com）· 經濟循環研究<br/>報告日期：2026 年 11 月 8 日 · "
            "資料：Shiller / FRED / Yahoo Finance · 全部可重現（quant/ 目錄）",
    "footer": "ECONOMIC CYCLES RESEARCH · 2026.11",
    "year": "2026",
    "word": "RESEARCH",
}
cover_palette = {"primary": "#496573", "secondary": "#578095", "text": "#151617",
                 "muted": "#757c7f", "bg": "#ffffff"}
fonts = {"sans": "JhengHei", "serif": "JhengHei", "kai": "JhengHei", "latin": "JhengHei"}
render_cover("03", cover_content, COVER_PDF, palette=cover_palette, fonts=fonts)
print("cover OK:", COVER_PDF)

fdoc = pymupdf.open()
cov = pymupdf.open(COVER_PDF)
bod = pymupdf.open(BODY_PDF)
fdoc.insert_pdf(cov, from_page=0, to_page=0)
fdoc.insert_pdf(bod)

toc = [[1, TITLE, 1]]
for title, _key in H1S:
    if title in pages:
        toc.append([1, title, pages[title]])
fdoc.set_toc(toc)
stamp_page_numbers(fdoc, skip_first=1)
fdoc.set_metadata({"title": TITLE, "author": "Charlie Chu", "creator": "Charlie Chu",
                   "subject": SUBJECT, "producer": "http://z.ai"})
TMP = FINAL + ".tmp"
fdoc.save(TMP, garbage=3, deflate=True)
fdoc.close()
os.replace(TMP, FINAL)
n = len(pymupdf.open(FINAL))
print(f"final OK: {FINAL} pages={n} bookmarks={len(toc) - 1}")
