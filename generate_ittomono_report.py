#!/usr/bin/env python3
"""
一棟もの物件レポートジェネレーター
全都市の一棟マンション・アパートを1ページに統合表示する。

区分マンションとは異なるスコアリングシステムを使用:
- 価格帯 (1.5億〜2億のスイートスポット)
- 立地 (既存の都市別立地スコアを流用)
- 駅距離
- 建物構造 (RC > S > 木造)
- 総戸数 (多いほど安定収入)
- 表面利回り
- 築年数 (新耐震基準)
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Make shared lib importable
_THIS_DIR = Path(__file__).resolve().parent
_LIB_ROOT = _THIS_DIR.parent
for p in [str(_THIS_DIR), str(_LIB_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generate_search_report_common import (
    classify_location_osaka,
    classify_location_fukuoka,
    classify_location_tokyo,
    site_header_css,
    site_header_html,
    global_nav_css,
    global_nav_html,
    load_first_seen,
    _format_first_seen,
    grade_tier,
    _NAV_PAGES,
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"


@dataclass
class IttomonoRow:
    source: str
    name: str
    price_text: str
    location: str
    area_text: str
    built_text: str
    station_text: str
    structure: str
    units: str
    yield_text: str
    layout_detail: str
    url: str
    city_key: str = ""
    price_man: int = 0
    area_sqm: float | None = None
    built_year: int | None = None
    walk_min: int | None = None
    units_count: int = 0
    yield_pct: float = 0.0
    total_score: int = 0
    tier_label: str = ""
    tier_class: str = ""
    tier_color: str = ""
    score_breakdown: dict[str, int] = field(default_factory=dict)
    avg_sqm_per_unit: float | None = None
    detail_comment: str = ""
    bucket_label: str = "Other"


def parse_data_file(data_path: Path, city_key: str) -> list[IttomonoRow]:
    """Parse 14-column pipe-delimited data file for 一棟もの."""
    rows = []
    if not data_path.exists():
        return rows

    for line in data_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 14:
            continue

        row = IttomonoRow(
            source=parts[0],
            name=parts[1],
            price_text=parts[2],
            location=parts[3],
            area_text=parts[4],
            built_text=parts[5],
            station_text=parts[6],
            structure=parts[7],
            units=parts[8],
            yield_text=parts[9],
            layout_detail=parts[10],
            url=parts[13],
            city_key=city_key,
        )
        _hydrate(row)
        rows.append(row)
    return rows


def _hydrate(row: IttomonoRow) -> None:
    """Parse text fields into structured values."""
    # Price
    text = row.price_text.replace(",", "")
    m_oku = re.search(r"(\d+(?:\.\d+)?)億", text)
    m_man = re.search(r"(\d+(?:\.\d+)?)万", text)
    total = 0
    if m_oku:
        total += int(float(m_oku.group(1)) * 10000)
    if m_man:
        total += int(float(m_man.group(1)))
    row.price_man = total

    # Area
    m = re.search(r"(\d+(?:\.\d+)?)\s*m", row.area_text, re.IGNORECASE)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)", row.area_text)
    row.area_sqm = float(m.group(1)) if m else None

    # Built year
    y = re.search(r"(\d{4})年", row.built_text)
    row.built_year = int(y.group(1)) if y else None

    # Walk minutes
    if "バス" not in row.station_text:
        m = re.search(r"徒歩\s*(\d+)\s*分", row.station_text)
        row.walk_min = int(m.group(1)) if m else None

    # Units count
    m = re.search(r"(\d+)", row.units)
    row.units_count = int(m.group(1)) if m else 0

    # Yield
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", row.yield_text)
    row.yield_pct = float(m.group(1)) if m else 0.0

    # Average sqm per unit
    if row.area_sqm and row.units_count and row.units_count > 0:
        row.avg_sqm_per_unit = round(row.area_sqm / row.units_count, 1)


# ============================================================
# Scoring system for 一棟もの
# ============================================================

def price_score(price_man: int) -> int:
    """Price scoring for 1.5億〜2億 range. Sweet spot = 1.6〜1.8億."""
    if 16000 <= price_man <= 18000:
        return 15  # Sweet spot
    if 15000 <= price_man <= 20000:
        return 10  # Within range
    if 14000 <= price_man < 15000:
        return 5  # Slightly below
    if 20000 < price_man <= 22000:
        return 5  # Slightly above
    return 0


def structure_score(structure: str) -> int:
    """Building structure scoring. RC/SRC > S造 > 木造."""
    if not structure:
        return 0
    if "RC" in structure or "SRC" in structure or "鉄筋コンクリート" in structure:
        return 15
    if "S造" in structure or "鉄骨" in structure:
        return 10
    if "木造" in structure:
        return 5
    return 0


def units_score(count: int) -> int:
    """Total units scoring. More units = more stable income."""
    if count >= 20:
        return 15
    if count >= 15:
        return 12
    if count >= 10:
        return 10
    if count >= 6:
        return 7
    if count >= 3:
        return 5
    return 0


def yield_score(pct: float) -> int:
    """Yield scoring. Higher is better but beware too-good-to-be-true."""
    if pct <= 0:
        return 0  # No data
    if pct >= 10:
        return 5  # Suspicious — may need major repairs
    if pct >= 7:
        return 15  # Excellent
    if pct >= 5:
        return 10  # Good
    if pct >= 4:
        return 7  # Acceptable
    return 3  # Low yield


def earthquake_score_ittomono(year: int | None) -> int:
    """New earthquake code compliance (1981+)."""
    if year is None:
        return 0
    if year >= 2000:
        return 15  # Modern standards
    if year >= 1981:
        return 10  # New earthquake code
    return 0  # Old earthquake code


def station_score_ittomono(walk_min: int | None) -> int:
    """Station proximity for 一棟もの (rental demand perspective)."""
    if walk_min is None:
        return 0
    if walk_min <= 5:
        return 15
    if walk_min <= 10:
        return 10
    if walk_min <= 15:
        return 5
    return 0


def location_score(row: IttomonoRow) -> tuple[str, int]:
    """Location scoring using existing city classifiers."""
    text = f"{row.location} {row.station_text} {row.name}"
    if row.city_key == "osaka":
        return classify_location_osaka(text)
    elif row.city_key == "tokyo":
        return classify_location_tokyo(text)
    elif row.city_key == "fukuoka":
        return classify_location_fukuoka(text)
    return "Other", 0


def score_row(row: IttomonoRow) -> None:
    """Calculate total score for a 一棟もの property."""
    bucket, loc_sc = location_score(row)
    row.bucket_label = bucket
    breakdown = {
        "price": price_score(row.price_man),
        "structure": structure_score(row.structure),
        "units": units_score(row.units_count),
        "yield": yield_score(row.yield_pct),
        "earthquake": earthquake_score_ittomono(row.built_year),
        "station": station_score_ittomono(row.walk_min),
        "location": loc_sc,
    }
    row.score_breakdown = breakdown
    row.total_score = sum(breakdown.values())
    row.tier_label, row.tier_class, row.tier_color = grade_tier(row.total_score)
    row.detail_comment = _build_comment(row)


def _build_comment(row: IttomonoRow) -> str:
    """Build detail comment for a 一棟もの property."""
    strengths = []
    cautions = []
    b = row.score_breakdown

    if b.get("price", 0) >= 15:
        strengths.append("価格スイートスポット")
    elif b.get("price", 0) >= 10:
        strengths.append("予算範囲内")
    if b.get("structure", 0) >= 15:
        strengths.append("RC/SRC構造")
    elif b.get("structure", 0) >= 10:
        strengths.append("鉄骨造")
    if b.get("units", 0) >= 12:
        strengths.append(f"戸数{row.units_count}戸で安定収入")
    if b.get("yield", 0) >= 15:
        strengths.append(f"利回り{row.yield_pct}%")
    if b.get("earthquake", 0) >= 10:
        strengths.append("新耐震基準")
    if b.get("station", 0) >= 10:
        strengths.append("駅近")
    if b.get("location", 0) >= 15:
        strengths.append("好立地エリア")

    if not row.structure:
        cautions.append("構造データなし")
    elif b.get("structure", 0) <= 5:
        cautions.append("木造（耐用年数注意）")
    if row.units_count == 0:
        cautions.append("戸数データなし")
    if row.yield_pct <= 0:
        cautions.append("利回りデータなし")
    elif b.get("yield", 0) <= 5:
        cautions.append("利回り要精査")
    if b.get("earthquake", 0) == 0 and row.built_year:
        cautions.append("旧耐震基準")
    if row.walk_min is None:
        cautions.append("駅距離不明")
    elif row.walk_min > 10:
        cautions.append("駅やや遠い")

    if not strengths:
        strengths.append("詳細情報で再評価余地")
    msg = " / ".join(strengths[:4])
    if cautions:
        msg += "。注意: " + "、".join(cautions[:3])
    return msg


# ============================================================
# HTML Report Generation
# ============================================================

def _avg_sqm_cell(r: IttomonoRow) -> str:
    """Build the avg ㎡/戸 cell with color coding and layout detail."""
    parts = []
    if r.avg_sqm_per_unit is not None:
        val = r.avg_sqm_per_unit
        if val >= 35:
            color = "#22c55e"  # green — meets requirement
        elif val >= 25:
            color = "#facc15"  # yellow — borderline
        else:
            color = "#f87171"  # red — too small
        parts.append(f'<span style="color:{color};font-weight:600">{val}㎡</span>')
    else:
        parts.append('<span style="color:var(--dim)">-</span>')
    # Show layout_detail if available (e.g. "1K×6戸, 1LDK×6戸")
    if r.layout_detail:
        parts.append(f'<div class="layout-detail">{html.escape(r.layout_detail)}</div>')
    return "".join(parts)


CITY_LABELS = {"osaka": "大阪", "fukuoka": "福岡", "tokyo": "東京"}
CITY_ACCENTS = {"osaka": "#6ee7ff", "fukuoka": "#ff6b6b", "tokyo": "#a78bfa"}


def build_report_html(all_rows: list[IttomonoRow]) -> str:
    """Build the 一棟もの HTML report (single page, all cities)."""
    sorted_rows = sorted(all_rows, key=lambda r: (-r.total_score, r.price_man))
    first_seen = load_first_seen()
    today_iso = dt.date.today().isoformat()
    for r in sorted_rows:
        if r.url and r.url not in first_seen:
            first_seen[r.url] = today_iso

    # Stats
    total = len(sorted_rows)
    by_city = Counter(r.city_key for r in sorted_rows)
    avg_price = round(sum(r.price_man for r in sorted_rows) / total) if total > 0 else 0
    avg_yield = round(sum(r.yield_pct for r in sorted_rows if r.yield_pct > 0) / max(1, sum(1 for r in sorted_rows if r.yield_pct > 0)), 2) if total > 0 else 0

    # Build table rows HTML
    table_html = []
    for idx, r in enumerate(sorted_rows, start=1):
        fs_display = _format_first_seen(r.url, first_seen)
        is_new = fs_display == "NEW"
        new_badge = '<span class="badge-new">NEW</span>' if is_new else f'<span class="fs-date">{fs_display}</span>' if fs_display else ''

        # Score breakdown pills
        b = r.score_breakdown
        pills = []
        for label, key in [("価格", "price"), ("構造", "structure"), ("戸数", "units"),
                           ("利回", "yield"), ("耐震", "earthquake"), ("駅距", "station"), ("立地", "location")]:
            val = b.get(key, 0)
            if val > 0:
                pills.append(f'<span class="sc-pill sc-pos">{label[:2]}+{val}</span>')
            elif val < 0:
                pills.append(f'<span class="sc-pill sc-neg">{label[:2]}{val}</span>')
            else:
                pills.append(f'<span class="sc-pill sc-zero">{label[:2]}0</span>')

        city_label = CITY_LABELS.get(r.city_key, r.city_key)
        city_accent = CITY_ACCENTS.get(r.city_key, "#3b9eff")

        table_html.append(f'''
        <tr class="prop-row" data-city="{r.city_key}" data-score="{r.total_score}">
          <td class="col-rank">{idx}</td>
          <td class="col-name">
            <a href="{html.escape(r.url)}" target="_blank" rel="noopener">{html.escape(r.name)}</a>
            <div class="row-meta">
              <span class="city-tag" style="border-color:{city_accent};color:{city_accent}">{city_label}</span>
              <span class="src-tag">{html.escape(r.source)}</span>
              {new_badge}
            </div>
          </td>
          <td class="col-price">{html.escape(r.price_text)}</td>
          <td class="col-location">{html.escape(r.location)}</td>
          <td class="col-structure">{html.escape(r.structure or '-')}</td>
          <td class="col-units">{html.escape(r.units or '-')}</td>
          <td class="col-avgm2">{_avg_sqm_cell(r)}</td>
          <td class="col-yield">{html.escape(r.yield_text or '-')}</td>
          <td class="col-built">{html.escape(r.built_text or '-')}</td>
          <td class="col-station">{html.escape(r.station_text or '-')}</td>
          <td class="col-score">
            <div class="score-total" style="color:{r.tier_color}">{r.total_score}</div>
            <div class="tier-badge {r.tier_class}">{r.tier_label}</div>
          </td>
          <td class="col-breakdown">
            <div class="breakdown-pills">{" ".join(pills)}</div>
            <div class="comment">{html.escape(r.detail_comment)}</div>
          </td>
        </tr>''')

    # City filter buttons
    filter_buttons = ['<button class="filter-btn active" data-city="all">全て</button>']
    for ck in ["osaka", "fukuoka", "tokyo"]:
        count = by_city.get(ck, 0)
        label = CITY_LABELS.get(ck, ck)
        accent = CITY_ACCENTS.get(ck, "#3b9eff")
        filter_buttons.append(f'<button class="filter-btn" data-city="{ck}" style="--btn-accent:{accent}">{label} ({count})</button>')

    nav_pages_updated = list(_NAV_PAGES) + [{"href": "ittomono.html", "label": "一棟もの"}]
    nav_links = []
    for p in nav_pages_updated:
        cls = ' class="cur"' if p["href"] == "ittomono.html" else ""
        nav_links.append(f'<a href="{p["href"]}"{cls}>{p["label"]}</a>')
    gnav_html = f'<div class="gnav"><div class="gnav-inner">{"".join(nav_links)}</div></div>'

    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>一棟もの物件検索 | Property Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #050507; --surface: rgba(255,255,255,0.035); --surface-hover: rgba(255,255,255,0.065);
      --border: rgba(255,255,255,0.08); --border-hover: rgba(255,255,255,0.18);
      --text: #f5f5f7; --text-secondary: #a1a1aa; --muted: #71717a; --dim: #3f3f46;
      --accent: #f59e0b; --accent-rgb: 245,158,11;
      --gnav-height: 52px; --z-nav: 100; --z-subnav: 90;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter','Noto Sans JP',system-ui,sans-serif;
      background: var(--bg); color: var(--text);
      min-height: 100vh; -webkit-font-smoothing: antialiased;
    }}
    {site_header_css()}
    {global_nav_css()}

    .page {{ max-width: 1400px; margin: 0 auto; padding: 0 24px; }}

    /* Hero */
    .hero {{
      padding: 32px 0 24px;
      border-bottom: 1px solid var(--border);
    }}
    .hero h1 {{
      font-size: clamp(20px, 2.5vw, 26px); font-weight: 700;
      background: linear-gradient(135deg, var(--accent), #fbbf24);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .hero-sub {{ font-size: 13px; color: var(--text-secondary); margin-top: 6px; }}

    /* Stats bar */
    .stats-bar {{
      display: flex; gap: 24px; flex-wrap: wrap; padding: 16px 0;
      border-bottom: 1px solid var(--border);
    }}
    .stat-item {{ display: flex; flex-direction: column; gap: 2px; }}
    .stat-label {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }}
    .stat-value {{ font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono',monospace; color: var(--accent); }}

    /* Filters */
    .filter-bar {{ display: flex; gap: 8px; padding: 16px 0; flex-wrap: wrap; }}
    .filter-btn {{
      padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border);
      background: transparent; color: var(--text-secondary); font-size: 12px; font-weight: 500;
      cursor: pointer; transition: all .2s;
    }}
    .filter-btn:hover {{ border-color: var(--border-hover); color: var(--text); }}
    .filter-btn.active {{
      background: rgba(var(--accent-rgb), 0.15); border-color: var(--accent); color: var(--accent);
    }}

    /* Search conditions */
    .conditions {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 16px 20px; margin: 16px 0 0;
    }}
    .conditions h3 {{ font-size: 12px; font-weight: 600; color: var(--accent); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.06em; }}
    .conditions ul {{ list-style: none; }}
    .conditions li {{ font-size: 12px; color: var(--text-secondary); padding: 3px 0; }}
    .conditions li::before {{ content: "\\2022"; color: var(--accent); margin-right: 8px; }}

    /* Table */
    .table-wrap {{ overflow-x: auto; margin-top: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th {{
      text-align: left; padding: 10px 8px; font-size: 10px; font-weight: 600;
      color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em;
      border-bottom: 1px solid var(--border); white-space: nowrap;
      cursor: pointer; user-select: none;
    }}
    th:hover {{ color: var(--text); }}
    td {{ padding: 12px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); vertical-align: top; }}
    tr.prop-row:hover {{ background: var(--surface-hover); }}
    tr.hidden {{ display: none; }}

    .col-rank {{ width: 36px; text-align: center; color: var(--muted); font-family: 'JetBrains Mono',monospace; }}
    .col-name a {{ color: var(--text); text-decoration: none; font-weight: 500; }}
    .col-name a:hover {{ color: var(--accent); text-decoration: underline; }}
    .col-price {{ font-family: 'JetBrains Mono',monospace; white-space: nowrap; color: #fbbf24; font-weight: 600; }}
    .col-location {{ max-width: 160px; }}
    .col-structure {{ white-space: nowrap; }}
    .col-units {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; }}
    .col-avgm2 {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; min-width: 70px; }}
    .col-avgm2 .layout-detail {{ font-size: 9px; color: var(--text-secondary); font-family: 'Noto Sans JP',sans-serif; margin-top: 2px; white-space: normal; line-height: 1.3; }}
    .col-yield {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; color: #34d399; }}
    .col-built {{ white-space: nowrap; }}
    .col-station {{ max-width: 200px; font-size: 11px; }}
    .col-score {{ text-align: center; }}
    .col-breakdown {{ min-width: 220px; }}

    .row-meta {{ display: flex; gap: 6px; margin-top: 4px; align-items: center; flex-wrap: wrap; }}
    .city-tag {{
      font-size: 9px; font-weight: 600; padding: 1px 6px; border-radius: 3px;
      border: 1px solid; text-transform: uppercase; letter-spacing: 0.04em;
    }}
    .src-tag {{
      font-size: 9px; color: var(--muted); padding: 1px 6px; border-radius: 3px;
      background: rgba(255,255,255,0.04);
    }}
    .badge-new {{
      font-size: 9px; font-weight: 700; color: #22c55e; padding: 1px 6px;
      border-radius: 3px; border: 1px solid #22c55e; animation: pulse 2s infinite;
    }}
    .fs-date {{ font-size: 9px; color: var(--dim); }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.6}} }}

    .score-total {{ font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono',monospace; }}
    .tier-badge {{
      font-size: 9px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
      display: inline-block; margin-top: 2px;
    }}
    .tier-strong {{ background: rgba(34,197,94,0.15); color: #22c55e; }}
    .tier-good {{ background: rgba(250,204,21,0.15); color: #facc15; }}
    .tier-conditional {{ background: rgba(251,146,60,0.15); color: #fb923c; }}
    .tier-pass {{ background: rgba(239,68,68,0.15); color: #ef4444; }}

    .breakdown-pills {{ display: flex; flex-wrap: wrap; gap: 3px; margin-bottom: 4px; }}
    .sc-pill {{
      font-size: 9px; font-weight: 500; padding: 1px 5px; border-radius: 3px;
      font-family: 'JetBrains Mono',monospace; white-space: nowrap;
    }}
    .sc-pos {{ background: rgba(34,197,94,0.12); color: #4ade80; }}
    .sc-neg {{ background: rgba(239,68,68,0.12); color: #f87171; }}
    .sc-zero {{ background: rgba(255,255,255,0.04); color: var(--dim); }}
    .comment {{ font-size: 10px; color: var(--text-secondary); line-height: 1.4; }}

    footer {{
      margin-top: 48px; padding: 24px 0 32px;
      border-top: 1px solid var(--border);
      display: flex; justify-content: space-between;
      font-size: 10px; color: var(--dim);
    }}

    @media (max-width: 768px) {{
      .page {{ padding: 0 12px; }}
      .stats-bar {{ gap: 16px; }}
      .stat-value {{ font-size: 15px; }}
      .col-breakdown {{ min-width: 180px; }}
      table {{ font-size: 11px; }}
    }}
  </style>
</head>
<body>
{site_header_html()}
{gnav_html}

<div class="page">
  <div class="hero">
    <h1>一棟もの物件検索</h1>
    <div class="hero-sub">一棟マンション・一棟アパート | 楽待マルチエリア検索</div>
  </div>

  <div class="stats-bar">
    <div class="stat-item">
      <div class="stat-label">Total Properties</div>
      <div class="stat-value">{total}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Avg Price</div>
      <div class="stat-value">{avg_price // 10000}億{avg_price % 10000}万</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Avg Yield</div>
      <div class="stat-value">{avg_yield}%</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Osaka</div>
      <div class="stat-value">{by_city.get("osaka", 0)}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Fukuoka</div>
      <div class="stat-value">{by_city.get("fukuoka", 0)}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Tokyo</div>
      <div class="stat-value">{by_city.get("tokyo", 0)}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Updated</div>
      <div class="stat-value" style="font-size:13px">{dt.date.today().isoformat()}</div>
    </div>
  </div>

  <div class="filter-bar">
    {"".join(filter_buttons)}
  </div>

  <div class="conditions">
    <h3>Search Conditions</h3>
    <ul>
      <li>価格帯: 1.5億〜2億円</li>
      <li>物件種別: 一棟マンション + 一棟アパート</li>
      <li>データソース: 楽待 (rakumachi.jp)</li>
      <li>エリア: 大阪（北区/西区/中央区等） / 福岡（博多区/中央区/南区） / 東京（渋谷区/新宿区/目黒区等）</li>
      <li>築年数: フィルタなし（スコアリングで新耐震基準を加点）</li>
      <li>スコアリング: 価格帯+構造(RC>S>木造)+戸数+利回り+耐震+駅距離+立地</li>
    </ul>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-sort="rank">#</th>
          <th data-sort="name">物件名</th>
          <th data-sort="price">価格</th>
          <th data-sort="location">所在地</th>
          <th data-sort="structure">構造</th>
          <th data-sort="units">戸数</th>
          <th data-sort="avgm2">㎡/戸</th>
          <th data-sort="yield">利回り</th>
          <th data-sort="built">築年</th>
          <th>駅</th>
          <th data-sort="score">Score</th>
          <th>内訳・コメント</th>
        </tr>
      </thead>
      <tbody id="prop-tbody">
        {"".join(table_html)}
      </tbody>
    </table>
  </div>

  <footer>
    <div>ITTOMONO SEARCH &mdash; 2026</div>
    <div>AUTO-UPDATED DAILY</div>
  </footer>
</div>

<script>
// City filter
document.querySelectorAll('.filter-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    var city = btn.dataset.city;
    document.querySelectorAll('.prop-row').forEach(function(row) {{
      if (city === 'all' || row.dataset.city === city) {{
        row.classList.remove('hidden');
      }} else {{
        row.classList.add('hidden');
      }}
    }});
  }});
}});

// Column sorting
document.querySelectorAll('th[data-sort]').forEach(function(th) {{
  th.addEventListener('click', function() {{
    var key = th.dataset.sort;
    var tbody = document.getElementById('prop-tbody');
    var rows = Array.from(tbody.querySelectorAll('tr.prop-row'));
    var asc = th.classList.contains('sort-asc');
    document.querySelectorAll('th').forEach(function(h) {{ h.classList.remove('sort-asc','sort-desc'); }});
    th.classList.add(asc ? 'sort-desc' : 'sort-asc');
    rows.sort(function(a, b) {{
      var va, vb;
      if (key === 'score') {{
        va = parseInt(a.dataset.score); vb = parseInt(b.dataset.score);
      }} else if (key === 'rank') {{
        va = parseInt(a.querySelector('.col-rank').textContent);
        vb = parseInt(b.querySelector('.col-rank').textContent);
      }} else if (key === 'price') {{
        va = a.querySelector('.col-price').textContent;
        vb = b.querySelector('.col-price').textContent;
        va = parseFloat(va.replace(/[^0-9.]/g,'')); vb = parseFloat(vb.replace(/[^0-9.]/g,''));
      }} else if (key === 'units') {{
        va = parseInt(a.querySelector('.col-units').textContent) || 0;
        vb = parseInt(b.querySelector('.col-units').textContent) || 0;
      }} else if (key === 'avgm2') {{
        va = parseFloat(a.querySelector('.col-avgm2').textContent) || 0;
        vb = parseFloat(b.querySelector('.col-avgm2').textContent) || 0;
      }} else if (key === 'yield') {{
        va = parseFloat(a.querySelector('.col-yield').textContent) || 0;
        vb = parseFloat(b.querySelector('.col-yield').textContent) || 0;
      }} else if (key === 'built') {{
        va = parseInt(a.querySelector('.col-built').textContent) || 0;
        vb = parseInt(b.querySelector('.col-built').textContent) || 0;
      }} else {{
        va = (a.querySelector('.col-' + key) || {{}}).textContent || '';
        vb = (b.querySelector('.col-' + key) || {{}}).textContent || '';
      }}
      if (va < vb) return asc ? 1 : -1;
      if (va > vb) return asc ? -1 : 1;
      return 0;
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
  }});
}});
</script>
</body>
</html>'''


def main():
    """Load all city data and generate the 一棟もの report."""
    print(f"一棟もの レポート生成 - {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    all_rows = []
    for city_key in ["osaka", "fukuoka", "tokyo"]:
        data_path = DATA_DIR / f"ittomono_{city_key}_raw.txt"
        rows = parse_data_file(data_path, city_key)
        print(f"  {CITY_LABELS[city_key]}: {len(rows)}件")
        all_rows.extend(rows)

    if not all_rows:
        print("  物件が0件 — データファイルを確認してください")
        return

    # Score all rows
    for row in all_rows:
        score_row(row)

    # Generate HTML
    html_content = build_report_html(all_rows)

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "ittomono.html"
    out_path.write_text(html_content, encoding="utf-8")
    print(f"  Generated: {out_path}")
    print(f"  Total: {len(all_rows)}件")


if __name__ == "__main__":
    main()
