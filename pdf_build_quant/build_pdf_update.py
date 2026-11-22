# -*- coding: utf-8 -*-
"""Build the 2026-11-21 follow-up report PDF (same pipeline as build_pdf.py,
which produced the frozen 11/8 original — that script is left untouched):
markdown -> pandoc HTML (styled) -> Edge headless print-to-pdf ->
cover via PDF skill template -> merge with bookmarks + page numbers -> qpdf.
Run with SYSTEM python (reportlab/pymupdf).
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

MD = os.path.join(ROOT, "量化類比推論更新報告_20261121.md")
STYLE = os.path.join(BUILD, "report_style_update.html")
BODY_HTML = os.path.join(BUILD, "body_update.html")
BODY_PDF = os.path.join(BUILD, "body_update.pdf")
COVER_PDF = os.path.join(BUILD, "cover_update.pdf")
FINAL = os.path.join(ROOT, "量化類比推論更新報告_20261121.pdf")

TITLE = "量化類比推論更新報告：黃仁勳辭職後的十一天"
SUBJECT = "2026-11-12 至 11-20 重大進展之量化後驗更新（距峰頂百分比口徑）"

H1S = [
    ("核心預測（先讀這節）：本波破裂何時落底、會落多深", "核心預測（先讀這節）"),
    ("一、現況快照：三個標的的三種深度", "一、現況快照"),
    ("二、事件簿：11/10–11/20（接續 11/8 版附錄）", "二、事件簿"),
    ("三、對 11/8 版報告的誠實計分卡", "三、對 11/8"),
    ("四、類比層更新：以新位置為條件的統計", "四、類比層"),
    ("五、統計層與後驗更新：E1 出局後的三元分割", "五、統計層"),
    ("六、時點更新：市場把「可能」變成「正在」", "六、時點更新"),
    ("七、與名家觀點的數字對照（更新版）", "七、與名家"),
    ("八、限制與誠實聲明（新增與延續並列）", "八、限制"),
    ("九、資料與程式碼", "九、資料"),
    ("十、結語：把預測說清楚", "十、結語"),
]
H2S = [
    ("何時落底（時點機率分布，合計 100%）", "何時落底（時點機率分布"),
    ("落多深（終點深度機率，2026-11-21 後驗）", "落多深（終點深度機率"),
    ("事件 3：護盤反彈觸頂回落（11/9–11/11）", "事件 3"),
    ("事件 4：黃仁勳辭職（11/12）——key-man 風險以最高等級兌現", "事件 4"),
    ("事件 5：完美財報被賣掉（11/17–11/20）——GSY 的反直覺發現現身", "事件 5"),
    ("5.1 更新方法（可重現）", "5.1 更新方法"),
    ("5.2 更新後情境矩陣（NDX 終點深度，點機率合計 100%）", "5.2 更新後情境"),
    ("5.3 敏感度分析（更新版）", "5.3 敏感度"),
    ("5.4 觸發變數表（重寫版）", "5.4 觸發變數"),
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
    html = re.sub(r'src="(quant/output_update/figs/[^"]+)"', repl, html)
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
    pages = {}
    for title, key in H1S + H2S:
        for pno in range(1, len(bod)):
            if bod[pno].search_for(key):
                pages[title] = pno + 2
                break
    for pno in range(1, len(bod)):
        if bod[pno].search_for("量化類比推論更新報告"):
            pages[TITLE] = pno + 2
            break
    return pages


def inject_toc_pages(pages: dict[str, int]) -> None:
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
    "kicker": "QUANT ANALOG REPORT · FOLLOW-UP · 後續報告",
    "hero": "更新報告",
    "summary": "黃仁勳辭職後的十一天：政策反彈觸頂（11/9-11/11）、key-man 風險兌現（11/12）、"
               "完美財報被賣掉（11/17-11/20）。以「距峰頂百分比」的同一把尺重估：NVDA 已越過 -40% "
               "終結性崩盤線、台股進入 -25~-40% 深度修正帶、NDX 終點深於 -25% 的機率上修至 66%；"
               "本輪谷底最可能（合計 80%）落在 2026-12 至 2027Q1（中位數 2026-12-20）。"
               "並對 11/8 版報告逐條計分（10/11 命中）。",
    "meta": "作者：Charlie Chu（charliechu1688@gmail.com）· 經濟循環研究<br/>報告日期：2026 年 11 月 21 日 · "
            "資料截至 2026-11-20 收盤 · 前置報告（11/8）已凍結為歷史證據（tag freeze-20261109）",
    "footer": "ECONOMIC CYCLES RESEARCH · 2026.11",
    "year": "2026",
    "word": "UPDATE",
}
cover_palette = {"primary": "#7a4a3a", "secondary": "#96604d", "text": "#151617",
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

# ─────────────────────────────────────────────── qpdf owner-lock (same as original)
OWNER_PW = "1031126"
subprocess.run([
    "qpdf",
    "--encrypt", "", OWNER_PW, "256",
    "--print=none", "--modify=none", "--extract=n",
    "--", FINAL, FINAL + ".enc",
], check=True, capture_output=True)
os.replace(FINAL + ".enc", FINAL)
chk = pymupdf.open(FINAL)
assert not chk.needs_pass, "PDF should open without a password"
assert chk.authenticate(OWNER_PW) > 0, "owner password check failed"
print(f"protected OK: opens freely, print/copy/modify disabled, AES-256, pages={len(chk)}")
