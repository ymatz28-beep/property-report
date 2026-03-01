#!/usr/bin/env python3
"""
物件問い合わせメッセージ自動生成スクリプト

レポートパイプラインのスコア上位物件に対して、
物件ごとにカスタマイズされた問い合わせ文面をHTML形式で出力。
コピーボタン付きで即座にペースト可能。

出力: output/inquiry-messages.html
"""

import html as html_mod
import re
from datetime import datetime
from pathlib import Path

from generate_search_report_common import (
    OSAKA_R_ROWS,
    PropertyRow,
    ReportConfig,
    dedupe_properties,
    global_nav_css,
    global_nav_html,
    load_sold_urls,
    parse_data_file,
    parse_osaka_r_rows,
    score_row,
)

DATA = Path("data")
OUTPUT = Path("output")
MAX_PER_CITY = 20  # Top N per city

# OC keywords (copied from report pipeline)
_OC_KW = [
    "オーナーチェンジ", "賃貸中", "利回り", "投資顧問", "投資物件", "家賃",
    "月額賃料", "年間収入", "年間賃料", "表面利回", "想定利回", "収益",
    "入居者付", "入居中", "賃借人", "テナント付", "現行賃料", "満室",
]

# Source → inquiry channel hint
SOURCE_CHANNELS = {
    "SUUMO": "SUUMO問い合わせフォーム",
    "Yahoo不動産": "Yahoo不動産問い合わせフォーム",
    "athome": "athome問い合わせフォーム",
    "楽待": "楽待問い合わせフォーム",
    "カウカモ": "カウカモ問い合わせフォーム",
    "LIFULL": "LIFULL HOME'S問い合わせフォーム",
    "ふれんず": "ふれんず問い合わせフォーム / 直接連絡",
    "大阪R不動産": "メール問い合わせ",
    "東京R不動産": "メール問い合わせ",
    "福岡R不動産": "メール問い合わせ",
}


def load_city_properties(city_key: str) -> list[PropertyRow]:
    """Load and score properties for a city (same pipeline as reports)."""
    configs = {
        "osaka": {
            "data_path": DATA / "suumo_osaka_raw.txt",
            "extra": [DATA / "multi_site_osaka_raw.txt", DATA / "restate_osaka_raw.txt"],
            "include_osaka_r": True,
            "label": "大阪",
            "accent": "#3b9eff",
            "accent_rgb": "59,158,255",
        },
        "fukuoka": {
            "data_path": DATA / "suumo_fukuoka_raw.txt",
            "extra": [DATA / "multi_site_fukuoka_raw.txt", DATA / "ftakken_fukuoka_raw.txt", DATA / "restate_fukuoka_raw.txt"],
            "include_osaka_r": False,
            "label": "福岡",
            "accent": "#34d399",
            "accent_rgb": "52,211,153",
        },
        "tokyo": {
            "data_path": DATA / "multi_site_tokyo_raw.txt",
            "extra": [DATA / "restate_tokyo_raw.txt", DATA / "cowcamo_tokyo_raw.txt", DATA / "suumo_tokyo_raw.txt"],
            "include_osaka_r": False,
            "label": "東京",
            "accent": "#a78bfa",
            "accent_rgb": "167,139,250",
        },
    }
    c = configs[city_key]
    config = ReportConfig(
        city_key=city_key, city_label=c["label"],
        accent=c["accent"], accent_rgb=c["accent_rgb"],
        data_path=c["data_path"], output_path=Path("/dev/null"),
        hero_conditions=[], search_condition_bullets=[], investor_notes=[],
        include_osaka_r=c["include_osaka_r"],
        extra_data_paths=[p for p in c["extra"] if p.exists()],
    )

    rows = parse_data_file(config.data_path)
    for ep in config.extra_data_paths:
        if ep.exists():
            rows.extend(parse_data_file(ep))
    if config.include_osaka_r:
        rows.extend(parse_osaka_r_rows(OSAKA_R_ROWS))

    deduped, _ = dedupe_properties(rows)
    sold = load_sold_urls()
    deduped = [r for r in deduped if r.url.rstrip("/") + "/" not in sold]
    # OC filter
    deduped = [r for r in deduped if not any(
        kw in f"{r.name} {r.station_text} {r.minpaku_status} {r.location} {r.raw_line}"
        for kw in _OC_KW
    )]
    # Pet NG filter
    deduped = [r for r in deduped if not (
        r.pet_status == "不可"
        or "ペット不可" in f"{r.pet_status} {r.name} {r.raw_line}"
        or "ペット飼育不可" in f"{r.pet_status} {r.name} {r.raw_line}"
    )]
    # Minpaku NG filter
    deduped = [r for r in deduped if not (
        "民泊禁止" in f"{r.minpaku_status} {r.name} {r.raw_line}"
        or "民泊不可" in f"{r.minpaku_status} {r.name} {r.raw_line}"
    )]
    # Score
    for row in deduped:
        score_row(row, config)
    # Quality filter
    deduped = [r for r in deduped if r.total_score >= 30]
    deduped.sort(key=lambda r: (-r.total_score, r.price_man))
    return deduped[:MAX_PER_CITY]


