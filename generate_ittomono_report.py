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
from revenue_calc import analyze as revenue_analyze, RevenueAnalysis

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
    revenue: RevenueAnalysis | None = None


def parse_data_file(data_path: Path, city_key: str) -> list[IttomonoRow]:
    """Parse pipe-delimited data file for 一棟もの.

    Supports both formats:
    - 15-column (score prepended): score|source|name|...|url
    - 14-column (legacy): source|name|...|url
    """
    rows = []
    if not data_path.exists():
        return rows

    for line in data_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]

        # Detect format: if first field is a number, it's the score column
        if len(parts) >= 15 and parts[0].isdigit():
            offset = 1  # skip score column
        elif len(parts) >= 14:
            offset = 0
        else:
            continue

        row = IttomonoRow(
            source=parts[offset],
            name=parts[offset + 1],
            price_text=parts[offset + 2],
            location=parts[offset + 3],
            area_text=parts[offset + 4],
            built_text=parts[offset + 5],
            station_text=parts[offset + 6],
            structure=parts[offset + 7],
            units=parts[offset + 8],
            yield_text=parts[offset + 9],
            layout_detail=parts[offset + 10],
            url=parts[-1],  # URL is always the last column
            city_key=city_key,
        )
        if offset == 1:
            row.total_score = int(parts[0])
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

    # Walk minutes — Kenbiya uses "歩N分", SUUMO/楽待 use "徒歩N分"
    if "バス" not in row.station_text:
        m = re.search(r"(?:徒歩|歩)\s*(\d+)\s*分", row.station_text)
        row.walk_min = int(m.group(1)) if m else None

    # Units count
    m = re.search(r"(\d+)", row.units)
    row.units_count = int(m.group(1)) if m else 0

    # Yield — cap at 15% (higher is scraping error)
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", row.yield_text)
    if m:
        val = float(m.group(1))
        if val <= 15.0:
            row.yield_pct = val
        else:
            row.yield_pct = 0.0  # discard: scraping error
            row.yield_text = ""  # clear display
    else:
        row.yield_pct = 0.0

    # Average sqm per unit + land area flag
    if row.area_sqm and row.units_count and row.units_count > 0:
        row.avg_sqm_per_unit = round(row.area_sqm / row.units_count, 1)
        # If avg < 15㎡/unit, almost certainly land area not building area
        if row.avg_sqm_per_unit < 15.0 and "(土地)" not in row.area_text:
            row.area_text = row.area_text + "(※土地面積の可能性)"


# ============================================================
# Scoring system for 一棟もの
# ============================================================

def price_score(price_man: int) -> int:
    """Price scoring for investment properties across all price ranges."""
    # High range: 1.5億〜2億 (original sweet spot)
    if 16000 <= price_man <= 18000:
        return 15  # Sweet spot
    if 15000 <= price_man <= 20000:
        return 10  # Within range
    if 14000 <= price_man < 15000:
        return 5
    if 20000 < price_man <= 22000:
        return 5
    # Mid range: 5000万〜1.5億 (cash flow oriented)
    if 5000 <= price_man <= 10000:
        return 10  # Accessible price, good leverage
    if 10000 < price_man < 14000:
        return 7  # Mid-high
    # Low range: under 5000万 (high yield / cash buy)
    if 3000 <= price_man < 5000:
        return 5
    return 0


def structure_score(structure: str) -> int:
    """Building structure scoring. RC/SRC > S造 > 木造. Floors-only → neutral."""
    if not structure:
        return 0
    if "RC" in structure or "SRC" in structure or "鉄筋コンクリート" in structure:
        return 15
    if "S造" in structure or "鉄骨" in structure:
        return 10
    if "木造" in structure:
        return 5
    # Floors-only (e.g. "2階建") — material unknown, small neutral score
    if re.search(r"\d+階建", structure):
        return 3
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
    """Location scoring using existing city classifiers.

    For 一棟もの: outer wards return 0 not -5 (rental demand still exists in
    peripheral areas — penalizing them distorts investment comparison).
    """
    text = f"{row.location} {row.station_text} {row.name}"
    if row.city_key == "osaka":
        label, score = classify_location_osaka(text)
    elif row.city_key == "tokyo":
        label, score = classify_location_tokyo(text)
        if score < 0:
            score = 0  # outer wards neutral for rental investment
    elif row.city_key == "fukuoka":
        label, score = classify_location_fukuoka(text)
    else:
        label, score = "Other", 0
    return label, score


def cf_score(row: IttomonoRow) -> int:
    """Cash flow scoring. CF+ properties get significant bonus."""
    rev = row.revenue
    if not rev or rev.verdict == "データ不足":
        return 0
    mcf = rev.monthly_cf
    if mcf > 20:
        return 20  # Strong CF
    if mcf > 10:
        return 15  # Good CF
    if mcf > 0:
        return 10  # Positive CF
    if mcf > -10:
        return 0   # Slightly negative
    return -5      # Deep negative


