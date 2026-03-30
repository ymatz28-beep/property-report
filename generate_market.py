"""Unified Market page generator.

Structure: City tabs → within each city: 区分 / 一棟もの / 戸建て
Each property includes investment analysis (score breakdown, revenue calc).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

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
from revenue_calc import analyze as revenue_analyze
from lib.renderer import create_env, PUBLIC_NAV
from lib.styles.design_tokens import get_base_css, get_css_tokens, get_google_fonts_url

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")

# ---------------------------------------------------------------------------
# Property nav (SSoT for all property pages)
# ---------------------------------------------------------------------------
PROPERTY_PAGES = [
    {"href": "market.html", "label": "Market"},
    {"href": "pipeline.html", "label": "Pipeline"},
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

    return rows


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


def _is_oc_row(row: PropertyRow) -> bool:
    """Check if a property row is owner-change (OC)."""
    text = f"{row.name} {row.station_text} {row.minpaku_status} {row.location} {row.raw_line}"
    return any(kw in text for kw in _OC_KEYWORDS)


import re as _re

def _extract_oc_rent(row: PropertyRow) -> tuple[float, float]:
    """Extract actual annual income (万円) and yield (%) from OC conditions.

    Returns (annual_income_man, yield_pct) or (0, 0) if not found.
    """
    text = row.raw_line
    annual_yen = 0.0
    yield_pct = 0.0
    m_rent = _re.search(r'年間予定収入[：:]?\s*(\d[\d,]+)円', text)
    if m_rent:
        annual_yen = float(m_rent.group(1).replace(',', ''))
    m_yield = _re.search(r'年利回り[：:]?\s*([\d.]+)%', text)
    if m_yield:
        yield_pct = float(m_yield.group(1))
    return (annual_yen / 10000, yield_pct)


def _kubun_to_dict(row: PropertyRow, first_seen: dict, city_key: str = "") -> dict:
    d = asdict(row)
    d["prop_type"] = "kubun"
    d["is_oc"] = _is_oc_row(row)
    fs = first_seen.get(row.url, "")
    d["first_seen"] = fs
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
        structure_for_calc = row.structure or "RC造"
        try:
            ra = revenue_analyze(
                price_man=row.price_man,
                yield_pct=est_yield,
                structure=structure_for_calc,
                built_year=row.built_year,
                units_count=1,
                area_sqm=row.area_sqm,
            )
            d["revenue"] = {
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
        except Exception:
            pass

    return d


# ---------------------------------------------------------------------------
# Load 一棟もの (whole buildings)
# ---------------------------------------------------------------------------
def _load_ittomono_by_city(city_key: str) -> list[IttomonoRow]:
    rows: list[IttomonoRow] = []
    for prefix in ["ittomono", "rakumachi_ittomono", "ftakken_ittomono"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            rows.extend(ittomono_parse(p, city_key))
    return rows


def _ittomono_to_dict(row: IttomonoRow, city_key: str = "fukuoka", first_seen: dict | None = None) -> dict:
    d = asdict(row)
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
    d["first_seen"] = fs_date
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
    area = row.area_sqm or 0
    if row.price_man and row.price_man > 0 and area > 0:
        rent_per_sqm, ward = _get_rent_per_sqm(city_key, row.location, row.built_year)
        monthly_rent = rent_per_sqm * area
        d["est_monthly_rent"] = f"{monthly_rent / 10000:.1f}万" if monthly_rent >= 10000 else f"{int(monthly_rent):,}円"
        d["rent_source"] = f"相場{ward}" if ward else "想定家賃"
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
            d["revenue"] = {
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
        kubun_props = [_kubun_to_dict(r, first_seen, city_key=cfg["key"]) for r in kubun_rows]

        # 一棟もの (city subset)
        city_ittomono = [r for r in all_ittomono if r.city_key == cfg["key"]]
        ittomono_props = [_ittomono_to_dict(r, city_key=cfg["key"], first_seen=first_seen) for r in city_ittomono[:15]]

        # 戸建て (city subset)
        city_kodate = [r for r in all_kodate if r.city_key == cfg["key"]]
        kodate_props = [_kodate_to_dict(r, city_key=cfg["key"], first_seen=first_seen) for r in city_kodate[:10]]

        # 格安区分 (budget tier — Fukuoka only)
        budget_rows = _load_budget(cfg["key"])
        budget_props = [_kubun_to_dict(r, first_seen, city_key=cfg["key"]) for r in budget_rows]
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
