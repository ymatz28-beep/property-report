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
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_LIB_PARENT = _PROJECT_ROOT.parent
for p in [str(_PROJECT_ROOT), str(_LIB_PARENT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from lib.styles.design_tokens import get_css_tokens, get_google_fonts_url

from generate_search_report_common import (
    OSAKA_R_ROWS,
    PropertyRow,
    ReportConfig,
    dedupe_properties,
    global_nav_css,
    global_nav_html,
    site_header_css,
    site_header_html,
    load_sold_urls,
    parse_data_file,
    parse_osaka_r_rows,
    score_row,
)

DATA = Path("data")
OUTPUT = Path("output")
MAX_PER_CITY = 10  # Top N per city

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
            "accent": "var(--accent-purple)",
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


def _generate_attraction(row: PropertyRow) -> str:
    """Generate natural-sounding reason for interest based on score breakdown."""
    b = row.score_breakdown
    points = []
    if b.get("station", 0) >= 15:
        points.append("駅からのアクセスの良さ")
    elif b.get("station", 0) >= 10:
        points.append("立地の利便性")
    if b.get("area", 0) >= 15:
        points.append(f"{row.area_sqm:.0f}㎡のゆとりある広さ")
    if b.get("location", 0) >= 15:
        points.append("周辺環境")
    if b.get("pet", 0) >= 15:
        points.append("ペット飼育可能な点")
    if b.get("budget", 0) >= 20:
        points.append("価格帯")
    if not points:
        points.append("条件に合致する内容")
    return "、".join(points[:2]) + "に魅力を感じ"


def _detect_source_type(row: PropertyRow) -> str:
    """Classify source into message variant type."""
    if "R不動産" in row.source or "カウカモ" in row.source or "ふれんず" in row.source:
        return "direct_email"
    if row.source == "楽待":
        return "investor_portal"
    return "portal_form"  # SUUMO, Yahoo, athome, LIFULL


def _pet_line(row: PropertyRow) -> str | None:
    """Generate pet confirmation line based on status."""
    if row.pet_status == "可" or row.pet_status == "相談可":
        return f"チワワ（3kg）を飼っております。ペット{row.pet_status}と記載がございましたが、念のため問題ございませんでしょうか。"
    if not row.pet_status or row.pet_status.strip() == "":
        return "なお、チワワ（3kg）を飼っております。ペット飼育は可能でしょうか。"
    return None


def _extra_questions(row: PropertyRow) -> list[str]:
    """Build list of extra data questions (excluding pet)."""
    questions = []
    if row.maintenance_fee == 0:
        questions.append("月額の管理費・修繕積立金の金額")
    if not row.built_year:
        questions.append("築年月")
    return questions


_CITY_AREAS = {
    "osaka": "大阪市西区・北区・中央区",
    "fukuoka": "福岡市博多区・中央区",
    "tokyo": "渋谷区・新宿区・目黒区・台東区",
}


def generate_message(row: PropertyRow, city_key: str) -> str:
    """Generate customized inquiry message for a property."""
    city_label = {"osaka": "大阪", "fukuoka": "福岡", "tokyo": "東京"}.get(city_key, "")

    # Clean property name
    name = re.sub(r"[●★☆◎♪]", "", row.name).strip()
    if len(name) > 30:
        name = name[:30]

    source_type = _detect_source_type(row)
    attraction = _generate_attraction(row)
    pet = _pet_line(row)
    extras = _extra_questions(row)

    lines = []

    area = _CITY_AREAS.get(city_key, "")
    common_context = f"{area}を中心に予算5,000万円以内で探しており、リノベーション前の物件を優先しております。"

    if source_type == "portal_form":
        # --- Concise portal form version ---
        lines.append(f"「{name}」（{row.price_text}）について、{attraction}お問い合わせいたします。")
        lines.append(row.url)
        lines.append("")
        lines.append(f"東京と{city_label}の2拠点生活を実施しており、{common_context}")
        lines.append(f"不在時には2ヶ月ほど不在にすることもあり、その間ウィークリー・マンスリーのような短期賃貸として活用することも視野に入れておりますが、そのような利用は可能でしょうか。")
        if pet:
            lines.append("")
            lines.append(pet)
        if extras:
            lines.append("")
            lines.append("あわせて以下もご確認いただけますと幸いです。")
            for q in extras:
                lines.append(f"・{q}")
        lines.append("")
        lines.append("上記の利用が可能であれば、ぜひ内覧をお願いしたく存じます。")
        lines.append("よろしくお願いいたします。")

    elif source_type == "investor_portal":
        # --- Investor portal version (楽待) ---
        lines.append(f"「{name}」について、{attraction}お問い合わせいたします。")
        lines.append(row.url)
        lines.append("")
        lines.append(f"東京と{city_label}の2拠点生活を前提に、{common_context}")
        lines.append(f"不在時には2ヶ月ほど不在にすることもあり、その間ウィークリー・マンスリーのような短期賃貸として活用したいと考えておりますが、こうした利用は可能でしょうか。")
        if pet:
            lines.append("")
            lines.append(pet)
        if extras:
            lines.append("")
            for q in extras:
                lines.append(f"・{q}")
        lines.append("")
        lines.append("上記が可能であれば、ぜひ内覧させていただきたいです。")
        lines.append("よろしくお願いいたします。")

    else:
        # --- Direct email version (R不動産, カウカモ, ふれんず) ---
        lines.append("お世話になります。")
        lines.append(f"貴サイトに掲載されている「{name}」を拝見し、{attraction}ご連絡いたしました。")
        lines.append(row.url)
        lines.append("")
        lines.append(f"東京と{city_label}の2拠点生活を実施しており、{common_context}")
        lines.append(f"居住用として使いつつ、不在時には2ヶ月ほど不在にすることもあり、その間ウィークリー・マンスリーのような短期賃貸として活用することも視野に入れておりますが、そのような利用は可能でしょうか。")
        if pet:
            lines.append("")
            lines.append(pet)
        if extras:
            lines.append("")
            lines.append("あわせて、以下の点もお伺いできればと存じます。")
            for q in extras:
                lines.append(f"・{q}")
        lines.append("")
        lines.append("上記の利用が可能であれば、ぜひ内覧をお願いしたく存じます。")
        lines.append("よろしくお願い申し上げます。")

    return "\n".join(lines)


def build_html(all_data: dict[str, list[tuple[PropertyRow, str]]]) -> str:
    """Build the full HTML page."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = sum(len(v) for v in all_data.values())

    city_colors = {
        "osaka": ("#3b9eff", "59,158,255"),
        "fukuoka": ("#34d399", "52,211,153"),
        "tokyo": ("var(--accent-purple)", "167,139,250"),
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
        <div class="city-section" id="city-{city_key}">
          <h2 class="city-title" style="border-left-color:{accent}">{label}（{len(items)}件）</h2>
        ''')

        for row, msg in items:
            idx += 1
            msg_id = f"msg-{idx}"
            channel = SOURCE_CHANNELS.get(row.source, "問い合わせ")
            source_type = _detect_source_type(row)
            type_labels = {"portal_form": "ポータルフォーム", "investor_portal": "投資家向け", "direct_email": "直接メール"}
            type_label = type_labels.get(source_type, "")

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
                <a href="{html_mod.escape(row.url)}" target="_blank" class="card-name">{html_mod.escape(row.name[:40])}</a>
                <div class="card-meta">{html_mod.escape(info_line)}</div>
                <div class="card-score">{row.total_score}pt — {html_mod.escape(channel)} ({html_mod.escape(type_label)})</div>
              </div>
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
    sh_css = site_header_css()
    sh_html = site_header_html()

    css_tokens = get_css_tokens()
    fonts_url = get_google_fonts_url()

    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>問い合わせメッセージ — Property</title>
  <link href="{fonts_url}" rel="stylesheet">
  <style>
    {sh_css}
    {nav_css}
    {css_tokens}
    * {{ box-sizing:border-box; margin:0; }}
    body {{ font-family:var(--font-body); background:var(--bg); color:var(--text); min-height:100vh; }}
    .wrap {{ max-width:900px; margin:0 auto; padding:24px 16px 80px; }}
    h1 {{ font-size:var(--fs-h1); font-weight:700; margin:24px 0 4px; }}
    .subtitle {{ color:var(--text-muted); font-size:13px; margin-bottom:32px; }}
    .city-section {{ margin-bottom:40px; scroll-margin-top:calc(var(--gnav-height, 52px) + 36px + 44px); }}
    .city-title {{ font-size:var(--fs-h2); font-weight:700; margin-bottom:16px; padding-left:14px; border-left:4px solid; }}
    .card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:20px; margin-bottom:16px; transition:border-color .2s; }}
    .card:hover {{ border-color:var(--card-accent, var(--border)); }}
    .card-header {{ display:flex; align-items:flex-start; gap:12px; margin-bottom:10px; }}
    .card-rank {{ font-size:14px; font-weight:800; color:var(--text-muted); min-width:28px; padding-top:2px; }}
    .card-info {{ flex:1; }}
    .card-name {{ font-size:16px; font-weight:800; line-height:1.3; color:var(--text); text-decoration:none; display:block; transition:color .2s; }}
    .card-name:hover {{ color:var(--card-accent, var(--accent, #6366f1)); }}
    .card-meta {{ font-size:13px; color:var(--text-muted); margin-top:2px; }}
    .card-score {{ font-size:12px; color:var(--text-muted); margin-top:2px; }}
    .card-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }}
    .tag {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:700; }}
    .tag-red {{ background:rgba(248,113,113,.12); color:var(--red); border:1px solid rgba(248,113,113,.25); }}
    .tag-green {{ background:rgba(52,211,153,.12); color:var(--green); border:1px solid rgba(52,211,153,.25); }}
    .tag-yellow {{ background:rgba(250,204,21,.12); color:var(--yellow); border:1px solid rgba(250,204,21,.25); }}
    .tag-muted {{ background:rgba(169,179,198,.08); color:var(--text-muted); border:1px solid rgba(169,179,198,.15); }}
    .msg-container {{ position:relative; }}
    .msg-text {{ background:rgba(0,0,0,.3); border:1px solid rgba(255,255,255,.06); border-radius:10px; padding:16px; font-family:var(--font-body); font-size:13px; line-height:1.8; white-space:pre-wrap; word-wrap:break-word; color:#ddd; max-height:300px; overflow-y:auto; }}
    .copy-btn {{ position:absolute; top:8px; right:8px; padding:6px 16px; border-radius:8px; border:1px solid rgba(255,255,255,.15); background:rgba(255,255,255,.06); color:#fff; font-size:12px; font-weight:700; cursor:pointer; transition:all .2s; }}
    .copy-btn:hover {{ background:rgba(255,255,255,.12); border-color:rgba(255,255,255,.3); }}
    .copy-btn.copied {{ background:rgba(52,211,153,.2); border-color:rgba(52,211,153,.5); color:var(--green); }}
    .nav {{ margin-top:40px; text-align:center; }}
    .nav a {{ display:inline-block; padding:10px 24px; border-radius:999px; border:1px solid var(--border); color:var(--text); margin:4px; font-size:13px; text-decoration:none; }}
    .nav a:hover {{ border-color:var(--accent, #6366f1); background:rgba(99,102,241,.06); }}
    .section-nav {{ position:sticky; top:calc(var(--gnav-height, 52px) + 36px); z-index:var(--z-subnav, 90); background:rgba(10,12,18,.94); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); border-bottom:1px solid rgba(255,255,255,.06); margin:0 -16px; padding:0 16px; }}
    .section-nav-inner {{ display:flex; gap:0; overflow-x:auto; white-space:nowrap; -webkit-overflow-scrolling:touch; scrollbar-width:none; }}
    .section-nav-inner::-webkit-scrollbar {{ display:none; }}
    .nav-tab {{ display:inline-flex; align-items:center; gap:4px; padding:10px 16px; font-size:12px; font-weight:600; color:rgba(255,255,255,.45); text-decoration:none; border-bottom:2px solid transparent; transition:color .2s, border-color .2s; cursor:pointer; }}
    .nav-tab:hover {{ color:rgba(255,255,255,.8); }}
    .nav-tab.active {{ color:#fff; border-bottom-color:var(--accent, #6366f1); }}
    .tab-count {{ font-size:10px; color:rgba(255,255,255,.3); font-family:var(--font-mono); }}
    .nav-tab.active .tab-count {{ color:rgba(255,255,255,.6); }}
    @media(max-width:640px) {{
      .card-header {{ flex-wrap:wrap; }}
      .nav-tab {{ padding:10px 12px; font-size:11px; }}
    }}
  </style>
</head>
<body>
{sh_html}
{nav_html}
<div class="wrap">
  <h1>問い合わせメッセージ</h1>
  <p class="subtitle">生成日: {today} — スコア上位{MAX_PER_CITY}件/都市 — 合計{total}件 — コピーして各サイトのフォームに貼り付け</p>

  <div class="section-nav"><div class="section-nav-inner">
    {"".join(f'<a href="#city-{k}" class="nav-tab">{city_labels[k]} <span class="tab-count">{len(all_data.get(k, []))}</span></a>' for k in ["osaka", "fukuoka", "tokyo"] if all_data.get(k))}
  </div></div>

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