def score_row(row: IttomonoRow) -> None:
    """Calculate total score for a 一棟もの property."""
    # Revenue analysis first (needed for CF score)
    if row.price_man > 0 and row.yield_pct > 0:
        row.revenue = revenue_analyze(
            price_man=row.price_man,
            yield_pct=row.yield_pct,
            structure=row.structure or "",
            built_year=row.built_year,
            units_count=row.units_count,
            area_sqm=row.area_sqm,
        )

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
        "cf": cf_score(row),
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

    if b.get("cf", 0) >= 15:
        mcf = row.revenue.monthly_cf if row.revenue else 0
        strengths.append(f"CF+{mcf:.0f}万/月")
    elif b.get("cf", 0) >= 10:
        mcf = row.revenue.monthly_cf if row.revenue else 0
        strengths.append(f"CF黒字+{mcf:.0f}万/月")
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
    if b.get("cf", 0) < 0:
        mcf = row.revenue.monthly_cf if row.revenue else 0
        cautions.append(f"CF赤字{mcf:+.0f}万/月")
    elif b.get("cf", 0) == 0 and row.revenue and row.revenue.monthly_cf <= 0:
        cautions.append("CF微赤字")
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
    """Build the avg ㎡/戸 cell with total area and layout detail."""
    parts = []
    if r.avg_sqm_per_unit is not None:
        val = r.avg_sqm_per_unit
        if val >= 35:
            color = "var(--accent-green)"
        elif val >= 25:
            color = "#facc15"
        else:
            color = "var(--accent-red-light)"
        parts.append(f'<span style="color:{color};font-weight:600">{val}㎡</span>')
    else:
        parts.append('<span style="color:var(--dim)">-</span>')
    # Total building area as small subscript (replaces the removed col-area column)
    if r.area_sqm:
        area_int = int(r.area_sqm)
        flag = "(土)" if "(土地)" in r.area_text else ""
        parts.append(f'<div class="area-sub">計{area_int}m²{flag}</div>')
    elif r.area_text and r.area_text != "-":
        # Fallback: show raw text truncated
        short = re.sub(r"\.\d+", "", r.area_text)[:10]
        parts.append(f'<div class="area-sub">{html.escape(short)}</div>')
    # Layout detail (e.g. "1K×6戸, 1LDK×6戸")
    if r.layout_detail:
        parts.append(f'<div class="layout-detail">{html.escape(r.layout_detail)}</div>')
    return "".join(parts)


CITY_LABELS = {"osaka": "大阪", "fukuoka": "福岡", "tokyo": "東京"}
CITY_ACCENTS = {"osaka": "#6ee7ff", "fukuoka": "#ff6b6b", "tokyo": "var(--accent-purple)"}


def _revenue_kpi(r: IttomonoRow) -> tuple[str, str]:
    """Return (net_yield_html, annual_cf_html) for card KPI row."""
    rev = r.revenue
    if not rev or rev.verdict == "データ不足":
        return ('<span class="kpi-netyield">-</span>', '<span class="kpi-cf">-</span>')

    # Net yield coloring
    ny = rev.net_yield_pct
    if ny >= 5:
        ny_color = "var(--accent-green)"
    elif ny >= 3:
        ny_color = "#facc15"
    else:
        ny_color = "var(--accent-red-light)"
    ny_html = f'<span class="kpi-netyield" style="color:{ny_color}">実質{ny:.1f}%</span>'

    # Monthly CF coloring
    mcf = rev.monthly_cf
    if mcf > 30:
        cf_color = "var(--accent-green)"
    elif mcf > 15:
        cf_color = "#34d399"
    elif mcf > 0:
        cf_color = "#facc15"
    else:
        cf_color = "var(--accent-red-light)"
    sign = "+" if mcf >= 0 else ""
    cf_html = f'<span class="kpi-cf" style="color:{cf_color}">CF{sign}{mcf:.1f}万/月</span>'

    return ny_html, cf_html


