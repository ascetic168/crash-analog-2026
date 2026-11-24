# -*- coding: utf-8 -*-
"""Build the 2026-11-24 "bear-market big up days" report PDF (same pipeline as
build_pdf_update.py, which produced the 11/21 follow-up):
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

MD = os.path.join(ROOT, "跌勢中的大漲_dotcom對照_20261124.md")
STYLE = os.path.join(BUILD, "report_style_rallies.html")
BODY_HTML = os.path.join(BUILD, "body_rallies.html")
BODY_PDF = os.path.join(BUILD, "body_rallies.pdf")
COVER_PDF = os.path.join(BUILD, "cover_rallies.pdf")
FINAL = os.path.join(ROOT, "跌勢中的大漲_dotcom對照_20261124.pdf")

TITLE = "跌勢中的大漲：dot-com 循環的對照清單"
SUBJECT = "2000–2002 那斯達克與 2000–2001 台股崩盤期『跌勢中大漲』的事件研究（距峰頂百分比口徑）"

# section titles exactly as written in the markdown (the TOC matcher strips whitespace)
H1S = [
    ("核心結論（先讀這節）", "核心結論（先讀這節）"),
    ("一、今天發生什麼事：資料確認", "一、今天發生什麼事"),
    ("二、NDX 崩盤期的 24 波「跌勢中的大漲」", "二、NDX 崩盤期"),
    ("三、每一波的故事：時間點、發生了什麼事、後來呢", "三、每一波的故事"),
    ("四、龍頭股對照：當年的 Cisco、Intel，與今天的 NVIDIA", "四、龍頭股對照"),
    ("五、台股 2000–2001 的對照", "五、台股 2000"),
    ("六、跨歷史基礎率：大跌之後的單日大漲，是不是落底訊號", "六、跨歷史基礎率"),
    ("七、與今天的異同（誠實的限制）", "七、與今天的異同"),
    ("八、資料與程式碼", "八、資料與程式碼"),
]
H2S = []


def pandoc_md() -> None:
    subprocess.run([
        PANDOC, MD,
        "-f", "markdown+raw_html",
        "-t", "html5",
        "-s",
        "--toc", "--toc-depth=1",
        "--include-in-header", STYLE,
        "--metadata", f"title={TITLE}",
        "-o", BODY_HTML,
    ], check=True, cwd=ROOT)


def fix_image_srcs() -> None:
    """Rewrite relative fig paths to absolute file:// URIs so Edge can load them."""
    html = Path(BODY_HTML).read_text(encoding="utf-8")
    def repl(m):
        return f'src="{(Path(ROOT) / m.group(1)).as_uri()}"'
    html = re.sub(r'src="(quant/output_rallies/figs/[^"]+)"', repl, html)
    Path(BODY_HTML).write_text(html, encoding="utf-8")


def tidy_tables() -> None:
    """Keep ISO dates and year-month labels on one line (nowrap spans) and flag
    7+-column tables so the stylesheet can shrink them; this report's generated
    tables are up to 9 wide. Only short parentheticals stay glued to their date —
    a long one would become an unbreakable line wider than the page."""
    html = Path(BODY_HTML).read_text(encoding="utf-8")
    date = re.compile(r"(\d{4}-\d{2}-\d{2}(?:（[^<]{0,10}）)?)|(?<![\d-])(?:\d{4}|\d{2})-\d{2}(?![\d-])")
    parts = re.split(r"(<[^>]+>)", html)
    in_style = False
    for i, part in enumerate(parts):
        if part.startswith("<"):
            in_style = part.startswith("<style") or (in_style and not part.startswith("</style"))
        elif not in_style:
            parts[i] = date.sub(lambda m: f'<span class="nw">{m.group(0)}</span>', part)
    html = "".join(parts)

    def wide(m):
        n = len(re.findall(r"<th[^>]*>", m.group(0)))
        return m.group(0).replace("<table", '<table class="wide"', 1) if n >= 7 else m.group(0)

    html = re.sub(r"<table>.*?</thead>", wide, html, flags=re.S)
    # pandoc computes column widths from the markdown source and fixes them in a
    # <colgroup>; combined with single-line headers that overflows the text
    # column (clipped last column + a printed scrollbar). Let the layout engine
    # distribute width by content instead.
    html = re.sub(r"<colgroup>.*?</colgroup>", "", html, flags=re.S)
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
    """pandoc prints the TOC before the front matter, and a long TOC spans two
    pages — start looking where the front matter begins, not right after page 1."""
    pages = {}
    start = next(i for i in range(len(bod)) if bod[i].search_for("報告日期"))
    for title, key in H1S + H2S:
        for pno in range(start, len(bod)):
            if bod[pno].search_for(key):
                pages[title] = pno + 2
                break
    for pno in range(start, len(bod)):
        if bod[pno].search_for("跌勢中的大漲：dot-com"):
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
tidy_tables()
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
    "kicker": "QUANT EVENT STUDY · 歷史對照 · 事件研究",
    "hero": "對照清單",
    "summary": "黃仁勳回任、美股與台股大漲之後的歷史對照：NDX 在 2000–2002 崩盤期有 41 個單日漲幅 5% 以上的交易日"
               "（24 波），台股 2000–2001 有 22 個（12 波），合計 63 個大漲日事後全部再跌破反彈前的低點。"
               "本報告逐波整理時間點、觸發事件與事後走勢，並用跨歷史基礎率回答「大跌後的單日大漲是不是落底訊號」。",
    "meta": "作者：Charlie Chu（charliechu1688@gmail.com）· 經濟循環研究<br/>報告日期：2026 年 11 月 24 日 · "
            "美股資料截至 2026-11-23 收盤 · 台股截至 2026-11-24 盤中／收盤（詳見內文）",
    "footer": "ECONOMIC CYCLES RESEARCH · 2026.11",
    "year": "2026",
    "word": "RALLY",
}
cover_palette = {"primary": "#2f4f6f", "secondary": "#4a6b8a", "text": "#151617",
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

# ─────────────────────────────────────────────── qpdf owner-lock (same as the other reports)
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
