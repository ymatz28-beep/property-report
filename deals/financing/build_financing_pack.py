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
FILES = ["00_playbook.md", "01_jfc_旅館業_事業計画書.md",
         "14_公庫_申請パック.md",
         "10_生活衛生同業組合_公庫低利の鍵.md",
         "02_shiga_賃貸_打診パッケージ.md",
         "08_旅館業_許可申請の詳細.md", "13_旅館業許可_申請パック.md",
         "03_リノベ相見積_インダストリアル.md", "09_インダストリアル_見積依頼書.md",
         "04_運営代行_候補と相場.md",
         "05_補助金_使えるもの全部.md", "12_福岡市補助金_受入環境_申請パック.md",
         "06_スケジュール_発注タイミング.md",
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
        # fenced code block (``` ... ```) → コピーボタン付き <pre>
        if ln.lstrip().startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1  # 閉じ ``` をスキップ
            code = html.escape("\n".join(buf))
            out.append('<div class="codewrap"><button class="copybtn" type="button">📋 コピー</button>'
                       f'<pre class="code">{code}</pre></div>')
            continue
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


# 目次チップ用の短いラベル（ファイル名→表示名）。FILESの順にidを s0.. と振る。
NAV_LABELS = {
    "00_playbook.md": "融資プレイブック",
    "01_jfc_旅館業_事業計画書.md": "公庫(旅館業)",
    "14_公庫_申請パック.md": "公庫(申請パック)",
    "10_生活衛生同業組合_公庫低利の鍵.md": "組合(公庫低利)",
    "02_shiga_賃貸_打診パッケージ.md": "滋賀(賃貸)",
    "08_旅館業_許可申請の詳細.md": "旅館業許可",
    "13_旅館業許可_申請パック.md": "旅館業許可(申請パック)",
    "03_リノベ相見積_インダストリアル.md": "リノベ相見積",
    "09_インダストリアル_見積依頼書.md": "見積依頼書",
    "04_運営代行_候補と相場.md": "運営代行",
    "05_補助金_使えるもの全部.md": "補助金まとめ",
    "12_福岡市補助金_受入環境_申請パック.md": "福岡市補助金(申請パック)",
    "06_スケジュール_発注タイミング.md": "発注カレンダー",
    "07_相談先メール下書き.md": "相談メール",
}


def build_flowchart(idmap: dict) -> str:
    """全体の流れを1枚のフローチャートに。各ボックスは該当章へジャンプ。"""
    g = idmap.get  # filename -> "sN"
    fin = g("00_playbook.md", "")
    jfc = g("01_jfc_旅館業_事業計画書.md", "")
    perm = g("08_旅館業_許可申請の詳細.md", "")
    sub = g("05_補助金_使えるもの全部.md", "")
    sch = g("06_スケジュール_発注タイミング.md", "")
    mail = g("07_相談先メール下書き.md", "")
    return f"""
<section class="flowwrap" id="flow">
  <h1>全体の流れ（上から着手順。各箱から章へ飛べる）</h1>
  <div class="flow">
    <a class="fbox first" href="#{mail}"><span class="badge">▶ いまここから</span><b>1. 相談メール3本を送る ＋ 事業者ID申請</b><small>福岡市 観光部／保健所／商工会議所へ。並行で事業者ID(gBizID)申請。ここが全部の入口</small></a>
    <div class="farrow">▼ 相談で段取りが見えたら</div>
    <a class="fbox start" href="#{perm}"><b>2. 旅館業（簡易宿所）許可を取る</b><small>すべての低金利と補助金を同時に開く"スイッチ"。福岡市は手数料22,000円・フロントICT代替OK・49㎡は用途変更不要。賃貸のままだと両方とも全滅</small></a>
    <div class="farrow">▼ この1手が、下の2つを同時に開く</div>
    <div class="frow">
      <a class="fbox" href="#{fin}"><b>3A. 融資（低金利の梯子）</b><small>公庫 振興事業貸付＝組合加入で設備20年→DSCR成立。次に商工中金。法人の受け皿はセゾン直接。※相見積は打診と並行で取る</small></a>
      <a class="fbox" href="#{sub}"><b>3B. 補助金・税優遇</b><small>福岡市 受入環境補助(半額・上限40万)／省力化補助／経営強化税制(即時償却・10%控除)</small></a>
    </div>
    <div class="farrow">▼ どちらも「決定の紙が出る前に発注したら対象外」</div>
    <a class="fbox gate" href="#{sch}"><b>4. ★発注ゲート</b><small>計画認定・交付決定を確認してから、鍵・端末・家具・空調を発注。リノベ本体は対象外なので先行してよい</small></a>
    <div class="farrow">▼</div>
    <a class="fbox" href="#{sch}"><b>5. 工事 → 旅館業 許可取得 → 開業（OTA掲載）</b></a>
    <div class="farrow">▼ ゴール</div>
    <a class="fbox end" href="#{sch}"><b>6. 実績報告で補助金が後払い入金 ＋ 確定申告で節税</b><small>立て替えた分を、補助金と即時償却/税額控除で回収する</small></a>
  </div>
</section>"""


def main() -> int:
    sections, nav, idmap = [], [], {}
    idx = 0
    for f in FILES:
        p = FIN_DIR / f
        if not p.exists():
            continue
        sid = f"s{idx}"; idmap[f] = sid; idx += 1
        label = NAV_LABELS.get(f, f)
        nav.append(f'<a class="chip" href="#{sid}" data-target="{sid}">{html.escape(label)}</a>')
        sections.append(f'<section id="{sid}" class="doc">\n{md_to_html(p.read_text(encoding="utf-8"))}\n</section>')
    flow = build_flowchart(idmap)
    nav_html = '<nav class="toc" id="toc">' + "".join(nav) + "</nav>"
    body = flow + "\n" + '\n<hr class="sec">\n'.join(sections)
    doc = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>融資・補助金パッケージ — プレイスポットしんばし</title>
<style>
:root{{--gold:#c9a84c;--ink:#1a1a1a}}
html{{scroll-behavior:smooth}}
body{{font-family:'Hiragino Sans','Noto Sans JP',sans-serif;max-width:840px;margin:0 auto;padding:0 20px 60px;color:var(--ink);line-height:1.7;background:#fff}}
h1{{font-size:22px;border-bottom:3px solid var(--gold);padding-bottom:6px;margin-top:8px}}
h2{{font-size:18px;border-left:5px solid var(--gold);padding-left:10px;margin-top:28px}}
h3{{font-size:15px;margin-top:20px;color:#333}}
h4{{font-size:14px;margin-top:14px;color:#555}}
section.doc{{scroll-margin-top:160px}}
.flowwrap{{scroll-margin-top:160px}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}}
th,td{{border:1px solid #ccc;padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:#f4efe2}}
blockquote{{background:#fff8e6;border-left:4px solid var(--gold);margin:12px 0;padding:8px 14px;font-size:13px;color:#5a4a1a}}
code{{background:#f0f0f0;padding:1px 5px;border-radius:4px;font-size:12px}}
ul,ol{{padding-left:22px}}
li{{margin:3px 0}}
hr{{border:none;border-top:1px solid #ddd;margin:16px 0}}
hr.sec{{border-top:2px dashed var(--gold);margin:36px 0}}
a{{color:#1e5fb4;word-break:break-all}}
/* PJ 3ページ切替タブ */
.pjnav{{position:sticky;top:0;z-index:30;display:flex;background:#0f1117;margin:0 -20px}}
.pjnav a{{flex:1;text-align:center;color:#cdd4e2;text-decoration:none;font-size:12.5px;font-weight:700;padding:11px 4px;border-bottom:3px solid transparent;white-space:nowrap}}
.pjnav a.on{{color:#ffd86b;border-bottom-color:#c9a84c;background:#1a1d27}}
/* sticky header: toolbar + toc chips */
.sticky{{position:sticky;top:42px;z-index:20;background:#1a1d27;margin:0 -20px 18px;padding:10px 20px}}
.toolbar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.toolbar button,.toolbar a.btn{{background:var(--gold);color:#1a1207;font-weight:700;border:none;padding:9px 15px;border-radius:9px;font-size:14px;text-decoration:none;cursor:pointer}}
.toolbar a.alt{{background:#242836;color:#e4e4e7}}
.toc{{display:flex;gap:7px;overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:9px;padding-bottom:3px}}
.toc .chip{{flex:0 0 auto;background:#242836;color:#cfd2da;border:1px solid #3a3f4f;padding:6px 11px;border-radius:999px;font-size:12.5px;font-weight:600;text-decoration:none;white-space:nowrap}}
.toc .chip.active{{background:var(--gold);color:#1a1207;border-color:var(--gold)}}
/* flowchart */
.flow{{display:flex;flex-direction:column;align-items:center;gap:0;margin:14px 0 6px}}
.fbox{{display:block;width:100%;max-width:640px;background:#fffdf7;border:2px solid var(--gold);border-radius:12px;padding:11px 15px;text-decoration:none;color:var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.fbox b{{display:block;font-size:14.5px}}
.fbox small{{display:block;color:#5a4a1a;font-size:11.5px;margin-top:3px;line-height:1.5}}
.fbox.start{{background:#fff4cf;border-color:#b8902a}}
.fbox.gate{{background:#ffe9e3;border-color:#e0623a}}
.fbox.end{{background:#e7f6ea;border-color:#2faa55}}
.fbox.first{{background:#1a1d27;border-color:#1a1d27;position:relative}}
.fbox.first b{{color:#ffd86b}} .fbox.first small{{color:#cfd2da}}
.fbox.first .badge{{display:inline-block;background:#ffd86b;color:#1a1207;font-weight:800;font-size:11px;padding:2px 9px;border-radius:999px;margin-bottom:5px}}
.frow{{display:flex;gap:12px;width:100%;max-width:640px}}
.frow .fbox{{flex:1}}
.farrow{{color:#b8902a;font-weight:700;font-size:12.5px;padding:6px 0;text-align:center}}
/* code blocks (コピー可) */
.codewrap{{position:relative;margin:12px 0}}
pre.code{{background:#0f1117;color:#e6e8ee;padding:30px 14px 14px;border-radius:10px;overflow-x:auto;font-size:12.5px;line-height:1.65;white-space:pre-wrap;word-break:break-word;font-family:'SFMono-Regular',Consolas,Menlo,monospace}}
.copybtn{{position:absolute;top:7px;right:7px;background:var(--gold);color:#1a1207;border:none;padding:5px 11px;border-radius:7px;font-size:12px;font-weight:700;cursor:pointer}}
.copybtn.done{{background:#2faa55;color:#fff}}
@media print{{.copybtn{{display:none}}}}
/* back to top */
#totop{{position:fixed;right:16px;bottom:16px;z-index:30;background:var(--gold);color:#1a1207;border:none;width:46px;height:46px;border-radius:50%;font-size:20px;font-weight:700;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.25);opacity:0;pointer-events:none;transition:opacity .2s}}
#totop.show{{opacity:.95;pointer-events:auto}}
@media print{{
  .sticky,#totop,.copybtn{{display:none}}
  body{{padding:0;font-size:10.5pt}}
  @page{{margin:14mm 12mm}}
  .fbox{{box-shadow:none}}a{{color:#1a1a1a}}
  .flowwrap{{page-break-after:always}}
  .doc{{break-before:page;page-break-before:always}}
  h1,h2,h3{{break-after:avoid;page-break-after:avoid;break-inside:avoid;page-break-inside:avoid}}
  table{{break-inside:auto;page-break-inside:auto}}
  tr,td,th{{break-inside:avoid;page-break-inside:avoid}}
  thead{{display:table-header-group}}
  blockquote,pre,.codewrap,li,img{{break-inside:avoid;page-break-inside:avoid}}
  p{{orphans:3;widows:3}}
}}
@media(max-width:700px){{body{{padding:0 14px 60px}}.sticky{{margin:0 -14px 16px;padding:9px 14px}}h1{{font-size:19px}}h2{{font-size:16px}}
  .frow{{flex-direction:column}}
  table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}}
  table thead,table tbody{{display:table;width:100%;min-width:520px}}}}
</style></head><body>
<nav class="pjnav"><a href="simulator.html">🎛 シミュレータ</a><a href="financing.html" class="on">💰 融資戦略</a><a href="yakuin.html">🏠 薬院 売る/貸す</a></nav>
<div class="sticky">
  <div class="toolbar">
    <button onclick="window.print()">🖨 印刷 / PDF</button>
    <a class="btn alt" href="{PDF_NAME}" download>⬇ PDF</a>
    <a class="btn alt" href="#flow">🗺 全体図</a>
  </div>
  {nav_html}
</div>
{body}
<hr class="sec">
<p style="font-size:11px;color:var(--text-secondary)">生成: property-analyzer/deals/financing/。数字の[要記入]はYumaの実数で更新する。各金融機関の融資条件は要直接照会。</p>
<button id="totop" aria-label="先頭へ" type="button">↑</button>
<script>
(function(){{
  var tt0=document.getElementById('totop');
  function toTop(){{ try{{ if('scrollBehavior' in document.documentElement.style){{ window.scrollTo({{top:0,behavior:'smooth'}}); }} else {{ window.scrollTo(0,0); }} }} catch(e){{ window.scrollTo(0,0); }} }}
  tt0.addEventListener('click', toTop);
  var chips=[].slice.call(document.querySelectorAll('.toc .chip'));
  var map={{}}; chips.forEach(function(c){{map[c.dataset.target]=c;}});
  var secs=[].slice.call(document.querySelectorAll('section[id]'));
  var io=new IntersectionObserver(function(es){{
    es.forEach(function(e){{
      if(e.isIntersecting){{
        chips.forEach(function(c){{c.classList.remove('active');}});
        var c=map[e.target.id]; if(c){{c.classList.add('active');
          c.scrollIntoView({{inline:'center',block:'nearest'}});}}
      }}
    }});
  }},{{rootMargin:'-120px 0px -65% 0px',threshold:0}});
  secs.forEach(function(s){{io.observe(s);}});
  var tt=document.getElementById('totop');
  addEventListener('scroll',function(){{tt.classList.toggle('show',scrollY>500);}},{{passive:true}});
  // copy buttons on code blocks
  function fallbackCopy(t,ok){{var ta=document.createElement('textarea');ta.value=t;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.focus();ta.select();try{{document.execCommand('copy');ok();}}catch(e){{}}document.body.removeChild(ta);}}
  [].slice.call(document.querySelectorAll('.copybtn')).forEach(function(b){{
    b.addEventListener('click',function(){{
      var pre=b.parentNode.querySelector('pre.code'); var t=pre.innerText;
      function ok(){{var o=b.textContent;b.textContent='✓ コピー済';b.classList.add('done');setTimeout(function(){{b.textContent=o;b.classList.remove('done');}},1500);}}
      if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(t).then(ok,function(){{fallbackCopy(t,ok);}});}}else{{fallbackCopy(t,ok);}}
    }});
  }});
}})();
</script>
</body></html>"""
    OUT.write_text(doc, encoding="utf-8")
    print(f"generated: {OUT.resolve()}")
    make_pdf()
    subprocess.run(["open", str(OUT.resolve())])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