def _revenue_block_html(r: IttomonoRow) -> str:
    """Build the L2 revenue detail block — waterfall breakdown format."""
    rev = r.revenue
    if not rev or rev.verdict == "データ不足":
        return ""

    def _f(v: float) -> str:
        if abs(v) >= 10000:
            return f"{v/10000:.2f}億"
        return f"{v:,.0f}万"

    p = rev.params
    vclass = {
        "高CF物件": "rv-high", "安定CF": "rv-stable",
        "薄利": "rv-thin", "CF赤字": "rv-red",
    }.get(rev.verdict, "rv-thin")

    payback = f"{rev.payback_years:.1f}年" if rev.payback_years != float("inf") else "∞"

    # CF color
    mcf = rev.monthly_cf
    cf_color = "var(--accent-green)" if mcf > 30 else "#34d399" if mcf > 15 else "#facc15" if mcf > 0 else "var(--accent-red-light)"
    cf_sign = "+" if rev.annual_cf >= 0 else ""

    # Building price for depreciation breakdown
    building_price = rev.price_man * p.building_ratio

    return f'''<div class="revenue-block">
      <div class="rv-header">
        <span class="rv-title">収益シミュレーション</span>
        <span class="rv-verdict {vclass}">{rev.verdict}</span>
      </div>
      <div class="rv-assumptions">前提: 頭金{p.down_payment_ratio*100:.0f}% + 諸費用{p.acquisition_cost_rate*100:.0f}% / 金利{p.loan_rate_annual*100:.1f}% / {rev.loan_years}年ローン / 空室率{p.vacancy_rate*100:.0f}% / 経費率{p.opex_rate*100:.0f}%</div>

      <div class="rv-section">
        <div class="rv-section-title">収入 → キャッシュフロー</div>
        <div class="rv-row"><span class="rv-desc">年間賃料収入</span><span class="rv-note">= 価格{_f(rev.price_man)} × 利回り{rev.yield_pct}%</span><span class="rv-amount">{_f(rev.gross_income)}</span></div>
        <div class="rv-row rv-minus"><span class="rv-desc">空室損（{p.vacancy_rate*100:.0f}%）</span><span class="rv-note"></span><span class="rv-amount">-{_f(rev.vacancy_loss)}</span></div>
        <div class="rv-row rv-minus"><span class="rv-desc">運営経費（管理・修繕・保険・税）</span><span class="rv-note">{p.opex_rate*100:.0f}%</span><span class="rv-amount">-{_f(rev.opex)}</span></div>
        <div class="rv-row rv-subtotal"><span class="rv-desc">営業利益</span><span class="rv-note"></span><span class="rv-amount">{_f(rev.noi)}</span></div>
        <div class="rv-row rv-minus"><span class="rv-desc">ローン返済</span><span class="rv-note">借入{_f(rev.loan_amount)} / {rev.loan_years}年</span><span class="rv-amount">-{_f(rev.annual_debt_service)}</span></div>
        <div class="rv-row rv-info"><span class="rv-desc">初期必要資金</span><span class="rv-note">頭金{_f(rev.down_payment)} + 諸費用{_f(rev.acquisition_cost)}</span><span class="rv-amount">{_f(rev.total_equity)}</span></div>
        <div class="rv-row rv-total"><span class="rv-desc">年間キャッシュフロー</span><span class="rv-note"></span><span class="rv-amount" style="color:{cf_color}">{cf_sign}{_f(rev.annual_cf)}</span></div>
        <div class="rv-row rv-highlight"><span class="rv-desc">月間キャッシュフロー</span><span class="rv-note"></span><span class="rv-amount" style="color:{cf_color}">{cf_sign}{rev.monthly_cf:,.1f}万/月</span></div>
      </div>

      <div class="rv-section">
        <div class="rv-section-title">減価償却 → 節税効果</div>
        <div class="rv-row"><span class="rv-desc">建物価格</span><span class="rv-note">= 取得価格 × 建物比率{p.building_ratio*100:.0f}%</span><span class="rv-amount">{_f(building_price)}</span></div>
        <div class="rv-row"><span class="rv-desc">残存耐用年数</span><span class="rv-note">法定{rev.useful_life}年 − 築{rev.price_man and rev.built_year and (2026 - rev.built_year) or "?"}年</span><span class="rv-amount">{rev.remaining_life}年</span></div>
        <div class="rv-row rv-subtotal"><span class="rv-desc">年間償却額</span><span class="rv-note">= {_f(building_price)} ÷ {rev.remaining_life}年</span><span class="rv-amount">{_f(rev.depreciation_annual)}</span></div>
        {"<div class='rv-row rv-highlight'><span class='rv-desc'>節税効果（損益通算）</span><span class='rv-note'>帳簿上の赤字 → 他の所得と相殺</span><span class='rv-amount' style=\"color:var(--accent-green)\">+{0}万/年</span></div>".format(f"{rev.tax_benefit:,.0f}") if rev.tax_benefit > 0 else "<div class='rv-row'><span class='rv-desc'>税負担</span><span class='rv-note'>課税所得{0}万 × 税率{1:.0f}%</span><span class='rv-amount'>-{2}万</span></div>".format(f"{rev.taxable_income:,.0f}", p.tax_rate*100, f"{rev.taxable_income * p.tax_rate:,.0f}")}
      </div>

      <div class="rv-bottom">
        <div class="rv-bottom-item"><span class="rv-bottom-label">税引後CF</span><span class="rv-bottom-val">{"+" if rev.after_tax_cf >= 0 else ""}{_f(rev.after_tax_cf)}/年</span></div>
        <div class="rv-bottom-item"><span class="rv-bottom-label">実質利回り</span><span class="rv-bottom-val">{rev.net_yield_pct:.1f}%</span></div>
        <div class="rv-bottom-item"><span class="rv-bottom-label">自己資金回収</span><span class="rv-bottom-val">{payback}</span></div>
      </div>
    </div>'''


def _monthly_rent_text(r) -> str:
    """Estimate monthly rent from price × yield for card KPI display."""
    if r.yield_pct > 0 and r.price_man > 0:
        annual_rent = r.price_man * r.yield_pct / 100  # 万円/年
        monthly = annual_rent / 12
        return f'<span class="kpi-label">家賃</span>{monthly:.0f}万/月'
    return '-'


def _verdict_label(tier_class: str) -> tuple[str, str]:
    """Return (verdict_text, verdict_css_class) based on tier."""
    if tier_class == "tier-strong":
        return "買い候補", "verdict-buy"
    elif tier_class == "tier-good":
        return "要検討", "verdict-consider"
    elif tier_class == "tier-conditional":
        return "条件付き", "verdict-conditional"
    return "見送り", "verdict-pass"


def _clean_name(name: str) -> str:
    """Remove internal ID hashes from fallback names (e.g. '健美家 世田谷区#5gnu' → '世田谷区 (健美家)')."""
    # Pattern: "{site} {location}#{4-char-id}"
    m = re.match(r"(楽待|健美家)\s+(.+?)#[a-z0-9]{4}$", name)
    if m:
        loc = m.group(2).strip().rstrip("-ー／/")
        return f"{loc} ({m.group(1)})"
    # Remove trailing hash if present without site prefix
    cleaned = re.sub(r"#[a-z0-9]{4,}$", "", name).strip()
    return cleaned


_STATION_NAME_PATTERN = re.compile(r"(?:駅」?|バス停)\s*徒歩[約]?\s*\d+分")


def _has_building_name_ittomono(name: str) -> bool:
    """Check if name contains a real building/mansion name."""
    # 3+ consecutive katakana = likely a building name
    if re.search(r"[\u30A0-\u30FF]{3,}", name):
        return True
    # Known building suffixes in kanji
    if re.search(r"[\u4e00-\u9fff](?:荘|館|邸|苑|棟|号棟)", name):
        return True
    return False


