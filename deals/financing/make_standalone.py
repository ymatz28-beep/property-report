#!/usr/bin/env python3
"""
単一 .md → 単独で渡せる A4 印刷用 HTML＋PDF を生成。
見積依頼書（工務店送付用）や公庫提出用など「1枚で完結して相手に渡す」資料向け。

Usage:
  python deals/financing/make_standalone.py <input.md> <output.html> "タイトル"
"""
from __future__ import annotations
import sys, subprocess
from pathlib import Path
from build_financing_pack import md_to_html, CHROME_CANDIDATES  # 同ディレクトリの整形ロジックを再利用

CSS = """
body{font-family:'Hiragino Sans','Noto Sans JP',sans-serif;max-width:800px;margin:0 auto;padding:32px 26px 64px;color:#1a1a1a;line-height:1.75;background:#fff}
h1{font-size:21px;border-bottom:3px solid #c9a84c;padding-bottom:8px;margin:4px 0 18px}
h2{font-size:16px;border-left:5px solid #c9a84c;padding-left:10px;margin-top:24px}
h3{font-size:14px;margin-top:16px;color:#333}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:12.5px}
th,td{border:1px solid #ccc;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f4efe2}
blockquote{background:#fff8e6;border-left:4px solid #c9a84c;margin:10px 0;padding:8px 13px;font-size:12.5px;color:#5a4a1a}
code{background:#f0f0f0;padding:1px 5px;border-radius:4px;font-size:12px}
ul,ol{padding-left:22px} li{margin:3px 0}
hr{border:none;border-top:1px solid #ddd;margin:14px 0}
a{color:#1e5fb4;word-break:break-all}
.codewrap{position:relative;margin:10px 0}
.copybtn{position:absolute;top:6px;right:6px;background:#c9a84c;color:#1a1207;border:none;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:700;cursor:pointer}
.copybtn.done{background:#2faa55;color:#fff}
pre.code{background:#0f1117;color:#e6e8ee;padding:28px 13px 13px;border-radius:9px;overflow-x:auto;font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word;font-family:'SFMono-Regular',Consolas,Menlo,monospace}
.bar{position:sticky;top:0;background:#1a1d27;margin:-32px -26px 18px;padding:11px 26px;display:flex;gap:10px}
.bar button{background:#c9a84c;color:#1a1207;font-weight:700;border:none;padding:9px 15px;border-radius:9px;font-size:14px;cursor:pointer}
@media print{.bar,.copybtn{display:none}body{padding:0}}
@media(max-width:700px){body{padding:14px}.bar{margin:-14px -14px 14px;padding:10px 14px}table{display:block;overflow-x:auto}}
"""

JS = """
<script>
(function(){
 function fb(t,ok){var a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.focus();a.select();try{document.execCommand('copy');ok();}catch(e){}document.body.removeChild(a);}
 [].slice.call(document.querySelectorAll('.copybtn')).forEach(function(b){b.addEventListener('click',function(){var p=b.parentNode.querySelector('pre.code'),t=p.innerText;function ok(){var o=b.textContent;b.textContent='✓ コピー済';b.classList.add('done');setTimeout(function(){b.textContent=o;b.classList.remove('done');},1500);}if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,function(){fb(t,ok);});}else{fb(t,ok);}});});
})();
</script>
"""


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: make_standalone.py <input.md> <output.html> <title>"); return 1
    src, out, title = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
    out.parent.mkdir(parents=True, exist_ok=True)
    body = md_to_html(src.read_text(encoding="utf-8"))
    doc = (f'<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
           f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
           f'<title>{title}</title><style>{CSS}</style></head><body>'
           f'<div class="bar"><button onclick="window.print()">\U0001f5a8 印刷 / PDFで保存</button></div>'
           f'{body}{JS}</body></html>')
    out.write_text(doc, encoding="utf-8")
    print(f"generated: {out.resolve()}")
    chrome = next((c for c in CHROME_CANDIDATES if Path(c).exists()), None)
    if chrome:
        pdf = out.with_suffix(".pdf")
        r = subprocess.run([chrome, "--headless", "--disable-gpu", "--no-sandbox",
                            f"--print-to-pdf={pdf}", "--no-pdf-header-footer", f"file://{out}"],
                           capture_output=True)
        if pdf.exists() and r.returncode == 0:
            print(f"[pdf] generated: {pdf.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
