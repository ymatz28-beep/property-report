"""Unified Market page generator.

Merges 3 city reports (区分) + 一棟もの into a single tabbed Market page.
Uses new Jinja2 templates with iUMA design system.
Replaces: generate_osaka_report.py, generate_fukuoka_report.py,
          generate_tokyo_report.py, generate_ittomono_report.py (for output only).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure lib is importable
_PROJECT_ROOT = Path(__file__).resolve().parent
_LIB_PARENT = _PROJECT_ROOT.parent  # ~/Documents/Projects
for p in [str(_PROJECT_ROOT), str(_LIB_PARENT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generate_search_report_common import (
    ReportConfig,
    PropertyRow,
    dedupe_properties,
    grade_tier,
    hydrate_parsed_fields,
    load_first_seen,
    load_sold_urls,
    parse_data_file,
    score_row,
)
from generate_ittomono_report import (
    IttomonoRow,
    build_report_html as _ittomono_build_unused,
    main as _ittomono_main_unused,
    parse_data_file as ittomono_parse,
    score_row as ittomono_score_row,
    _filter_rows as ittomono_filter,
    _deduplicate_rows as ittomono_dedup,
)
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


# ---------------------------------------------------------------------------
# City configs (extracted from individual generators)
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


# ---------------------------------------------------------------------------
# Load & score city properties (区分)
# ---------------------------------------------------------------------------

# OC / pet / minpaku filter keywords (from generate_search_report_common)
_OC_KEYWORDS = [
    "オーナーチェンジ", "賃貸中", "利回り", "投資顧問", "投資物件",
    "家賃", "月額賃料", "年間収入", "年間賃料",
    "表面利回", "想定利回", "収益", "入居者付", "入居中",
    "賃借人", "テナント付", "現行賃料", "満室",
]

TIER_GREEN = 80
TIER_YELLOW = 65
MAX_YELLOW_FILL = 20


def _load_city(cfg: dict) -> list[PropertyRow]:
    """Load, dedupe, filter, score properties for one city."""
    data_path = cfg["data_path"]
    if not data_path.exists():
        print(f"  [SKIP] {cfg['label']}: {data_path} not found")
        return []

    rows = parse_data_file(data_path)
    for extra in _find_extra_paths(cfg["key"]):
        if extra.exists():
            rows.extend(parse_data_file(extra))

    if cfg.get("include_osaka_r"):
        # Import inline to avoid circular
        try:
            from generate_search_report_common import parse_osaka_r_rows, OSAKA_R_ROWS
            rows.extend(parse_osaka_r_rows(OSAKA_R_ROWS))
        except ImportError:
            pass

    rows, _ = dedupe_properties(rows)

    # Filters
    sold = load_sold_urls()
    rows = [r for r in rows if r.url.rstrip("/") + "/" not in sold]

    def _is_oc(r: PropertyRow) -> bool:
        text = f"{r.name} {r.station_text} {r.minpaku_status} {r.location} {r.raw_line}"
        return any(kw in text for kw in _OC_KEYWORDS)

    rows = [r for r in rows if not _is_oc(r)]
    rows = [r for r in rows if r.pet_status != "不可" and "ペット不可" not in f"{r.pet_status} {r.name} {r.raw_line}" and "ペット飼育不可" not in f"{r.pet_status} {r.name} {r.raw_line}"]
    rows = [r for r in rows if "民泊禁止" not in f"{r.minpaku_status} {r.name} {r.raw_line}" and "民泊不可" not in f"{r.minpaku_status} {r.name} {r.raw_line}"]

    # Score
    config = ReportConfig(
        city_key=cfg["key"],
        city_label=cfg["label"],
        accent="#6366f1",
        accent_rgb="99,102,241",
        data_path=data_path,
        output_path=OUTPUT_DIR / "market.html",
        hero_conditions=[],
        search_condition_bullets=[],
        investor_notes=[],
    )
    for row in rows:
        score_row(row, config)

    # Tier filter
    rows = [r for r in rows if r.total_score >= TIER_YELLOW]
    rows.sort(key=lambda r: -r.total_score)

    green = [r for r in rows if r.total_score >= TIER_GREEN]
    yellow = [r for r in rows if TIER_YELLOW <= r.total_score < TIER_GREEN]
    if len(green) >= MAX_YELLOW_FILL:
        rows = green
    else:
        slots = MAX_YELLOW_FILL - len(green)
        rows = green + yellow[:slots]

    print(f"  {cfg['label']}: {len(rows)} properties (green={len(green)}, yellow={len(yellow)})")
    return rows


def _row_to_dict(row: PropertyRow, first_seen: dict) -> dict:
    """Convert PropertyRow to template-friendly dict."""
    d = asdict(row)
    fs = first_seen.get(row.url, "")
    d["first_seen"] = fs
    # Mark as new if first seen within 3 days
    if fs:
        from datetime import datetime, timedelta
        try:
            fs_date = datetime.strptime(fs[:10], "%Y-%m-%d")
            d["is_new"] = (datetime.now() - fs_date).days <= 3
        except (ValueError, TypeError):
            d["is_new"] = False
    else:
        d["is_new"] = False
    return d


# ---------------------------------------------------------------------------
# Load ittomono properties
# ---------------------------------------------------------------------------
def _load_ittomono() -> list[dict]:
    """Load and score ittomono properties across all cities."""
    all_rows: list[IttomonoRow] = []
    for city_key in ["osaka", "fukuoka", "tokyo"]:
        for prefix in ["ittomono", "rakumachi", "ftakken_ittomono"]:
            p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
            if p.exists():
                parsed = ittomono_parse(p, city_key)
                all_rows.extend(parsed)

    if not all_rows:
        return []

    all_rows = ittomono_filter(all_rows)
    all_rows = ittomono_dedup(all_rows)

    for row in all_rows:
        ittomono_score_row(row)

    # Top scored, filter low
    all_rows = [r for r in all_rows if r.total_score >= 40]
    all_rows.sort(key=lambda r: -r.total_score)
    all_rows = all_rows[:30]  # Top 30

    result = []
    for row in all_rows:
        d = asdict(row)
        # Map ittomono fields to unified card format
        d["maintenance_fee_text"] = ""
        d["pet_status"] = ""
        d["minpaku_status"] = ""
        d["first_seen"] = ""
        d["is_new"] = False
        # Yield as extra KPI
        if row.yield_pct:
            d["yield_text"] = f"{row.yield_pct:.1f}%"
        result.append(d)

    print(f"  一棟もの: {len(result)} properties")
    return result


# ---------------------------------------------------------------------------
# Load patrol summary
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

    # Load all cities
    cities = []
    all_count = 0
    all_green = 0
    all_yellow = 0
    all_prices = []
    all_areas = []
    pet_ok = 0

    for cfg in CITY_CONFIGS:
        rows = _load_city(cfg)
        props = [_row_to_dict(r, first_seen) for r in rows]
        green = sum(1 for r in rows if r.total_score >= TIER_GREEN)
        yellow = len(rows) - green
        cities.append({
            "key": cfg["key"],
            "label": cfg["label"],
            "count": len(props),
            "properties": props,
        })
        all_count += len(props)
        all_green += green
        all_yellow += yellow
        all_prices.extend(r.price_man for r in rows if r.price_man > 0)
        all_areas.extend(r.area_sqm for r in rows if r.area_sqm)
        pet_ok += sum(1 for r in rows if r.pet_status in ("可", "相談可"))

    # Load ittomono
    ittomono_props = _load_ittomono()
    ittomono_data = {
        "count": len(ittomono_props),
        "properties": ittomono_props,
    }

    # Totals
    avg_price = int(sum(all_prices) / len(all_prices)) if all_prices else 0
    avg_area = round(sum(all_areas) / len(all_areas), 1) if all_areas else 0

    totals = {
        "count": all_count,
        "green_count": all_green,
        "yellow_count": all_yellow,
        "avg_price": avg_price,
        "avg_area": avg_area,
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
        ittomono=ittomono_data,
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

    # Also keep legacy city reports for backward compat during transition
    # (patrol still references them)

    return out


if __name__ == "__main__":
    main()