def _fix_station_name(r: "IttomonoRow") -> str:
    """If the name field is ONLY a station/bus-stop text (no real building name),
    replace it with a human-readable fallback: '{区/市名} {構造}'."""
    if not _STATION_NAME_PATTERN.search(r.name):
        return r.name  # name looks fine
    # If name contains a real building name, keep it
    if _has_building_name_ittomono(r.name):
        return r.name
    # Extract ward/city name from location
    loc = r.location.strip()
    area_m = re.search(r"([\u4e00-\u9fff]{2,6}[区市町村])", loc)
    area_label = area_m.group(1) if area_m else loc[:6] if loc else "物件"
    struct = r.structure if r.structure else ""
    struct_short = ""
    if "RC" in struct or "鉄筋コンクリート" in struct:
        struct_short = "RC"
    elif "SRC" in struct:
        struct_short = "SRC"
    elif "S造" in struct or "鉄骨" in struct:
        struct_short = "S造"
    elif "木造" in struct:
        struct_short = "木造"
    fallback = f"{area_label} {struct_short}".strip() if struct_short else area_label
    print(f"  [FIX] 駅名→物件名修正: '{r.name}' → '{fallback}'")
    return fallback


def _filter_rows(rows: list[IttomonoRow]) -> list[IttomonoRow]:
    """Remove obviously bad data before dedup and scoring."""
    import datetime as _dt
    current_year = _dt.date.today().year
    filtered = []
    for r in rows:
        # units < 2: not an apartment building (likely a single unit or parsing error)
        if r.units_count > 0 and r.units_count < 2:
            print(f"  [FILTER] 戸数1戸除外: {r.name} ({r.price_text}, {r.units})")
            continue
        # Future completion: not yet built
        if r.built_year and r.built_year > current_year:
            print(f"  [FILTER] 未来竣工除外: {r.name} ({r.built_year}年竣工予定)")
            continue
        # Fix station text used as property name (ftakken scraper artifact)
        r.name = _fix_station_name(r)
        # Clean internal IDs from displayed names
        r.name = _clean_name(r.name)
        filtered.append(r)
    removed = len(rows) - len(filtered)
    if removed > 0:
        print(f"  データ品質フィルタ: {removed}件除外")
    return filtered


def _url_district_matches(url: str, location: str, city_key: str) -> bool:
    """URLのdistrictとlocationが一致するか（search_ittomono._url_location_validの簡易版）。"""
    import sys as _sys
    _this_dir = Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))
    try:
        from search_ittomono import _url_location_valid
        return _url_location_valid(url, location, city_key)
    except Exception:
        return True  # import失敗時は通過


def _deduplicate_rows(rows: list[IttomonoRow]) -> list[IttomonoRow]:
    """Deduplicate by (price_man, area_rounded, units_count).

    Priority: URL district matches location > more specific location text.
    This ensures cross-listed properties use the entry whose URL path
    matches the extracted location (not a mis-matched ward search page).
    """
    seen: dict[tuple, IttomonoRow] = {}
    for r in rows:
        area_m = re.search(r"([\d.]+)", r.area_text)
        area_num = float(area_m.group(1)) if area_m else 0
        sig = (r.price_man, round(area_num, 0), r.units_count)
        url_ok = _url_district_matches(r.url, r.location, r.city_key)
        if sig in seen:
            existing = seen[sig]
            existing_url_ok = _url_district_matches(existing.url, existing.location, existing.city_key)
            # Prefer: URL-location matched entry > longer location text
            if url_ok and not existing_url_ok:
                seen[sig] = r  # new entry is better (URL matches)
            elif url_ok == existing_url_ok and len(r.location) > len(existing.location):
                seen[sig] = r  # same quality, longer location wins
        else:
            seen[sig] = r
    deduped = list(seen.values())
    dup_count = len(rows) - len(deduped)
    if dup_count > 0:
        print(f"  レポート側重複除外: {dup_count}件")
    return deduped