def generate_message(row: PropertyRow, city_key: str) -> str:
    """Generate customized inquiry message for a property."""
    # Determine city context
    city_context = {
        "osaka": "大阪でセカンド拠点となる住居用物件",
        "fukuoka": "福岡で住居用物件",
        "tokyo": "都内で住居用物件",
    }
    city_text = city_context.get(city_key, "住居用物件")

    # Clean property name (remove ● and marketing fluff)
    name = re.sub(r"[●★☆◎♪]", "", row.name).strip()
    if len(name) > 30:
        name = name[:30]

    # Build missing data questions
    questions = []

    if row.maintenance_fee == 0:
        questions.append("月額の管理費・修繕積立金の金額")

    if not row.pet_status or row.pet_status.strip() == "":
        questions.append("ペット飼育の可否（小型犬を飼っております）")
    elif row.pet_status == "相談可":
        questions.append("ペット飼育の条件（小型犬を飼っており、具体的な制限があれば）")

    # Always ask about management rules (indirect minpaku check)
    questions.append("管理規約の写しまたは主要な使用制限事項")

    if not row.built_year:
        questions.append("築年月")

    # Build message
    lines = []
    lines.append("お世話になります。")
    lines.append(f"東京在住の手嶋と申します。")
    lines.append("")

    # Source-specific intro
    if "R不動産" in row.source:
        lines.append(f"貴サイトに掲載されている「{name}」の物件に大変興味を持ちご連絡いたしました。")
    else:
        lines.append(f"掲載されている「{name}」（{row.price_text}）の物件についてお問い合わせいたします。")

    lines.append("")
    lines.append(f"現在、法人名義で{city_text}を探しており、ペットと一緒に住める物件を重視しております。")
    lines.append(f"こちらの物件に興味がありますので、可能であれば内覧をお願いできればと思います。")
    lines.append("")

    if questions:
        lines.append("また、検討にあたり以下の点を確認させていただけると幸いです。")
        lines.append("")
        for i, q in enumerate(questions, 1):
            lines.append(f"  {i}. {q}")
        lines.append("")

    lines.append("ご多忙のところ恐れ入りますが、ご回答いただけますと助かります。")
    lines.append("どうぞよろしくお願いいたします。")
    lines.append("")
    lines.append("手嶋 優真")

    return "\n".join(lines)


