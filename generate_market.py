"""Unified Market page generator.

Structure: City tabs → within each city: 区分 / 一棟もの / 戸建て
Each property includes investment analysis (score breakdown, revenue calc).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from statistics import median as _stat_median

_PROJECT_ROOT = Path(__file__).resolve().parent
_LIB_PARENT = _PROJECT_ROOT.parent
for p in [str(_PROJECT_ROOT), str(_LIB_PARENT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generate_search_report_common import (
    ReportConfig,
    PropertyRow,
    _clean_station_text,
    dedupe_properties,
    load_first_seen,
    load_sold_urls,
    parse_data_file,
    score_row,
)
from generate_ittomono_report import (
    IttomonoRow,
    parse_data_file as ittomono_parse,
    score_row as ittomono_score_row,
    _filter_rows as ittomono_filter,
    _deduplicate_rows as ittomono_dedup,
)
from revenue_calc import analyze as revenue_analyze, InvestmentParams
from lib.renderer import create_env, PUBLIC_NAV
from lib.styles.design_tokens import get_base_css, get_css_tokens, get_google_fonts_url

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")

# Ad-copy name patterns that should be replaced with location-based fallback
_ADCOPY_RE = re.compile(
    r"^【[^】]+】|"       # 【満室稼働中】...
    r"^[▶▲■◆◇●★☆※◎]+|"  # ▶金町駅...
    r"^「[^」]+」"         # 「東武練馬」駅...
)

def _clean_adcopy_name(name: str, location: str, layout: str = "") -> str:
    """Clean property names: strip ad-copy suffixes, replace pure ad-copy with fallback."""
    if not name:
        return name
    name = name.replace("&nbsp;", " ").strip()

    # Step 1: Strip ad-copy suffixes from real building names
    # 【オーナーチェンジ】, （賃貸中）, etc.
    name = re.sub(r"[【\(（][^】\)）]*(?:オーナーチェンジ|賃貸中|OC|満室|投資用)[^】\)）]*[】\)）]", "", name).strip()
    # Trailing ！ phrases (e.g., "〜マンション！好立地！" → "〜マンション")
    name = re.sub(r"[！!][^！!]*$", "", name).strip()

    # Step 2: Detect pure ad-copy (no building name at all) → replace with fallback
    bldg_suffixes = ["マンション", "ハイツ", "コーポ", "レジデンス", "ビル", "荘",
                     "パレス", "テラス", "プラザ", "メゾン", "ガーデン", "パーク",
                     "ハウス", "ドーム", "タワー", "コート", "シャトー", "グラン",
                     "ステート", "ロイヤル", "エステート", "フォレスト", "シティ",
                     "アーバン", "ライオンズ", "アンピール", "ピュアドーム",
                     "ニック", "サン", "ロワール", "ペルル"]

    def _fallback():
        area_m = re.search(r"([\u4e00-\u9fff]{2,6}[区市町村])", location)
        area_label = area_m.group(1) if area_m else location[:6] if location else "物件"
        return f"{area_label} {layout}".strip() if layout else area_label

    # Starts with ad markers → always fallback
    if _ADCOPY_RE.match(name):
        return _fallback()
    # Has building suffix → keep (already cleaned of ad suffixes above)
    if any(s in name for s in bldg_suffixes):
        return name
    # Starts with 利回り/駅名/数字+% → ad-copy
    if re.match(r"^(利回り|表面利回|想定利回|\d+[\d.]*%)", name):
        return _fallback()
    # Station+walk pattern without building name (e.g., "八丁堀駅徒歩5分")
    if re.match(r"^.{1,10}駅.{0,5}(徒歩|バス).{0,5}$", name):
        return _fallback()
    # Long names with station keywords but no building suffix
    if len(name) > 20 and ("駅" in name or "徒歩" in name):
        return _fallback()
    # Descriptive sentence patterns (Japanese punctuation = not a building name)
    if "、" in name or "。" in name:
        return _fallback()
    # Ad-copy descriptive keywords without building suffix
    _ad_keywords = {"エリア", "立地", "好立地", "便利", "通勤", "アクセス", "おすすめ",
                    "注目", "人気", "希少", "必見", "新着", "限定", "即入居", "賃貸中"}
    if any(kw in name for kw in _ad_keywords):
        return _fallback()
    return name

# ---------------------------------------------------------------------------
# Property nav (SSoT for all property pages)
# ---------------------------------------------------------------------------
PROPERTY_PAGES = [
    {"href": "market.html", "label": "Market"},
    {"href": "simulate.html", "label": "Simulate"},
]

# Gnav: page-level navigation within property section (SSoT)
GNAV_PAGES = [
    {"href": "index.html", "label": "Hub"},
    {"href": "market.html", "label": "Market"},
    {"href": "naiken-analysis.html", "label": "内覧分析"},
    {"href": "inquiry-messages.html", "label": "問い合わせ"},
    {"href": "inquiry-pipeline.html", "label": "Pipeline"},
]

CITY_CONFIGS: list[dict] = [
    {
        "key": "osaka",
        "label": "大阪",
        "data_path": DATA_DIR / "suumo_osaka_raw.txt",
        "include_osaka_r": True,
    },
    {
        "key": "fukuoka",
        "label": "福岡",
        "data_path": DATA_DIR / "suumo_fukuoka_raw.txt",
        "include_osaka_r": False,
    },
    {
        "key": "tokyo",
        "label": "東京",
        "data_path": DATA_DIR / "suumo_tokyo_raw.txt",
        "include_osaka_r": False,
    },
]

_OC_KEYWORDS = [
    "オーナーチェンジ", "賃貸中", "利回り", "投資顧問", "投資物件",
    "家賃", "月額賃料", "年間収入", "年間賃料",
    "表面利回", "想定利回", "収益", "入居者付", "入居中",
    "賃借人", "テナント付", "現行賃料", "満室",
]

TIER_GREEN = 80
TIER_YELLOW = 65
MAX_YELLOW_FILL = 20
MAX_KUBUN_ITEMS = 25

# Budget tier: CF-focused investment (SEARCH_CRITERIA: 40㎡以上, 上位のみ)
BUDGET_TIER_MIN = 60
BUDGET_MAX_ITEMS = 15


# ---------------------------------------------------------------------------
# Extra data source discovery
# ---------------------------------------------------------------------------
def _find_extra_paths(city_key: str) -> list[Path]:
    paths = []
    for prefix in ["rakumachi", "yahoo", "athome", "cowcamo", "ftakken"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            paths.append(p)
    for prefix in ["restate", "lifull"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# Load 区分 (condominium units)
# ---------------------------------------------------------------------------
def _load_kubun(cfg: dict) -> list[PropertyRow]:
    data_path = cfg["data_path"]
    if not data_path.exists():
        return []

    rows = parse_data_file(data_path)
    for extra in _find_extra_paths(cfg["key"]):
        if extra.exists():
            rows.extend(parse_data_file(extra))

    if cfg.get("include_osaka_r"):
        try:
            from generate_search_report_common import parse_osaka_r_rows, OSAKA_R_ROWS
            rows.extend(parse_osaka_r_rows(OSAKA_R_ROWS))
        except ImportError:
            pass

    rows, _ = dedupe_properties(rows)

    sold = load_sold_urls()
    rows = [r for r in rows if r.url.rstrip("/") + "/" not in sold]

    def _is_oc(r: PropertyRow) -> bool:
        text = f"{r.name} {r.station_text} {r.minpaku_status} {r.location} {r.raw_line}"
        return any(kw in text for kw in _OC_KEYWORDS)

    rows = [r for r in rows if not _is_oc(r)]
    rows = [r for r in rows if r.pet_status != "不可" and "ペット不可" not in f"{r.pet_status} {r.name} {r.raw_line}" and "ペット飼育不可" not in f"{r.pet_status} {r.name} {r.raw_line}"]
    rows = [r for r in rows if "民泊禁止" not in f"{r.minpaku_status} {r.name} {r.raw_line}" and "民泊不可" not in f"{r.minpaku_status} {r.name} {r.raw_line}"]
    # Exclude wooden structures (木造は値段がつかない)
    rows = [r for r in rows if r.structure != "木造"]
    # 30㎡未満除外 (投資対象外)
    rows = [r for r in rows if r.area_sqm is None or r.area_sqm >= 30]

    config = ReportConfig(
        city_key=cfg["key"], city_label=cfg["label"],
        accent="#6366f1", accent_rgb="99,102,241",
        data_path=data_path, output_path=OUTPUT_DIR / "market.html",
        hero_conditions=[], search_condition_bullets=[], investor_notes=[],
    )
    for row in rows:
        score_row(row, config)

    rows = [r for r in rows if r.total_score >= TIER_YELLOW]
    rows.sort(key=lambda r: -r.total_score)

    green = [r for r in rows if r.total_score >= TIER_GREEN]
    yellow = [r for r in rows if TIER_YELLOW <= r.total_score < TIER_GREEN]
    if len(green) >= MAX_YELLOW_FILL:
        rows = green
    else:
        slots = MAX_YELLOW_FILL - len(green)
        rows = green + yellow[:slots]

    return rows[:MAX_KUBUN_ITEMS]


def _load_budget(city_key: str) -> list[PropertyRow]:
    """Load budget properties (≤1000万, OC included) — CF-focused investment."""
    p = DATA_DIR / f"ftakken_{city_key}_budget_raw.txt"
    if not p.exists():
        return []

    rows = parse_data_file(p)
    rows, _ = dedupe_properties(rows)

    sold = load_sold_urls()
    rows = [r for r in rows if r.url.rstrip("/") + "/" not in sold]

    # Budget tier: exclude 木造, 40㎡未満 (SEARCH_CRITERIA: 最低40㎡)
    rows = [r for r in rows if r.structure != "木造"]
    rows = [r for r in rows if r.area_sqm is not None and r.area_sqm >= 40]
    config = ReportConfig(
        city_key=city_key, city_label=city_key,
        accent="#6366f1", accent_rgb="99,102,241",
        data_path=p, output_path=OUTPUT_DIR / "market.html",
        hero_conditions=[], search_condition_bullets=[], investor_notes=[],
    )
    for row in rows:
        score_row(row, config)

    rows = [r for r in rows if r.total_score >= BUDGET_TIER_MIN]
    rows.sort(key=lambda r: -r.total_score)
    return rows[:BUDGET_MAX_ITEMS]


# ── Ward-level rent per sqm (円/㎡/月) ──
# Source: SUUMO/アットホーム/LIFULL 2025-2026年データ（1R/1K/1LDK中心）
_RENT_PER_SQM_BY_WARD: dict[str, dict[str, int]] = {
    "fukuoka": {
        "中央区": 3200,   # 天神・大名。市内最高賃料帯
        "博多区": 3000,   # 駅近需要強い
        "東区":   2600,   # 箱崎・千早
        "南区":   2400,   # 大橋・高宮
        "早良区": 2300,   # 西新・藤崎
        "西区":   2200,   # 姪浜方面
        "城南区": 2000,   # 市内最安帯
    },
    "osaka": {
        "中央区": 3400,   # 難波・心斎橋
        "西区":   3300,   # 堀江・新町
        "北区":   3200,   # 梅田
        "浪速区": 3100,   # なんば
        "福島区": 3000,   # 梅田近接
        "天王寺区": 2900, # 上本町
        "淀川区": 2800,   # 新大阪
        "都島区": 2800,   # 京橋
        "東淀川区": 2300, # 郊外
    },
    "tokyo": {
        "中央区": 3900,   # 日本橋・銀座
        "新宿区": 4000,   # ㎡単価最高帯
        "渋谷区": 4000,   # 高単身需要
        "港区":   3500,   # 超都心
        "豊島区": 3800,   # 池袋
        "品川区": 3600,   # 利便性◎
        "目黒区": 3100,   # 高級住宅地
        "文京区": 3200,   # 大学・病院
        "台東区": 3100,   # 上野
        "中野区": 3600,   # 需要安定
        "墨田区": 3700,   # 小面積物件多
        "板橋区": 3400,   # 再開発中
        "練馬区": 3100,   # 西部
        "北区":   3200,   # 赤羽
        "足立区": 3400,   # 利回り出やすい
        "葛飾区": 3400,   # 足立並み
    },
}

# City-level fallback (ward not found)
_ESTIMATED_RENT_PER_SQM: dict[str, int] = {
    "osaka": 2800,
    "fukuoka": 2400,
    "tokyo": 3200,
}


def _age_discount(built_year: int | None) -> float:
    """Rent discount factor for building age.

    Market data averages skew toward newer properties.
    Older buildings command lower rents — apply conservative discount.
    """
    if not built_year:
        return 0.80  # Unknown age → conservative
    age = CURRENT_YEAR - built_year
    if age <= 10:
        return 1.00
    if age <= 20:
        return 0.92
    if age <= 30:
        return 0.82
    if age <= 40:
        return 0.72
    return 0.65  # 40年超


CURRENT_YEAR = 2026  # for age calculation


def _get_rent_per_sqm(city_key: str, location: str, built_year: int | None = None) -> tuple[int, str]:
    """Get age-adjusted rent per sqm (円/㎡) and ward name.

    Returns (rent_per_sqm, ward_name). ward_name is "" if city fallback used.
    """
    import re as _re_local
    ward_match = _re_local.search(r'([^\s市県都府]+区)', location)
    ward = ward_match.group(1) if ward_match else ""
    ward_data = _RENT_PER_SQM_BY_WARD.get(city_key, {})
    if ward and ward in ward_data:
        base = ward_data[ward]
    else:
        base = _ESTIMATED_RENT_PER_SQM.get(city_key, 2800)
        ward = ""
    adjusted = int(base * _age_discount(built_year))
    return adjusted, ward


# ── Price Validity (適正価格判定) ──
# Cap rates by city — used for income approach fair value
# 区分マンション投資の実勢Cap Rate（居住用物件寄り、表面利回りより低め）
_CAP_RATES: dict[str, float] = {
    "fukuoka": 0.050,  # 5.0% — 地方都市（投資利回り5-7%帯）
    "osaka": 0.045,    # 4.5% — 準都心
    "tokyo": 0.035,    # 3.5% — 都心（低利回り・値上がり期待）
}


def _extract_ward(location: str) -> str:
    """Extract ward name (e.g. '博多区') from location string."""
    m = re.search(r'([^\s市県都府]+区)', location)
    return m.group(1) if m else ""


def _build_sqm_benchmarks(rows: list, city_key: str) -> dict[str, dict]:
    """Build ㎡単価 benchmarks by ward from property rows.

    Returns: {ward: {median, count}, "_city": {median, count}}
    """
    ward_prices: dict[str, list[float]] = {}
    all_prices: list[float] = []

    for row in rows:
        price = getattr(row, "price_man", 0) or 0
        area = getattr(row, "area_sqm", 0) or 0
        if price <= 0 or area <= 0:
            continue
        sqm = price / area  # 万円/㎡
        loc = getattr(row, "location", "")
        ward = _extract_ward(loc)
        if ward:
            ward_prices.setdefault(ward, []).append(sqm)
        all_prices.append(sqm)

    result: dict[str, dict] = {}
    for ward, prices in ward_prices.items():
        if len(prices) >= 3:
            result[ward] = {"median": _stat_median(prices), "count": len(prices)}
    if all_prices:
        result["_city"] = {"median": _stat_median(all_prices), "count": len(all_prices)}
    return result


def _compute_price_validity(
    price_man: int,
    area_sqm: float,
    monthly_rent_yen: float,
    city_key: str,
    ward: str,
    sqm_benchmarks: dict[str, dict],
    maintenance_fee: int = 0,
) -> dict | None:
    """Compute price validity: income approach + comparable sales.

    Returns dict with: fair_price_man, deviation_pct, label, color,
                       income_fair, comp_fair, comp_source, cap_rate
    """
    if price_man <= 0 or area_sqm <= 0 or monthly_rent_yen <= 0:
        return None

    # Income approach: NOI / Cap Rate
    cap_rate = _CAP_RATES.get(city_key, 0.055)
    annual_rent = monthly_rent_yen * 12
    opex = maintenance_fee * 12 + annual_rent * 0.08
    noi = annual_rent * (1 - 0.07) - opex  # vacancy 7%
    if noi <= 0:
        return None
    income_fair_man = round(noi / cap_rate / 10000)

    # Comparable sales: median ㎡単価 × area
    bench = sqm_benchmarks.get(ward) or sqm_benchmarks.get("_city")
    comp_fair_man = None
    comp_source = ""
    if bench:
        comp_fair_man = round(bench["median"] * area_sqm)
        comp_source = ward if ward in sqm_benchmarks else "市全体"

    # Weighted average (comp 60% + income 40% — comparable sales more reliable for 区分)
    if comp_fair_man and comp_fair_man > 0:
        fair_price = comp_fair_man * 0.6 + income_fair_man * 0.4
    else:
        fair_price = income_fair_man

    if fair_price <= 0:
        return None

    deviation = (price_man - fair_price) / fair_price * 100

    # Thresholds: 不動産は売り出し価格が適正価格+10-20%が標準
    if deviation < -20:
        label, color_key = "割安", "green"
    elif deviation <= 10:
        label, color_key = "適正", "accent"
    elif deviation <= 30:
        label, color_key = "やや割高", "yellow"
    else:
        label, color_key = "割高", "red"

    return {
        "fair_price_man": round(fair_price),
        "deviation_pct": round(deviation, 1),
        "label": label,
        "color": color_key,
        "income_fair": income_fair_man,
        "comp_fair": comp_fair_man,
        "comp_source": comp_source,
        "cap_rate": cap_rate * 100,
    }


def _is_oc_row(row: PropertyRow) -> bool:
    """Check if a property row is owner-change (OC)."""
    text = f"{row.name} {row.station_text} {row.minpaku_status} {row.location} {row.raw_line}"
    return any(kw in text for kw in _OC_KEYWORDS)


import re as _re

_CONFIRMED_OC_KEYWORDS = [
    "賃貸中", "オーナーチェンジ", "入居者付", "入居中",
    "月額賃料", "年間収入", "年間賃料", "年間予定収入",
]


def _is_confirmed_oc(row: PropertyRow) -> bool:
    """Strictly check if property has confirmed tenant (actual rent available).

    Unlike _is_oc_row (broad filter for kubun section), this only returns True
    when there is strong evidence of an existing tenant. "利回り" alone is NOT enough.
    Checks: pet field "OC" marker (from yield scraper) + keyword search in all text fields.
    """
    # Yield scraper stores OC flag in pet column
    if getattr(row, "pet_status", "") == "OC":
        return True
    text = f"{row.name} {row.station_text} {row.minpaku_status} {row.location} {row.raw_line}"
    return any(kw in text for kw in _CONFIRMED_OC_KEYWORDS)


def _extract_oc_rent(row: PropertyRow) -> tuple[float, float]:
    """Extract actual annual income (万円) and yield (%) from OC conditions.

    Returns (annual_income_man, yield_pct) or (0, 0) if not found.
    """
    text = row.raw_line
    annual_man = 0.0
    yield_pct = 0.0
    # Pattern 1: explicit annual income (円 or 万円)
    m_rent = _re.search(r'年間(?:予定)?収入[：:]?\s*([\d,.]+)万円', text)
    if m_rent:
        annual_man = float(m_rent.group(1).replace(',', ''))
    if annual_man == 0:
        m_rent2 = _re.search(r'年間(?:予定)?収入[：:]?\s*(\d[\d,]+)円', text)
        if m_rent2:
            annual_man = float(m_rent2.group(1).replace(',', '')) / 10000
    # Pattern 2: explicit yield
    m_yield = _re.search(r'年利回り[：:]?\s*([\d.]+)%', text)
    if m_yield:
        yield_pct = float(m_yield.group(1))
    # Pattern 3: yield from listing title (e.g., "利回り9.93%")
    if yield_pct == 0:
        m_yield2 = _re.search(r'利回り\s*([\d.]+)\s*[%％]', text)
        if m_yield2:
            yv = float(m_yield2.group(1))
            if 1.0 <= yv <= 30.0:
                yield_pct = yv
    # Derive annual income from price × yield if not explicitly stated
    if annual_man == 0 and yield_pct > 0 and row.price_man > 0:
        annual_man = row.price_man * yield_pct / 100  # 万円
    return (annual_man, yield_pct)


def _kubun_to_dict(row: PropertyRow, first_seen: dict, city_key: str = "", sqm_benchmarks: dict | None = None) -> dict:
    d = asdict(row)
    d["prop_type"] = "kubun"
    d["name"] = _clean_adcopy_name(d["name"], d.get("location", ""), d.get("layout", ""))
    d["is_oc"] = _is_confirmed_oc(row)
    fs = first_seen.get(row.url, "")
    d["first_seen"] = fs[5:] if fs and len(fs) >= 10 else fs  # MM-DD only
    if fs:
        from datetime import datetime
        try:
            fs_date = datetime.strptime(fs[:10], "%Y-%m-%d")
            d["is_new"] = (datetime.now() - fs_date).days <= 3
        except (ValueError, TypeError):
            d["is_new"] = False
    else:
        d["is_new"] = False
    # Walk minutes
    d["walk_min_text"] = f"{int(row.walk_min)}分" if getattr(row, "walk_min", None) else "—"
    # Price per sqm
    if row.price_man > 0 and getattr(row, "area_sqm", None) and row.area_sqm > 0:
        ppsm = row.price_man * 10000 / row.area_sqm
        ppsm_man = ppsm / 10000
        if ppsm_man >= 100:
            d["price_per_sqm"] = f"{ppsm_man:.0f}万/㎡"
        else:
            d["price_per_sqm"] = f"{ppsm_man:.1f}万/㎡"
    else:
        d["price_per_sqm"] = "—"

    # Format maintenance fee as total yen
    if row.maintenance_fee > 0:
        d["maintenance_fee_text"] = f"{row.maintenance_fee:,}円"
    else:
        d["maintenance_fee_text"] = ""

    # Revenue analysis for kubun
    # Always compute market rent (age-adjusted ward-level estimate).
    # For OC: also extract actual rent. Display both for comparison.
    d["revenue"] = None
    d["est_monthly_rent"] = ""  # used for CF calculation (actual > market)
    d["rent_source"] = ""
    d["actual_rent"] = ""       # OC actual rent (blank for non-OC)
    d["market_rent"] = ""       # ward-level age-adjusted estimate
    d["market_rent_label"] = "" # e.g. "相場博多区"
    d["rent_gap_pct"] = ""      # deviation: (actual - market) / market
    d["rent_per_sqm"] = 0
    d["price_validity"] = None
    _monthly_rent_yen = 0  # track for price validity
    _ward_for_validity = ""
    if row.price_man > 0 and getattr(row, "area_sqm", None) and row.area_sqm > 0:
        # Always compute market rent (age-adjusted)
        mkt_per_sqm, ward = _get_rent_per_sqm(city_key, row.location, row.built_year)
        mkt_monthly = mkt_per_sqm * row.area_sqm  # 円
        mkt_annual = mkt_monthly * 12 / 10000  # 万円
        d["rent_per_sqm"] = mkt_per_sqm
        d["market_rent"] = f"{mkt_monthly / 10000:.1f}万" if mkt_monthly >= 10000 else f"{int(mkt_monthly):,}円"
        d["market_rent_label"] = ward if ward else ""

        # OC: extract actual rent
        oc_annual_man, oc_yield = _extract_oc_rent(row) if d["is_oc"] else (0, 0)
        if oc_annual_man > 0:
            actual_monthly = oc_annual_man * 10000 / 12  # 円
            d["actual_rent"] = f"{actual_monthly / 10000:.1f}万" if actual_monthly >= 10000 else f"{int(actual_monthly):,}円"
            # Deviation: how much actual differs from market
            if mkt_monthly > 0:
                gap = (actual_monthly - mkt_monthly) / mkt_monthly * 100
                d["rent_gap_pct"] = f"{gap:+.0f}%"
            # Use actual rent for CF (more reliable)
            monthly_rent = actual_monthly
            annual_rent = oc_annual_man
            est_yield = oc_yield if oc_yield > 0 else (annual_rent / row.price_man) * 100
            d["rent_source"] = "実家賃"
            d["est_monthly_rent"] = d["actual_rent"]
        else:
            # Non-OC: use market estimate for CF
            monthly_rent = mkt_monthly
            annual_rent = mkt_annual
            est_yield = (annual_rent / row.price_man) * 100
            d["rent_source"] = f"相場{d['market_rent_label']}" if d["market_rent_label"] else "相場"
            d["est_monthly_rent"] = d["market_rent"]

        d["yield_text"] = f"{est_yield:.1f}%"
        _monthly_rent_yen = monthly_rent  # capture for price validity
        _ward_for_validity = ward
        structure_for_calc = row.structure or "RC造"
        # 融資年数: 60 - 築年数（フロア15年・上限35年 — 澤畠さん筑波銀行）
        try:
            ra = revenue_analyze(
                price_man=row.price_man,
                yield_pct=est_yield,
                structure=structure_for_calc,
                built_year=row.built_year,
                units_count=1,
                area_sqm=row.area_sqm,
                maintenance_fee_monthly=row.maintenance_fee or 0,
            )
            rev = {
                "noi": round(ra.noi, 1),
                "net_yield": round(ra.net_yield_pct, 2),
                "monthly_cf": round(ra.monthly_cf, 1),
                "after_tax_monthly_cf": round(ra.after_tax_cf / 12, 1),
                "ccr": round(ra.ccr_pct, 1),
                "payback_years": round(ra.payback_years, 1) if ra.payback_years != float("inf") else None,
                "depreciation_annual": round(ra.depreciation_annual, 1),
                "tax_benefit": round(ra.tax_benefit, 1),
                "verdict": ra.verdict,
                "down_payment": round(ra.down_payment, 1),
                "acquisition_cost": round(ra.acquisition_cost, 1),
                "total_equity": round(ra.total_equity, 1),
                "loan_amount": round(ra.loan_amount, 1),
                "loan_years": ra.loan_years,
                "loan_rate": ra.params.loan_rate_annual * 100,
                "annual_debt_service": round(ra.annual_debt_service, 1),
                "est_monthly_rent": d["est_monthly_rent"],
                "rent_source": d["rent_source"],
                "rent_per_sqm": mkt_per_sqm,
                "structure_used": structure_for_calc,
            }
            # 固定融資シナリオ: CF(15年) と CF(20年)
            for scenario_years in (15, 20):
                ra_s = revenue_analyze(
                    price_man=row.price_man, yield_pct=est_yield,
                    structure=structure_for_calc, built_year=row.built_year,
                    units_count=1, area_sqm=row.area_sqm,
                    maintenance_fee_monthly=row.maintenance_fee or 0,
                    params=InvestmentParams(loan_years=scenario_years),
                )
                rev[f"cf_{scenario_years}y"] = round(ra_s.after_tax_cf / 12, 1)
            # 現金購入比較（200万以下）
            if row.price_man <= 200:
                ra_cash = revenue_analyze(
                    price_man=row.price_man, yield_pct=est_yield,
                    structure=structure_for_calc, built_year=row.built_year,
                    units_count=1, area_sqm=row.area_sqm,
                    maintenance_fee_monthly=row.maintenance_fee or 0,
                    params=InvestmentParams(down_payment_ratio=1.0),
                )
                rev["cash_cf"] = round(ra_cash.after_tax_cf / 12, 1)
                rev["cash_equity"] = round(ra_cash.total_equity, 1)
                rev["cash_ccr"] = round(ra_cash.ccr_pct, 1)
            d["revenue"] = rev
        except Exception:
            pass

    # Price validity (適正価格判定)
    if _monthly_rent_yen > 0 and sqm_benchmarks:
        d["price_validity"] = _compute_price_validity(
            price_man=row.price_man,
            area_sqm=row.area_sqm,
            monthly_rent_yen=_monthly_rent_yen,
            city_key=city_key,
            ward=_ward_for_validity,
            sqm_benchmarks=sqm_benchmarks,
            maintenance_fee=row.maintenance_fee or 0,
        )

    return d


# ---------------------------------------------------------------------------
# Load 一棟もの (whole buildings)
# ---------------------------------------------------------------------------
def _load_ittomono_by_city(city_key: str) -> list[IttomonoRow]:
    rows: list[IttomonoRow] = []
    for prefix in ["ittomono", "rakumachi_ittomono", "ftakken_ittomono", "yield_ittomono"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            rows.extend(ittomono_parse(p, city_key))
    return rows


def _ittomono_to_dict(row: IttomonoRow, city_key: str = "fukuoka", first_seen: dict | None = None) -> dict:
    d = asdict(row)
    d["name"] = _clean_adcopy_name(d["name"], d.get("location", ""))
    d["prop_type"] = "ittomono"
    d["maintenance_fee_text"] = ""
    d["pet_status"] = ""
    d["minpaku_status"] = ""
    # Freshness (first_seen)
    fs_date = ""
    is_new = False
    if first_seen and row.url:
        fs_date = first_seen.get(row.url, "")
    if fs_date:
        import datetime as _dt
        try:
            fs_d = _dt.date.fromisoformat(fs_date)
            age_days = (_dt.date.today() - fs_d).days
            is_new = age_days <= 7
        except Exception:
            pass
    d["first_seen"] = fs_date[5:] if fs_date and len(fs_date) >= 10 else fs_date  # MM-DD only
    d["is_new"] = is_new

    # Clean station text (remove route names)
    d["station_text"] = _clean_station_text(row.station_text)

    if row.yield_pct:
        d["yield_text"] = f"{row.yield_pct:.1f}%"

    # Walk minutes
    d["walk_min_text"] = f"{int(row.walk_min)}分" if getattr(row, "walk_min", None) else "—"
    # Price per sqm
    if row.price_man and row.price_man > 0 and getattr(row, "area_sqm", None) and row.area_sqm > 0:
        ppsm = row.price_man * 10000 / row.area_sqm
        ppsm_man = ppsm / 10000
        if ppsm_man >= 100:
            d["price_per_sqm"] = f"{ppsm_man:.0f}万/㎡"
        else:
            d["price_per_sqm"] = f"{ppsm_man:.1f}万/㎡"
    else:
        d["price_per_sqm"] = "—"

    # Estimated monthly rent (ward-level, age-adjusted)
    d["est_monthly_rent"] = ""
    d["rent_source"] = "想定家賃"
    d["market_rent"] = ""
    d["market_rent_label"] = ""
    d["actual_rent"] = ""
    d["rent_gap_pct"] = ""
    d["is_oc"] = False
    area = row.area_sqm or 0
    if row.price_man and row.price_man > 0 and area > 0:
        rent_per_sqm, ward = _get_rent_per_sqm(city_key, row.location, row.built_year)
        monthly_rent = rent_per_sqm * area
        d["est_monthly_rent"] = f"{monthly_rent / 10000:.1f}万" if monthly_rent >= 10000 else f"{int(monthly_rent):,}円"
        d["rent_source"] = f"相場{ward}" if ward else "想定家賃"
        d["market_rent"] = d["est_monthly_rent"]
        d["market_rent_label"] = ward if ward else ""
        d["rent_per_sqm"] = rent_per_sqm

    # Revenue analysis — estimate yield from area if missing
    yield_pct = row.yield_pct
    if (not yield_pct or yield_pct <= 0) and row.price_man and row.price_man > 0:
        units = row.units_count or 1
        if area > 0:
            rent_per_sqm, _ = _get_rent_per_sqm(city_key, row.location, row.built_year)
            annual_rent = rent_per_sqm * area * 12 / 10000  # 万円
            yield_pct = (annual_rent / row.price_man) * 100
            d["yield_text"] = f"≈{yield_pct:.1f}%"
    if row.price_man and yield_pct and row.price_man > 0 and yield_pct > 0:
        try:
            ra = revenue_analyze(
                price_man=row.price_man,
                yield_pct=yield_pct,
                structure=row.structure or "RC造",
                built_year=row.built_year,
                units_count=row.units_count or 0,
                area_sqm=row.area_sqm,
            )
            rev_dict = {
                "noi": round(ra.noi, 1),
                "net_yield": round(ra.net_yield_pct, 2),
                "monthly_cf": round(ra.monthly_cf, 1),
                "after_tax_monthly_cf": round(ra.after_tax_cf / 12, 1),
                "ccr": round(ra.ccr_pct, 1),
                "payback_years": round(ra.payback_years, 1) if ra.payback_years != float("inf") else None,
                "depreciation_annual": round(ra.depreciation_annual, 1),
                "tax_benefit": round(ra.tax_benefit, 1),
                "verdict": ra.verdict,
                "down_payment": round(ra.down_payment, 1),
                "acquisition_cost": round(ra.acquisition_cost, 1),
                "total_equity": round(ra.total_equity, 1),
                "loan_amount": round(ra.loan_amount, 1),
                "loan_years": ra.loan_years,
                "loan_rate": ra.params.loan_rate_annual * 100,
                "annual_debt_service": round(ra.annual_debt_service, 1),
                "est_monthly_rent": d["est_monthly_rent"],
                "rent_source": d["rent_source"],
                "structure_used": row.structure or "RC造",
            }
            # 固定融資シナリオ: CF(15年) と CF(20年)
            for scenario_years in (15, 20):
                ra_s = revenue_analyze(
                    price_man=row.price_man, yield_pct=yield_pct,
                    structure=row.structure or "RC造", built_year=row.built_year,
                    units_count=row.units_count or 0, area_sqm=row.area_sqm,
                    params=InvestmentParams(loan_years=scenario_years),
                )
                rev_dict[f"cf_{scenario_years}y"] = round(ra_s.after_tax_cf / 12, 1)
            d["revenue"] = rev_dict
        except Exception:
            d["revenue"] = None
    else:
        d["revenue"] = None

    return d


# ---------------------------------------------------------------------------
# Load 戸建て (detached houses)
# ---------------------------------------------------------------------------
def _load_kodate_by_city(city_key: str) -> list[IttomonoRow]:
    """Load kodate data — uses ittomono parser since format is similar."""
    rows: list[IttomonoRow] = []
    for prefix in ["ftakken_kodate", "rakumachi_kodate"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            rows.extend(ittomono_parse(p, city_key))
    return rows


def _kodate_to_dict(row: IttomonoRow, city_key: str = "fukuoka", first_seen: dict | None = None) -> dict:
    d = _ittomono_to_dict(row, city_key=city_key, first_seen=first_seen)
    d["prop_type"] = "kodate"
    return d


# ---------------------------------------------------------------------------
# Patrol summary
# ---------------------------------------------------------------------------
def _load_patrol_summary() -> dict | None:
    p = DATA_DIR / "patrol_summary.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Pipeline auto-flag: 収益物件の上位をinquiries.yamlへ自動注入
# ---------------------------------------------------------------------------
def _pipeline_auto_flag(cities: list[dict]) -> None:
    """Flag top profitable properties into the pipeline (CF+ & CCR high)."""
    try:
        import yaml as _yaml
        from pathlib import Path as _Path
        from datetime import date as _date

        inq_path = _Path("data/inquiries.yaml")
        if not inq_path.exists():
            return
        raw = _yaml.safe_load(inq_path.read_text(encoding="utf-8"))
        inquiries = raw.get("inquiries", []) if isinstance(raw, dict) else raw
        existing_urls = {inq.get("url", "").rstrip("/") for inq in inquiries}

        # Next ID
        max_id = 0
        for inq in inquiries:
            try:
                max_id = max(max_id, int(inq.get("id", "inq-0").split("-")[-1]))
            except (ValueError, IndexError):
                pass

        new_flagged = []
        for city_data in cities:
            for prop in city_data.get("profitable", {}).get("properties", []):
                url = prop.get("url", "").rstrip("/")
                if not url or url in existing_urls:
                    continue
                rev = prop.get("revenue", {})
                if not rev:
                    continue
                ccr = rev.get("ccr", 0)
                cf = rev.get("after_tax_monthly_cf", 0)
                if cf <= 0 or ccr < 5.0:
                    continue

                max_id += 1
                entry = {
                    "id": f"inq-{max_id:03d}",
                    "name": prop.get("name", ""),
                    "url": prop.get("url", ""),
                    "source": prop.get("source", ""),
                    "city": city_data.get("key", ""),
                    "score": prop.get("total_score", 0),
                    "status": "flagged",
                    "price": prop.get("price_man", 0),
                    "area": prop.get("area_sqm", 0),
                    "layout": prop.get("layout", ""),
                    "station": prop.get("station_text", prop.get("location", "")),
                    "year_built": prop.get("built_year"),
                    "pet": prop.get("pet_status") or "unknown",
                    "short_term": None,
                    "management_fee": prop.get("maintenance_fee", 0),
                    "agent": None,
                    "thread_id": None,
                    "viewing_date": None,
                    "decision": None,
                    "notes": f"自動フラグ: CF {cf:.1f}万/月, CCR {ccr:.1f}%",
                    "created": str(_date.today()),
                    "updated": str(_date.today()),
                }
                new_flagged.append(entry)
                existing_urls.add(url)

        if new_flagged:
            inquiries.extend(new_flagged)
            if isinstance(raw, dict):
                raw["inquiries"] = inquiries
            else:
                raw = inquiries
            inq_path.write_text(
                _yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            print(f"  → Pipeline: {len(new_flagged)}件を自動フラグ (CF+/CCR≥5%)")
            for e in new_flagged[:5]:
                print(f"    {e['id']} {e['name']} CCR={e['notes'].split('CCR ')[-1]}")
        else:
            print("  → Pipeline: 新規フラグ対象なし")
    except Exception as e:
        print(f"  → Pipeline auto-flag error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Generating unified Market page ===")

    first_seen = load_first_seen()

    # Backfill: register new URLs in first_seen.json
    import datetime as _dt
    _today_iso = _dt.date.today().isoformat()
    _backfilled = 0

    # Collect all ittomono/kodate for global filtering
    all_ittomono: list[IttomonoRow] = []
    all_kodate: list[IttomonoRow] = []
    for cfg in CITY_CONFIGS:
        all_ittomono.extend(_load_ittomono_by_city(cfg["key"]))
        all_kodate.extend(_load_kodate_by_city(cfg["key"]))

    # Backfill first_seen for ittomono/kodate URLs
    for r in all_ittomono:
        if r.url and r.url not in first_seen:
            first_seen[r.url] = _today_iso
            _backfilled += 1
    for r in all_kodate:
        if r.url and r.url not in first_seen:
            first_seen[r.url] = _today_iso
            _backfilled += 1
    if _backfilled:
        _fs_path = Path("data") / "first_seen.json"
        _fs_path.write_text(json.dumps(first_seen, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  first_seen.json: {_backfilled}件バックフィル")

    # Filter & dedup ittomono globally
    if all_ittomono:
        all_ittomono = ittomono_filter(all_ittomono)
        all_ittomono = ittomono_dedup(all_ittomono)
        for row in all_ittomono:
            ittomono_score_row(row)
        all_ittomono = [r for r in all_ittomono if r.total_score >= 40]
        all_ittomono.sort(key=lambda r: -r.total_score)

    # Filter & dedup kodate globally (lighter scoring, skip units filter)
    if all_kodate:
        all_kodate = ittomono_dedup(all_kodate)
        for row in all_kodate:
            ittomono_score_row(row)
        all_kodate = [r for r in all_kodate if r.total_score >= 20]
        all_kodate.sort(key=lambda r: -r.total_score)

    # Build city data
    cities = []
    total_kubun = 0
    total_ittomono = 0
    total_kodate = 0
    total_budget = 0
    all_prices = []
    all_areas = []
    pet_ok = 0

    for cfg in CITY_CONFIGS:
        # 区分
        kubun_rows = _load_kubun(cfg)
        # Build ㎡単価 benchmarks per segment (budget/yield vs kubun have different price bands)
        budget_rows = _load_budget(cfg["key"])
        kubun_benchmarks = _build_sqm_benchmarks(kubun_rows, cfg["key"])
        budget_benchmarks = _build_sqm_benchmarks(budget_rows, cfg["key"]) if budget_rows else kubun_benchmarks
        kubun_props = [_kubun_to_dict(r, first_seen, city_key=cfg["key"], sqm_benchmarks=kubun_benchmarks) for r in kubun_rows]

        # 一棟もの (city subset)
        city_ittomono = [r for r in all_ittomono if r.city_key == cfg["key"]]
        ittomono_props = [_ittomono_to_dict(r, city_key=cfg["key"], first_seen=first_seen) for r in city_ittomono[:15]]

        # 戸建て (city subset)
        city_kodate = [r for r in all_kodate if r.city_key == cfg["key"]]
        kodate_props = [_kodate_to_dict(r, city_key=cfg["key"], first_seen=first_seen) for r in city_kodate[:10]]

        # 格安区分 (budget tier — Fukuoka only)
        budget_props = [_kubun_to_dict(r, first_seen, city_key=cfg["key"], sqm_benchmarks=budget_benchmarks) for r in budget_rows]
        # Budget tier: CF赤字もOC実家賃データとして価値があるため、フィルタなし

        city_total = len(kubun_props) + len(ittomono_props) + len(kodate_props) + len(budget_props)

        cities.append({
            "key": cfg["key"],
            "label": cfg["label"],
            "count": city_total,
            "kubun": {"count": len(kubun_props), "properties": kubun_props},
            "ittomono": {"count": len(ittomono_props), "properties": ittomono_props},
            "kodate": {"count": len(kodate_props), "properties": kodate_props},
            "budget": {"count": len(budget_props), "properties": budget_props},
            "_sqm_benchmarks_kubun": kubun_benchmarks,
            "_sqm_benchmarks_budget": budget_benchmarks,
        })

        total_kubun += len(kubun_props)
        total_ittomono += len(ittomono_props)
        total_kodate += len(kodate_props)
        total_budget += len(budget_props)
        all_prices.extend(r.price_man for r in kubun_rows if r.price_man > 0)
        all_areas.extend(r.area_sqm for r in kubun_rows if r.area_sqm)
        pet_ok += sum(1 for r in kubun_rows if r.pet_status in ("可", "相談可"))

        budget_str = f" + 格安{len(budget_props)}" if budget_props else ""
        print(f"  {cfg['label']}: 区分{len(kubun_props)} + 一棟{len(ittomono_props)} + 戸建{len(kodate_props)}{budget_str}")

    # ── 収益物件: 各都市パネル内にCF > 0物件を種別横断で追加 ──
    total_profitable = 0
    for city_data in cities:
        profitable = []
        # Existing sections → profitable candidates
        # kodate excluded: market rent estimate uses apartment ㎡ rates → unreliable for houses
        for section_key in ["kubun", "ittomono", "budget"]:
            for prop in city_data[section_key]["properties"]:
                rev = prop.get("revenue")
                # CF >= 1.0万 OR CCR >= 8%（低価格物件はCF絶対額が小さいためCCRで救済）
                cf_ok = rev and rev.get("after_tax_monthly_cf") is not None and (rev["after_tax_monthly_cf"] >= 1.0 or rev.get("ccr", 0) >= 8.0)
                if cf_ok and rev.get("total_equity", float("inf")) < 1000:
                    prop_copy = dict(prop)
                    type_labels = {"kubun": "区分", "ittomono": "一棟", "kodate": "戸建", "budget": "格安区分"}
                    prop_copy["_type_label"] = type_labels.get(section_key, section_key)
                    profitable.append(prop_copy)

        # ── Yield-focused kubun (OC included, no pet filter) → profitable直接注入 ──
        yield_p = DATA_DIR / f"yield_{city_data['key']}_raw.txt"
        if yield_p.exists():
            yield_rows = parse_data_file(yield_p)
            yield_rows, _ = dedupe_properties(yield_rows)
            sold = load_sold_urls()
            yield_rows = [r for r in yield_rows if r.url.rstrip("/") + "/" not in sold]
            yield_rows = [r for r in yield_rows if r.area_sqm is None or r.area_sqm >= 15]
            # Exclude URLs already in other sections (avoid double-counting)
            existing_urls = set()
            for sk in ["kubun", "ittomono", "kodate", "budget"]:
                for p in city_data[sk]["properties"]:
                    existing_urls.add(p.get("url", ""))
            yield_rows = [r for r in yield_rows if r.url not in existing_urls]
            # Score and filter
            config = ReportConfig(
                city_key=city_data["key"], city_label=city_data["label"],
                accent="#6366f1", accent_rgb="99,102,241",
                data_path=yield_p, output_path=OUTPUT_DIR / "market.html",
                hero_conditions=[], search_condition_bullets=[], investor_notes=[],
            )
            for row in yield_rows:
                score_row(row, config)
            # 収益物件は居住スコアではなくCF/CCRで評価。スコア閾値を緩和（駅遠OC物件の救済）
            yield_rows = [r for r in yield_rows if r.total_score >= 20]
            # Build yield-specific benchmarks (cheap OC properties != kubun)
            _yield_bench = _build_sqm_benchmarks(yield_rows, city_data["key"])
            _city_bench = _yield_bench if _yield_bench.get("_city") else city_data.get("_sqm_benchmarks_budget", {})
            for row in yield_rows:
                d = _kubun_to_dict(row, first_seen, city_key=city_data["key"], sqm_benchmarks=_city_bench)
                rev = d.get("revenue")
                # CF >= 1.0万 OR CCR >= 8%（低価格物件はCF絶対額が小さいためCCRで救済）
                cf_ok = rev and rev.get("after_tax_monthly_cf") is not None and (rev["after_tax_monthly_cf"] >= 1.0 or rev.get("ccr", 0) >= 8.0)
                if cf_ok and rev.get("total_equity", float("inf")) < 1000:
                    d["_type_label"] = "利回り区分"
                    profitable.append(d)

        # Filter: 手出しが大きいのにCF薄利は除外（CCR < 5% AND 手出し > 200万）
        profitable = [p for p in profitable
                      if p.get("revenue", {}).get("ccr", 0) >= 5.0
                      or p.get("revenue", {}).get("total_equity", 0) <= 200]

        # Cross-source dedup: same location+area across different sources = same property
        import re as _re_dedup
        seen_loc_area: dict[str, int] = {}
        deduped: list[dict] = []
        for p in profitable:
            loc_raw = p.get("location", "")
            # Strip prefecture prefix then numbers/address details → ward+town only
            loc_raw = _re_dedup.sub(r"^(東京都|大阪府|京都府|北海道|.{2,3}県)", "", loc_raw)
            loc_raw = loc_raw.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
            loc = _re_dedup.sub(r"[\s　\d丁目番地号−\-]", "", loc_raw)[:10]
            area_int = str(int(p["area_sqm"])) if p.get("area_sqm") else ""
            key = f"{loc}|{area_int}" if loc and area_int else None
            if key and key in seen_loc_area:
                # Keep the one with higher CCR
                existing = deduped[seen_loc_area[key]]
                # print(f"    [DEDUP] {p.get('name','')} ≈ {existing.get('name','')} (key={key})")
                if p.get("revenue", {}).get("ccr", 0) > existing.get("revenue", {}).get("ccr", 0):
                    deduped[seen_loc_area[key]] = p
                continue
            idx = len(deduped)
            deduped.append(p)
            if key:
                seen_loc_area[key] = idx
        profitable = [p for p in deduped if p is not None]

        profitable.sort(key=lambda p: p.get("revenue", {}).get("ccr", 0), reverse=True)
        city_data["profitable"] = {"count": len(profitable), "properties": profitable}
        city_data["count"] += len(profitable)
        total_profitable += len(profitable)
    print(f"  収益物件: {total_profitable}件 (CF > 0)")

    # ── 収益物件 → Pipeline 自動フラグ（CCR上位をinquiries.yamlに注入） ──
    _pipeline_auto_flag(cities)

    # Totals
    total_count = total_kubun + total_ittomono + total_kodate + total_budget
    avg_price = int(sum(all_prices) / len(all_prices)) if all_prices else 0

    totals = {
        "count": total_count,
        "kubun_count": total_kubun,
        "ittomono_count": total_ittomono,
        "kodate_count": total_kodate,
        "budget_count": total_budget,
        "avg_price": avg_price,
        "pet_ok_count": pet_ok,
    }

    patrol_summary = _load_patrol_summary()

    # Render
    env = create_env(
        extra_dirs=[_PROJECT_ROOT / "lib" / "templates"],
        scope="public",
    )

    template = env.get_template("pages/market.html")
    html = template.render(
        cities=cities,
        totals=totals,
        patrol_summary=patrol_summary,
        property_pages=PROPERTY_PAGES,
        property_current="Market",
        gnav_pages=GNAV_PAGES,
        gnav_current="Market",
        nav_items=PUBLIC_NAV,
        current_page="Property",
        css_tokens=get_css_tokens(),
        base_css=get_base_css(),
        google_fonts_url=get_google_fonts_url(),
    )

    out = OUTPUT_DIR / "market.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Generated: {out} ({len(html) // 1024}KB)")

    # --- QA gate (warn-only; deploy step should call qa_market.py --strict) ---
    try:
        from qa_market import run_qa
        run_qa(out, strict=False)
    except Exception as _qa_err:
        print(f"[QA] skipped ({_qa_err})")

    return out


if __name__ == "__main__":
    main()