def build_report_html(all_rows: list[IttomonoRow]) -> str:
    """Build the 一棟もの HTML report — card view (mobile) + table view (desktop)."""
    all_rows = _filter_rows(all_rows)
    all_rows = _deduplicate_rows(all_rows)
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

    # Build card + table HTML
    card_html = []
    table_html = []
    for idx, r in enumerate(sorted_rows, start=1):
        fs_display = _format_first_seen(r.url, first_seen)
        is_new = fs_display == "NEW"
        new_badge = '<span class="badge-new">NEW</span>' if is_new else f'<span class="fs-date">{fs_display}</span>' if fs_display else ''
        verdict_text, verdict_class = _verdict_label(r.tier_class)

        b = r.score_breakdown
        pills = []
        for label, key in [("CF", "cf"), ("価格", "price"), ("構造", "structure"), ("戸数", "units"),
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
        ny_html, cf_html = _revenue_kpi(r)
        rv_block = _revenue_block_html(r)

        # --- Card view item ---
        card_html.append(f'''
        <div class="card" data-city="{r.city_key}" data-score="{r.total_score}">
          <div class="card-head" onclick="this.parentElement.classList.toggle('open')">
            <div class="card-top">
              <span class="card-rank">#{idx}</span>
              <span class="score-badge" style="color:{r.tier_color};border-color:{r.tier_color}">{r.total_score}</span>
              <span class="verdict {verdict_class}">{verdict_text}</span>
              {new_badge}
            </div>
            <div class="card-title">
              <a href="{html.escape(r.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">{html.escape(r.name)}</a>
            </div>
            <div class="card-kpi">
              <span class="kpi-price">{html.escape(r.price_text)}</span>
              <span class="kpi-yield">{html.escape(r.yield_text or '-')}</span>
              <span class="kpi-rent">{_monthly_rent_text(r)}</span>
              {ny_html}
              {cf_html}
              <span class="kpi-units">{html.escape(r.units or '-')}</span>
              <span class="kpi-struct">{html.escape(r.structure or '-')}</span>
              <span class="kpi-area">{html.escape(r.area_text or '-')}</span>
            </div>
            <div class="card-meta">
              <span class="city-tag" style="border-color:{city_accent};color:{city_accent}">{city_label}</span>
              <span class="card-loc">{html.escape(r.location)}</span>
            </div>
            <svg class="chevron" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>
          </div>
          <div class="card-detail">
            <div class="detail-grid">
              <div class="dg-item"><span class="dg-label">築年</span><span class="dg-val">{html.escape(r.built_text or '-')}</span></div>
              <div class="dg-item"><span class="dg-label">駅</span><span class="dg-val">{html.escape(r.station_text or '-')}</span></div>
              <div class="dg-item"><span class="dg-label">面積</span><span class="dg-val">{html.escape(r.area_text or '-')}</span></div>
              <div class="dg-item"><span class="dg-label">㎡/戸</span><span class="dg-val">{_avg_sqm_cell(r)}</span></div>
            </div>
            {rv_block}
            <div class="detail-breakdown">
              <div class="breakdown-pills">{" ".join(pills)}</div>
            </div>
            <div class="detail-comment">{html.escape(r.detail_comment)}</div>
          </div>
        </div>''')

        # --- Table: revenue cells ---
        rev = r.revenue
        if rev and rev.verdict != "データ不足":
            tbl_netyield = f'<span style="color:{"var(--accent-green)" if rev.net_yield_pct >= 5 else "#facc15" if rev.net_yield_pct >= 3 else "var(--accent-red-light)"}">{rev.net_yield_pct:.1f}%</span>'
            mcf = rev.monthly_cf
            cf_sign = "+" if mcf >= 0 else ""
            tbl_cf = f'<span style="color:{"var(--accent-green)" if mcf > 30 else "#34d399" if mcf > 15 else "#facc15" if mcf > 0 else "var(--accent-red-light)"}">{cf_sign}{mcf:.1f}万</span>'
        else:
            tbl_netyield = '<span style="color:var(--dim)">-</span>'
            tbl_cf = '<span style="color:var(--dim)">-</span>'

        # --- Table row ---
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
          <td class="col-netyield">{tbl_netyield}</td>
          <td class="col-cf">{tbl_cf}</td>
          <td class="col-built">{html.escape(r.built_text or '-')}</td>
          <td class="col-station">{html.escape(r.station_text or '-')}</td>
          <td class="col-score">
            <div class="score-total" style="color:{r.tier_color}">{r.total_score}</div>
            <div class="verdict {verdict_class}">{verdict_text}</div>
          </td>
          <td class="col-breakdown">
            <div class="breakdown-pills">{" ".join(pills)}</div>
            <div class="comment">{html.escape(r.detail_comment)}</div>
          </td>
        </tr>''')

    # City filter buttons
    filter_buttons = ['<button class="filter-btn active" data-city="all">ALL</button>']
    for ck in ["osaka", "fukuoka", "tokyo"]:
        count = by_city.get(ck, 0)
        label = CITY_LABELS.get(ck, ck)
        accent = CITY_ACCENTS.get(ck, "#3b9eff")
        filter_buttons.append(f'<button class="filter-btn" data-city="{ck}" style="--btn-accent:{accent}">{label} ({count})</button>')

    nav_links = []
    for p in _NAV_PAGES:
        cls = ' class="cur"' if p["href"] == "ittomono.html" else ""
        nav_links.append(f'<a href="{p["href"]}"{cls}>{p["label"]}</a>')
    gnav_html_str = f'<div class="gnav"><div class="gnav-inner">{"".join(nav_links)}</div></div>'

    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>\u4e00\u68df\u3082\u306e\u7269\u4ef6\u691c\u7d22 | Property Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0f1117; --surface: rgba(255,255,255,0.035); --surface-hover: rgba(255,255,255,0.065);
      --surface-2: rgba(255,255,255,0.05); --surface-3: rgba(255,255,255,0.07);
      --border: rgba(255,255,255,0.08); --border-hover: rgba(255,255,255,0.18);
      --text: #f5f5f7; --text-secondary: #a1a1aa; --muted: #71717a; --dim: #3f3f46;
      --accent: #f59e0b; --accent-rgb: 245,158,11;
      --green: #22c55e; --yellow: #facc15; --orange: #fb923c; --red: #ef4444;
      --gnav-height: 52px; --z-nav: 100; --z-subnav: 90;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter','Noto Sans JP',system-ui,sans-serif;
      background: var(--bg); color: var(--text);
      min-height: 100vh; -webkit-font-smoothing: antialiased;
      font-size: 14px;
    }}
    {site_header_css()}
    {global_nav_css()}

    .page {{ max-width: 1400px; margin: 0 auto; padding: 0 20px; }}

    /* ===== Hero (compact) ===== */
    .hero {{ padding: 24px 0 16px; }}
    .hero h1 {{
      font-size: clamp(20px, 2.5vw, 26px); font-weight: 700;
      background: linear-gradient(135deg, var(--accent), #fbbf24);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .hero-sub {{ font-size: 13px; color: var(--text-secondary); margin-top: 4px; }}

    /* ===== Stats grid ===== */
    .stats-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
      gap: 8px; padding: 12px 0 16px;
    }}
    .sg-item {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
      padding: 10px 12px; text-align: center;
    }}
    .sg-label {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }}
    .sg-value {{ font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono',monospace; color: var(--accent); margin-top: 2px; }}

    /* ===== Toolbar: filters + view toggle ===== */
    .toolbar {{
      display: flex; align-items: center; gap: 8px; padding: 12px 0; flex-wrap: wrap;
      border-bottom: 1px solid var(--border);
      position: sticky; top: 88px; z-index: var(--z-subnav);
      background: var(--bg);
    }}
    .filter-btn {{
      padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border);
      background: transparent; color: var(--text-secondary); font-size: 13px; font-weight: 500;
      cursor: pointer; transition: all .2s;
    }}
    .filter-btn:hover {{ border-color: var(--border-hover); color: var(--text); }}
    .filter-btn.active {{
      background: rgba(var(--accent-rgb), 0.15); border-color: var(--accent); color: var(--accent);
    }}
    .view-toggle {{
      margin-left: auto; display: flex; gap: 4px;
      background: var(--surface); border-radius: 6px; padding: 2px;
    }}
    .vt-btn {{
      padding: 5px 10px; border: none; border-radius: 4px; background: transparent;
      color: var(--muted); font-size: 12px; cursor: pointer; transition: all .2s;
    }}
    .vt-btn.active {{ background: var(--surface-3); color: var(--text); }}
    .vt-btn svg {{ width: 16px; height: 16px; vertical-align: middle; stroke: currentColor; fill: none; stroke-width: 2; }}

    /* ===== Card view ===== */
    .card-list {{ display: flex; flex-direction: column; gap: 8px; padding: 16px 0; }}
    .card {{
      background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
      overflow: hidden; transition: border-color .2s;
    }}
    .card:hover {{ border-color: var(--border-hover); }}
    .card.hidden {{ display: none; }}
    .card-head {{
      padding: 14px 16px; cursor: pointer; position: relative;
      -webkit-tap-highlight-color: transparent;
    }}
    .card-top {{
      display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
    }}
    .card-rank {{ font-size: 11px; color: var(--muted); font-family: 'JetBrains Mono',monospace; }}
    .score-badge {{
      font-size: 15px; font-weight: 700; font-family: 'JetBrains Mono',monospace;
      border: 1.5px solid; border-radius: 6px; padding: 1px 8px; line-height: 1.3;
    }}
    .verdict {{
      font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
      letter-spacing: 0.02em;
    }}
    .verdict-buy {{ background: rgba(34,197,94,0.15); color: var(--green); }}
    .verdict-consider {{ background: rgba(250,204,21,0.15); color: var(--yellow); }}
    .verdict-conditional {{ background: rgba(251,146,60,0.15); color: var(--orange); }}
    .verdict-pass {{ background: rgba(239,68,68,0.15); color: var(--red); }}

    .card-title {{ margin-bottom: 8px; }}
    .card-title a {{
      color: var(--accent); text-decoration: none; font-weight: 600; font-size: 14px;
      line-height: 1.4;
    }}
    .card-title a::after {{ content: ' ↗'; font-size: 11px; opacity: 0.6; }}
    .card-title a:hover {{ text-decoration: underline; }}

    .card-kpi {{
      display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 6px;
    }}
    .card-kpi span {{ font-size: 13px; font-family: 'JetBrains Mono',monospace; }}
    .kpi-price {{ color: #fbbf24; font-weight: 600; }}
    .kpi-yield {{ color: #34d399; }}
    .kpi-rent {{ color: #60a5fa; }}
    .kpi-rent .kpi-label {{ font-size: 10px; color: var(--muted); margin-right: 2px; font-family: 'Inter',sans-serif; }}
    .kpi-area {{ color: var(--text-secondary); font-size: 12px !important; }}
    .kpi-units {{ color: var(--text-secondary); }}
    .kpi-struct {{ color: var(--text-secondary); }}

    .card-meta {{
      display: flex; align-items: center; gap: 6px;
    }}
    .card-loc {{ font-size: 12px; color: var(--text-secondary); }}

    .chevron {{
      position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
      width: 20px; height: 20px; stroke: var(--muted); fill: none; stroke-width: 2;
      transition: transform .2s;
    }}
    .card.open .chevron {{ transform: translateY(-50%) rotate(180deg); }}

    .card-detail {{
      max-height: 0; overflow: hidden; transition: max-height .3s ease;
      border-top: 1px solid transparent;
    }}
    .card.open .card-detail {{
      max-height: 900px; border-top-color: var(--border);
    }}
    .card-detail > * {{ padding: 0 16px; }}
    .card-detail > :first-child {{ padding-top: 12px; }}
    .card-detail > :last-child {{ padding-bottom: 14px; }}

    .detail-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px;
      margin-bottom: 10px;
    }}
    .dg-item {{ display: flex; justify-content: space-between; align-items: baseline; }}
    .dg-label {{ font-size: 11px; color: var(--muted); }}
    .dg-val {{ font-size: 13px; font-family: 'JetBrains Mono',monospace; }}
    .detail-breakdown {{ margin-bottom: 8px; }}
    .detail-comment {{ font-size: 12px; color: var(--text-secondary); line-height: 1.5; }}

    /* ===== Revenue block (waterfall breakdown) ===== */
    .revenue-block {{
      background: rgba(245,158,11,0.04); border: 1px solid rgba(245,158,11,0.12);
      border-radius: 8px; padding: 14px 16px; margin-bottom: 10px;
    }}
    .rv-header {{
      display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
    }}
    .rv-title {{
      font-size: 12px; font-weight: 700; color: var(--accent);
      letter-spacing: 0.04em;
    }}
    .rv-verdict {{
      font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
    }}
    .rv-high {{ background: rgba(34,197,94,0.15); color: var(--green); }}
    .rv-stable {{ background: rgba(52,211,153,0.15); color: #34d399; }}
    .rv-thin {{ background: rgba(250,204,21,0.15); color: var(--yellow); }}
    .rv-red {{ background: rgba(239,68,68,0.15); color: var(--red); }}
    .rv-assumptions {{
      font-size: 10px; color: var(--muted); margin-bottom: 10px;
      font-family: 'JetBrains Mono',monospace;
    }}
    .rv-section {{ margin-bottom: 10px; }}
    .rv-section-title {{
      font-size: 10px; font-weight: 700; color: var(--text-secondary);
      text-transform: uppercase; letter-spacing: 0.06em;
      margin-bottom: 4px; padding-bottom: 3px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }}
    .rv-row {{
      display: flex; align-items: baseline; padding: 3px 0; font-size: 12px;
    }}
    .rv-desc {{ flex: 1; color: var(--text); min-width: 0; }}
    .rv-note {{ flex: 1; font-size: 10px; color: var(--muted); text-align: right; padding-right: 12px; font-family: 'JetBrains Mono',monospace; }}
    .rv-amount {{
      width: 90px; text-align: right; font-weight: 600;
      font-family: 'JetBrains Mono',monospace; flex-shrink: 0;
    }}
    .rv-minus .rv-amount {{ color: var(--text-secondary); }}
    .rv-subtotal {{
      border-top: 1px solid rgba(255,255,255,0.08); margin-top: 2px; padding-top: 4px;
    }}
    .rv-subtotal .rv-desc {{ font-weight: 600; }}
    .rv-total {{
      border-top: 1px solid rgba(255,255,255,0.12); margin-top: 2px; padding-top: 4px;
    }}
    .rv-total .rv-desc {{ font-weight: 700; }}
    .rv-total .rv-amount {{ font-size: 14px; }}
    .rv-info {{ border-top: 1px dashed var(--border); padding-top: 4px; margin-top: 2px; }}
    .rv-info .rv-desc {{ color: var(--text-secondary); font-size: 11px; }}
    .rv-info .rv-amount {{ color: var(--text-secondary); font-size: 11px; }}
    .rv-info .rv-note {{ font-size: 10px; }}
    .rv-highlight {{ padding: 4px 0; }}
    .rv-highlight .rv-desc {{ font-weight: 600; color: var(--accent); }}
    .rv-highlight .rv-amount {{ font-size: 14px; }}
    .rv-bottom {{
      display: flex; gap: 16px; margin-top: 8px; padding-top: 8px;
      border-top: 1px solid rgba(255,255,255,0.08); flex-wrap: wrap;
    }}
    .rv-bottom-item {{ text-align: center; }}
    .rv-bottom-label {{ font-size: 10px; color: var(--muted); display: block; }}
    .rv-bottom-val {{ font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono',monospace; }}
    @media (max-width: 480px) {{
      .rv-note {{ display: none; }}
      .rv-amount {{ width: 80px; }}
    }}

    /* Revenue KPI in card */
    .kpi-netyield {{ font-weight: 600; }}
    .kpi-cf {{ font-weight: 600; }}

    /* ===== Table view (desktop) ===== */
    .table-wrap {{ overflow-x: auto; margin-top: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
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
    .col-name a {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
    .col-name a::after {{ content: ' ↗'; font-size: 10px; opacity: 0.5; }}
    .col-name a:hover {{ text-decoration: underline; }}
    .col-price {{ font-family: 'JetBrains Mono',monospace; white-space: nowrap; color: #fbbf24; font-weight: 600; }}
    .col-location {{ max-width: 160px; font-size: 12px; }}
    .col-structure {{ white-space: nowrap; }}
    .col-units {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; }}
    .col-avgm2 {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; min-width: 70px; }}
    .col-avgm2 .area-sub {{ font-size: 10px; color: var(--text-secondary); font-family: 'JetBrains Mono',monospace; margin-top: 2px; }}
    .col-avgm2 .layout-detail {{ font-size: 10px; color: var(--text-secondary); font-family: 'Noto Sans JP',sans-serif; margin-top: 2px; white-space: normal; line-height: 1.3; }}
    .col-yield {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; color: #34d399; }}
    .col-netyield {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; }}
    .col-cf {{ white-space: nowrap; font-family: 'JetBrains Mono',monospace; font-weight: 600; }}
    .col-built {{ white-space: nowrap; }}
    .col-station {{ max-width: 200px; font-size: 12px; }}
    .col-score {{ text-align: center; }}
    .col-breakdown {{ min-width: 220px; }}

    .row-meta {{ display: flex; gap: 6px; margin-top: 4px; align-items: center; flex-wrap: wrap; }}
    .city-tag {{
      font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px;
      border: 1px solid; text-transform: uppercase; letter-spacing: 0.04em;
    }}
    .src-tag {{
      font-size: 10px; color: var(--muted); padding: 1px 6px; border-radius: 3px;
      background: rgba(255,255,255,0.04);
    }}
    .badge-new {{
      font-size: 10px; font-weight: 700; color: var(--green); padding: 1px 6px;
      border-radius: 3px; border: 1px solid var(--green); animation: pulse 2s infinite;
    }}
    .fs-date {{ font-size: 10px; color: var(--dim); }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.6}} }}

    .score-total {{ font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono',monospace; }}
    .tier-badge,.tier-strong,.tier-good,.tier-conditional,.tier-pass {{ display: none; }}

    .breakdown-pills {{ display: flex; flex-wrap: wrap; gap: 3px; margin-bottom: 4px; }}
    .sc-pill {{
      font-size: 10px; font-weight: 500; padding: 2px 6px; border-radius: 3px;
      font-family: 'JetBrains Mono',monospace; white-space: nowrap;
    }}
    .sc-pos {{ background: rgba(34,197,94,0.12); color: #4ade80; }}
    .sc-neg {{ background: rgba(239,68,68,0.12); color: #f87171; }}
    .sc-zero {{ background: rgba(255,255,255,0.04); color: var(--dim); }}
    .comment {{ font-size: 12px; color: var(--text-secondary); line-height: 1.4; }}

    footer {{
      margin-top: 48px; padding: 24px 0 32px;
      border-top: 1px solid var(--border);
      display: flex; justify-content: space-between;
      font-size: 11px; color: var(--dim);
    }}

    /* ===== Responsive ===== */
    /* Mobile: card default, table hidden */
    @media (max-width: 960px) {{
      .table-wrap {{ display: none; }}
      .card-list {{ display: flex; }}
      .view-toggle {{ display: none; }}
    }}
    /* Desktop: table default, cards hidden */
    @media (min-width: 961px) {{
      .card-list {{ display: none; }}
      .table-wrap {{ display: block; }}
      body.view-cards .card-list {{ display: flex; }}
      body.view-cards .table-wrap {{ display: none; }}
      body.view-table .card-list {{ display: none; }}
      body.view-table .table-wrap {{ display: block; }}
    }}
    @media (max-width: 640px) {{
      .page {{ padding: 0 12px; }}
      .sg-value {{ font-size: 15px; }}
      .toolbar {{ top: 88px; padding: 8px 0; }}
      .card-head {{ padding: 12px 14px; }}
    }}
  </style>
</head>
<body>
{site_header_html()}
{gnav_html_str}

<div class="page">
  <div class="hero">
    <h1>\u4e00\u68df\u3082\u306e\u7269\u4ef6\u691c\u7d22</h1>
    <div class="hero-sub">\u4e00\u68df\u30de\u30f3\u30b7\u30e7\u30f3\u30fb\u4e00\u68df\u30a2\u30d1\u30fc\u30c8 | \u697d\u5f85 3\u90fd\u5e02\u691c\u7d22 | {dt.date.today().isoformat()}</div>
  </div>

  <div class="stats-grid">
    <div class="sg-item"><div class="sg-label">Total</div><div class="sg-value">{total}</div></div>
    <div class="sg-item"><div class="sg-label">Avg Price</div><div class="sg-value">{avg_price // 10000}.{avg_price % 10000 // 1000}\u5104</div></div>
    <div class="sg-item"><div class="sg-label">Avg Yield</div><div class="sg-value">{avg_yield}%</div></div>
    <div class="sg-item"><div class="sg-label">\u5927\u962a</div><div class="sg-value">{by_city.get("osaka", 0)}</div></div>
    <div class="sg-item"><div class="sg-label">\u798f\u5ca1</div><div class="sg-value">{by_city.get("fukuoka", 0)}</div></div>
    <div class="sg-item"><div class="sg-label">\u6771\u4eac</div><div class="sg-value">{by_city.get("tokyo", 0)}</div></div>
  </div>

  <div class="toolbar">
    {"".join(filter_buttons)}
    <div class="view-toggle">
      <button class="vt-btn" data-view="cards" title="Card view">
        <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      </button>
      <button class="vt-btn active" data-view="table" title="Table view">
        <svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
    </div>
  </div>

  <div class="card-list" id="card-list">
    {"".join(card_html)}
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-sort="rank">#</th>
          <th data-sort="name">\u7269\u4ef6\u540d</th>
          <th data-sort="price">\u4fa1\u683c</th>
          <th data-sort="location">\u6240\u5728\u5730</th>
          <th data-sort="structure">\u69cb\u9020</th>
          <th data-sort="units">\u6238\u6570</th>
          <th data-sort="avgm2">\u33a1/\u6238</th>
          <th data-sort="yield">\u5229\u56de\u308a</th>
          <th data-sort="netyield">\u5b9f\u8cea</th>
          <th data-sort="cf">CF/\u6708</th>
          <th data-sort="built">\u7bc9\u5e74</th>
          <th>\u99c5</th>
          <th data-sort="score">Score</th>
          <th>\u5185\u8a33</th>
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
// City filter — works on both cards and table rows
document.querySelectorAll('.filter-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    var city = btn.dataset.city;
    document.querySelectorAll('.prop-row, .card').forEach(function(el) {{
      if (city === 'all' || el.dataset.city === city) {{
        el.classList.remove('hidden');
      }} else {{
        el.classList.add('hidden');
      }}
    }});
  }});
}});

// View toggle (desktop only)
document.querySelectorAll('.vt-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.vt-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    document.body.classList.remove('view-cards', 'view-table');
    document.body.classList.add('view-' + btn.dataset.view);
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
      }} else if (key === 'netyield') {{
        va = parseFloat(a.querySelector('.col-netyield').textContent) || 0;
        vb = parseFloat(b.querySelector('.col-netyield').textContent) || 0;
      }} else if (key === 'cf') {{
        va = parseFloat(a.querySelector('.col-cf').textContent.replace(/[^\\d.-]/g,'')) || 0;
        vb = parseFloat(b.querySelector('.col-cf').textContent.replace(/[^\\d.-]/g,'')) || 0;
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

    # ふれんず (一棟マンション) — Fukuoka only
    ftakken_ittomono = DATA_DIR / "ftakken_ittomono_fukuoka_raw.txt"
    if ftakken_ittomono.exists():
        ft_rows = parse_data_file(ftakken_ittomono, "fukuoka")
        print(f"  ふれんず(一棟マンション): {len(ft_rows)}件")
        all_rows.extend(ft_rows)

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
