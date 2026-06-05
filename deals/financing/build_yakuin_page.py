#!/usr/bin/env python3
"""薬院「売る or 貸す」試算ページ（スマホ用Web・PJ 3ページの1つ）。
出力: output/yakuin-sell-or-rent.html（配信時は yakuin.html にリネーム）。"""
from __future__ import annotations
import subprocess
from pathlib import Path
from build_financing_pack import md_to_html

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "deals" / "financing" / "11_薬院_売却vs賃貸_試算.md"
OUT = ROOT / "output" / "yakuin-sell-or-rent.html"

CSS = """
:root{--gold:#c9a84c}
html{scroll-behavior:smooth}
body{font-family:'Hiragino Sans','Noto Sans JP',sans-serif;max-width:840px;margin:0 auto;padding:0 18px 60px;color:#1a1a1a;line-height:1.75;background:#f7f6f2}
h1{font-size:21px;border-bottom:3px solid var(--gold);padding-bottom:7px;margin:14px 0 16px}
h2{font-size:17px;border-left:5px solid var(--gold);padding-left:10px;margin-top:26px}
h3{font-size:14px;margin-top:16px;color:#333}
table{border-collapse:collapse;width:100%;margin:11px 0;font-size:13px;background:#fff}
th,td{border:1px solid #ccc;padding:7px 9px;text-align:left;vertical-align:top}
th{background:#f4efe2}
blockquote{background:#fff8e6;border-left:4px solid var(--gold);margin:11px 0;padding:9px 13px;font-size:13px;color:#5a4a1a}
ul,ol{padding-left:22px}li{margin:3px 0}
hr{border:none;border-top:1px solid #ddd;margin:14px 0}
code{background:#eee;padding:1px 5px;border-radius:4px;font-size:12px}
a{color:#1e5fb4;word-break:break-all}
.pjnav{position:sticky;top:0;z-index:30;display:flex;background:#0f1117;margin:0 -18px 12px}
.pjnav a{flex:1;text-align:center;color:#cdd4e2;text-decoration:none;font-size:12.5px;font-weight:700;padding:11px 4px;border-bottom:3px solid transparent;white-space:nowrap}
.pjnav a.on{color:#ffd86b;border-bottom-color:var(--gold);background:#1a1d27}
@media(max-width:700px){body{padding:0 13px 60px}table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}}
"""

NAV = ('<nav class="pjnav"><a href="simulator.html">🎛 シミュレータ</a>'
       '<a href="yakuin.html" class="on">🏠 薬院 売る/貸す</a>'
       '<a href="financing.html">💰 融資戦略</a></nav>')


def main() -> int:
    body = md_to_html(SRC.read_text(encoding="utf-8"))
    doc = (f'<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
           f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
           f'<title>薬院 売る or 貸す 試算 — プレイスポットしんばしPJ</title>'
           f'<style>{CSS}</style></head><body>{NAV}{body}</body></html>')
    OUT.write_text(doc, encoding="utf-8")
    print(f"generated: {OUT.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
