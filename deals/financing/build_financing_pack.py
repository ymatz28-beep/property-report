#!/usr/bin/env python3
"""
融資打診パッケージ HTML 生成
------------------------------------------------------------
deals/financing/*.md（00_playbook / 01_jfc / 02_shiga）を読み、
印刷もスマホ閲覧もできる1枚の印刷向けHTMLに束ねる。
出力: output/financing-<deal>.html （deploy_private が /property/ へ配信）

Usage: python deals/financing/build_financing_pack.py
"""
from __future__ import annotations
import re, html, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # property-analyzer/
FIN_DIR = ROOT / "deals" / "financing"
OUT = ROOT / "output" / "financing-placespot-shinbashi.html"
PDF_OUT = ROOT / "output" / "financing-placespot-shinbashi.pdf"
PDF_NAME = PDF_OUT.name
FILES = ["00_playbook.md", "01_jfc_旅館業_事業計画書.md", "02_shiga_賃貸_打診パッケージ.md",
         "03_リノベ相見積_インダストリアル.md", "04_運営代行_候補と相場.md",
         "05_補助金_使えるもの全部.md", "06_スケジュール_発注タイミング.md",
         "07_相談先メール下書き.md"]

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def make_pdf() -> bool:
    """HTMLからChrome headlessでPDFを生成（印刷・提出用）。Chrome無ければスキップ。"""
    chrome = next((c for c in CHROME_CANDIDATES if Path(c).exists()), None)
    if not chrome:
        print("[pdf] Chrome未検出のためPDF生成スキップ（HTMLの🖨ボタンで保存可）")
        return False
    r = subprocess.run([
        chrome, "--headless", "--disable-gpu", "--no-sandbox",
        f"--print-to-pdf={PDF_OUT}", "--no-pdf-header-footer",
        f"file://{OUT}",
    ], capture_output=True)
    ok = PDF_OUT.exists() and r.returncode == 0
    print(f"[pdf] {'generated: '+str(PDF_OUT.resolve()) if ok else 'failed'}")
    return ok


def md_to_html(md: str) -> str:
    """最小限の Markdown→HTML（見出し/表/リスト/引用/太字/段落）。"""
    lines = md.split("\n")
    out, i = [], 0
    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"(https?://[^\s)]+)", r'<a href="\1">\1</a>', s)
        return s
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1; continue
        # table block
        if ln.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i+1]):
            header = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = "<table><thead><tr>" + "".join(f"<th>{inline(h)}</th>" for h in header) + "</tr></thead><tbody>"
            for r in rows:
                t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
            t += "</tbody></table>"
            out.append(t); continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").rstrip()); i += 1
            out.append(f'<blockquote>{inline(" ".join(buf))}</blockquote>'); continue
        if re.match(r"^\s*[-*]\s+", ln) or re.match(r"^\s*\d+\.\s+", ln):
            ordered = bool(re.match(r"^\s*\d+\.\s+", ln))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and (re.match(r"^\s*[-*]\s+", lines[i]) or re.match(r"^\s*\d+\.\s+", lines[i])):
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[i])); i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>"); continue
        if re.match(r"^---+$", ln):
            out.append("<hr>"); i += 1; continue
        out.append(f"<p>{inline(ln)}</p>"); i += 1
    return "\n".join(out)


def main() -> int:
    sections = []
    for f in FILES:
        p = FIN_DIR / f
        if p.exists():
            sections.append(md_to_html(p.read_text(encoding="utf-8")))
    body = '\n<hr class="sec">\n'.join(sections)
    doc = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>融資打診パッケージ — プレイスポットしんばし</title>
<style>
body{{font-family:'Hiragino Sans','Noto Sans JP',sans-serif;max-width:840px;margin:0 auto;padding:28px 20px;color:#1a1a1a;line-height:1.7;background:#fff}}
h1{{font-size:22px;border-bottom:3px solid #c9a84c;padding-bottom:6px;margin-top:8px}}
h2{{font-size:18px;border-left:5px solid #c9a84c;padding-left:10px;margin-top:28px}}
h3{{font-size:15px;margin-top:20px;color:#333}}
h4{{font-size:14px;margin-top:14px;color:#555}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}}
th,td{{border:1px solid #ccc;padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:#f4efe2}}
blockquote{{background:#fff8e6;border-left:4px solid #c9a84c;margin:12px 0;padding:8px 14px;font-size:13px;color:#5a4a1a}}
code{{background:#f0f0f0;padding:1px 5px;border-radius:4px;font-size:12px}}
ul,ol{{padding-left:22px}}
li{{margin:3px 0}}
hr{{border:none;border-top:1px solid #ddd;margin:16px 0}}
hr.sec{{border-top:2px dashed #c9a84c;margin:36px 0}}
a{{color:#1e5fb4;word-break:break-all}}
.toolbar{{position:sticky;top:0;background:#1a1d27;margin:-28px -20px 18px;padding:12px 20px;display:flex;gap:10px;flex-wrap:wrap;z-index:10}}
.toolbar button,.toolbar a{{background:#c9a84c;color:#1a1207;font-weight:700;border:none;padding:10px 16px;border-radius:9px;font-size:14px;text-decoration:none;cursor:pointer}}
.toolbar a.alt{{background:#242836;color:#e4e4e7}}
@media print{{.toolbar{{display:none}}body{{padding:0}}h2{{page-break-before:auto}}a{{color:#1a1a1a}}}}
@media(max-width:700px){{body{{padding:14px}}.toolbar{{margin:-14px -14px 16px;padding:10px 14px}}h1{{font-size:19px}}h2{{font-size:16px}}
  table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}}
  table thead,table tbody{{display:table;width:100%;min-width:520px}}}}
</style></head><body>
<div class="toolbar">
  <button onclick="window.print()">🖨 印刷 / PDFで保存</button>
  <a class="alt" href="{PDF_NAME}" download>⬇ PDFをダウンロード</a>
</div>
{body}
<hr class="sec">
<p style="font-size:11px;color:var(--text-muted)">生成: property-analyzer/deals/financing/。数字の[要記入]はYumaの実数で更新する。各金融機関の融資条件は要直接照会。</p>
</body></html>"""
    OUT.write_text(doc, encoding="utf-8")
    print(f"generated: {OUT.resolve()}")
    make_pdf()
    subprocess.run(["open", str(OUT.resolve())])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