def build_html(all_data: dict[str, list[tuple[PropertyRow, str]]]) -> str:
    """Build the full HTML page."""
    today = datetime.now().strftime("%Y-%m-%d")
    total = sum(len(v) for v in all_data.values())

    city_colors = {
        "osaka": ("#3b9eff", "59,158,255"),
        "fukuoka": ("#34d399", "52,211,153"),
        "tokyo": ("#a78bfa", "167,139,250"),
    }
    city_labels = {"osaka": "大阪", "fukuoka": "福岡", "tokyo": "東京"}

    cards_html = []
    idx = 0
    for city_key in ["osaka", "fukuoka", "tokyo"]:
        items = all_data.get(city_key, [])
        if not items:
            continue
        accent, accent_rgb = city_colors[city_key]
        label = city_labels[city_key]

        cards_html.append(f'''
        <div class="city-section">
          <h2 class="city-title" style="border-left-color:{accent}">{label}（{len(items)}件）</h2>
        ''')

        for row, msg in items:
            idx += 1
            msg_id = f"msg-{idx}"
            channel = SOURCE_CHANNELS.get(row.source, "問い合わせ")

            # Missing data tags
            tags = []
            if row.maintenance_fee == 0:
                tags.append('<span class="tag tag-red">管理費不明</span>')
            else:
                tags.append(f'<span class="tag tag-green">管理費 {row.maintenance_fee:,}円</span>')
            if not row.pet_status or row.pet_status.strip() == "":
                tags.append('<span class="tag tag-red">ペット不明</span>')
            elif row.pet_status == "相談可":
                tags.append('<span class="tag tag-yellow">ペット相談可</span>')
            elif row.pet_status == "可":
                tags.append('<span class="tag tag-green">ペット可</span>')
            tags.append(f'<span class="tag tag-muted">{html_mod.escape(row.source)}</span>')

            # Property info line
            area = f"{row.area_sqm:.0f}㎡" if row.area_sqm else "面積不明"
            built = f"{row.built_year}年築" if row.built_year else "築年不明"
            walk = f"徒歩{row.walk_min}分" if row.walk_min else ""
            info_parts = [row.price_text, area, built, row.layout or ""]
            if walk:
                info_parts.append(walk)
            info_line = " / ".join(p for p in info_parts if p)

            msg_escaped = html_mod.escape(msg)

            cards_html.append(f'''
          <div class="card" style="--card-accent:{accent}">
            <div class="card-header">
              <div class="card-rank">#{idx}</div>
              <div class="card-info">
                <div class="card-name">{html_mod.escape(row.name[:40])}</div>
                <div class="card-meta">{html_mod.escape(info_line)}</div>
                <div class="card-score">{row.total_score}pt — {html_mod.escape(channel)}</div>
              </div>
              <a href="{html_mod.escape(row.url)}" target="_blank" class="card-link">物件ページ →</a>
            </div>
            <div class="card-tags">{"".join(tags)}</div>
            <div class="msg-container">
              <pre class="msg-text" id="{msg_id}">{msg_escaped}</pre>
              <button class="copy-btn" onclick="copyMsg('{msg_id}', this)" data-accent="{accent}">
                コピー
              </button>
            </div>
          </div>
            ''')

        cards_html.append('</div>')

    nav_css = global_nav_css()
    nav_html = global_nav_html("inquiry-messages.html")

    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>問い合わせメッセージ — iUMA Property</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Noto+Sans+JP:wght@400;700;900&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
  <style>
    {nav_css}
    :root {{ --bg:#0b0f16; --card:rgba(255,255,255,0.04); --line:rgba(255,255,255,0.10); --text:#edf3ff; --muted:#a9b3c6; --green:#34d399; --red:#f87171; --yellow:#facc15; }}
    * {{ box-sizing:border-box; margin:0; }}
    body {{ font-family:'Inter','Noto Sans JP',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }}
    .wrap {{ max-width:900px; margin:0 auto; padding:24px 16px 80px; }}
    h1 {{ font-size:28px; font-weight:900; margin:24px 0 4px; }}
    .subtitle {{ color:var(--muted); font-size:13px; margin-bottom:32px; }}
    .city-section {{ margin-bottom:40px; }}
    .city-title {{ font-size:20px; font-weight:800; margin-bottom:16px; padding-left:14px; border-left:4px solid; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px; margin-bottom:16px; transition:border-color .2s; }}
    .card:hover {{ border-color:var(--card-accent, var(--line)); }}
    .card-header {{ display:flex; align-items:flex-start; gap:12px; margin-bottom:10px; }}
    .card-rank {{ font-size:14px; font-weight:800; color:var(--muted); min-width:28px; padding-top:2px; }}
    .card-info {{ flex:1; }}
    .card-name {{ font-size:16px; font-weight:800; line-height:1.3; }}
    .card-meta {{ font-size:13px; color:var(--muted); margin-top:2px; }}
    .card-score {{ font-size:12px; color:var(--muted); margin-top:2px; }}
    .card-link {{ font-size:12px; color:var(--card-accent, #3b9eff); text-decoration:none; white-space:nowrap; padding-top:2px; }}
    .card-link:hover {{ text-decoration:underline; }}
    .card-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }}
    .tag {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:700; }}
    .tag-red {{ background:rgba(248,113,113,.12); color:var(--red); border:1px solid rgba(248,113,113,.25); }}
    .tag-green {{ background:rgba(52,211,153,.12); color:var(--green); border:1px solid rgba(52,211,153,.25); }}
    .tag-yellow {{ background:rgba(250,204,21,.12); color:var(--yellow); border:1px solid rgba(250,204,21,.25); }}
    .tag-muted {{ background:rgba(169,179,198,.08); color:var(--muted); border:1px solid rgba(169,179,198,.15); }}
    .msg-container {{ position:relative; }}
    .msg-text {{ background:rgba(0,0,0,.3); border:1px solid rgba(255,255,255,.06); border-radius:10px; padding:16px; font-family:'Noto Sans JP',sans-serif; font-size:13px; line-height:1.8; white-space:pre-wrap; word-wrap:break-word; color:#ddd; max-height:300px; overflow-y:auto; }}
    .copy-btn {{ position:absolute; top:8px; right:8px; padding:6px 16px; border-radius:8px; border:1px solid rgba(255,255,255,.15); background:rgba(255,255,255,.06); color:#fff; font-size:12px; font-weight:700; cursor:pointer; transition:all .2s; }}
    .copy-btn:hover {{ background:rgba(255,255,255,.12); border-color:rgba(255,255,255,.3); }}
    .copy-btn.copied {{ background:rgba(52,211,153,.2); border-color:rgba(52,211,153,.5); color:var(--green); }}
    .summary {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-bottom:32px; }}
    .summary-card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; text-align:center; }}
    .summary-card .num {{ font-size:28px; font-weight:900; }}
    .summary-card .lbl {{ font-size:12px; color:var(--muted); margin-top:4px; }}
    .nav {{ margin-top:40px; text-align:center; }}
    .nav a {{ display:inline-block; padding:10px 24px; border-radius:999px; border:1px solid var(--line); color:var(--text); margin:4px; font-size:13px; text-decoration:none; }}
    .nav a:hover {{ border-color:#3b9eff; background:rgba(59,158,255,.06); }}
    @media(max-width:640px) {{
      .card-header {{ flex-wrap:wrap; }}
      .card-link {{ width:100%; text-align:right; }}
    }}
  </style>
</head>
<body>
{nav_html}
<div class="wrap">
  <h1>問い合わせメッセージ</h1>
  <p class="subtitle">生成日: {today} — スコア上位{MAX_PER_CITY}件/都市 — 合計{total}件 — コピーして各サイトのフォームに貼り付け</p>

  <div class="summary">
    {"".join(f'<div class="summary-card"><div class="num" style="color:{city_colors[k][0]}">{len(all_data.get(k, []))}</div><div class="lbl">{city_labels[k]}</div></div>' for k in ["osaka", "fukuoka", "tokyo"])}
    <div class="summary-card"><div class="num">{total}</div><div class="lbl">合計</div></div>
  </div>

  {"".join(cards_html)}

  <div class="nav">
    <a href="index.html">← Hub</a>
    <a href="minpaku-osaka.html">大阪レポート</a>
    <a href="minpaku-fukuoka.html">福岡レポート</a>
    <a href="minpaku-tokyo.html">東京レポート</a>
  </div>
</div>

<script>
function copyMsg(id, btn) {{
  const el = document.getElementById(id);
  const text = el.textContent;
  navigator.clipboard.writeText(text).then(() => {{
    btn.textContent = 'コピー済み ✓';
    btn.classList.add('copied');
    setTimeout(() => {{
      btn.textContent = 'コピー';
      btn.classList.remove('copied');
    }}, 2000);
  }});
}}
</script>
</body>
</html>'''


def main():
    print(f"問い合わせメッセージ生成 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    all_data: dict[str, list[tuple[PropertyRow, str]]] = {}

    for city_key in ["osaka", "fukuoka", "tokyo"]:
        print(f"\n  {city_key}...")
        props = load_city_properties(city_key)
        messages = []
        for row in props:
            msg = generate_message(row, city_key)
            messages.append((row, msg))
        all_data[city_key] = messages
        print(f"    {len(messages)}件のメッセージ生成")

    OUTPUT.mkdir(exist_ok=True)
    out_path = OUTPUT / "inquiry-messages.html"
    html_content = build_html(all_data)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"\n  出力: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
