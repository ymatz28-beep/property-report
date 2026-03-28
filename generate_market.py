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
    {"href": "portfolio.html", "label": "Portfolio"},
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


_ESTIMATED_RENT_PER_SQM: dict[str, int] = {
    "osaka": 2800,    # 大阪: ㎡あたり月額賃料（円）
    "fukuoka": 2400,  # 福岡
    "tokyo": 3200,    # 東京
}


def _kubun_to_dict(row: PropertyRow, first_seen: dict, city_key: str = "") -> dict:
    d = asdict(row)
    d["prop_type"] = "kubun"
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

    # Revenue analysis for kubun (estimate yield from market rent)
    d["revenue"] = None
    if row.price_man > 0 and getattr(row, "area_sqm", None) and row.area_sqm > 0:
        rent_per_sqm = _ESTIMATED_RENT_PER_SQM.get(city_key, 2800)
        annual_rent = rent_per_sqm * row.area_sqm * 12 / 10000  # 万円
        est_yield = (annual_rent / row.price_man) * 100
        d["yield_text"] = f"{est_yield:.1f}%"
        try:
            ra = revenue_analyze(
                price_man=row.price_man,
                yield_pct=est_yield,
                structure=row.layout or "RC造",  # kubun = mostly RC
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
                "loan_amount": round(ra.loan_amount, 1),
                "loan_years": ra.loan_years,
                "annual_debt_service": round(ra.annual_debt_service, 1),
            }
        except Exception:
            pass

    return d


# ---------------------------------------------------------------------------
# Load 一棟もの (whole buildings)
# ---------------------------------------------------------------------------
def _load_ittomono_by_city(city_key: str) -> list[IttomonoRow]:
    rows: list[IttomonoRow] = []
    for prefix in ["ittomono", "rakumachi", "ftakken_ittomono"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            rows.extend(ittomono_parse(p, city_key))
    return rows


def _ittomono_to_dict(row: IttomonoRow) -> dict:
    d = asdict(row)
    d["prop_type"] = "ittomono"
    d["maintenance_fee_text"] = ""
    d["pet_status"] = ""
    d["minpaku_status"] = ""
    d["first_seen"] = ""
    d["is_new"] = False

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

    # Revenue analysis
    if row.price_man and row.yield_pct and row.price_man > 0 and row.yield_pct > 0:
        try:
            ra = revenue_analyze(
                price_man=row.price_man,
                yield_pct=row.yield_pct,
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
                "loan_amount": round(ra.loan_amount, 1),
                "loan_years": ra.loan_years,
                "annual_debt_service": round(ra.annual_debt_service, 1),
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
    for prefix in ["ftakken_kodate"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            rows.extend(ittomono_parse(p, city_key))
    return rows


def _kodate_to_dict(row: IttomonoRow) -> dict:
    d = _ittomono_to_dict(row)
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

    # Collect all ittomono/kodate for global filtering
    all_ittomono: list[IttomonoRow] = []
    all_kodate: list[IttomonoRow] = []
    for cfg in CITY_CONFIGS:
        all_ittomono.extend(_load_ittomono_by_city(cfg["key"]))
        all_kodate.extend(_load_kodate_by_city(cfg["key"]))

    # Filter & dedup ittomono globally
    if all_ittomono:
        all_ittomono = ittomono_filter(all_ittomono)
        all_ittomono = ittomono_dedup(all_ittomono)
        for row in all_ittomono:
            ittomono_score_row(row)
        all_ittomono = [r for r in all_ittomono if r.total_score >= 40]
        all_ittomono.sort(key=lambda r: -r.total_score)

    # Filter & dedup kodate globally (lighter scoring)
    if all_kodate:
        all_kodate = ittomono_dedup(all_kodate)
        for row in all_kodate:
            ittomono_score_row(row)
        all_kodate = [r for r in all_kodate if r.total_score >= 30]
        all_kodate.sort(key=lambda r: -r.total_score)

    # Build city data
    cities = []
    total_kubun = 0
    total_ittomono = 0
    total_kodate = 0
    all_prices = []
    all_areas = []
    pet_ok = 0

    for cfg in CITY_CONFIGS:
        # 区分
        kubun_rows = _load_kubun(cfg)
        kubun_props = [_kubun_to_dict(r, first_seen, city_key=cfg["key"]) for r in kubun_rows]

        # 一棟もの (city subset)
        city_ittomono = [r for r in all_ittomono if r.city_key == cfg["key"]]
        ittomono_props = [_ittomono_to_dict(r) for r in city_ittomono[:15]]

        # 戸建て (city subset)
        city_kodate = [r for r in all_kodate if r.city_key == cfg["key"]]
        kodate_props = [_kodate_to_dict(r) for r in city_kodate[:10]]

        city_total = len(kubun_props) + len(ittomono_props) + len(kodate_props)

        cities.append({
            "key": cfg["key"],
            "label": cfg["label"],
            "count": city_total,
            "kubun": {"count": len(kubun_props), "properties": kubun_props},
            "ittomono": {"count": len(ittomono_props), "properties": ittomono_props},
            "kodate": {"count": len(kodate_props), "properties": kodate_props},
        })

        total_kubun += len(kubun_props)
        total_ittomono += len(ittomono_props)
        total_kodate += len(kodate_props)
        all_prices.extend(r.price_man for r in kubun_rows if r.price_man > 0)
        all_areas.extend(r.area_sqm for r in kubun_rows if r.area_sqm)
        pet_ok += sum(1 for r in kubun_rows if r.pet_status in ("可", "相談可"))

        print(f"  {cfg['label']}: 区分{len(kubun_props)} + 一棟{len(ittomono_props)} + 戸建{len(kodate_props)}")

    # Totals
    total_count = total_kubun + total_ittomono + total_kodate
    avg_price = int(sum(all_prices) / len(all_prices)) if all_prices else 0

    totals = {
        "count": total_count,
        "kubun_count": total_kubun,
        "ittomono_count": total_ittomono,
        "kodate_count": total_kodate,
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
    return out


if __name__ == "__main__":
    main()
