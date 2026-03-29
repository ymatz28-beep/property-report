"""Pipeline page generator.

Reads inquiries.yaml and generates a Kanban-style pipeline tracking board.
Uses shared iUMA design system components.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent
_LIB_PARENT = _PROJECT_ROOT.parent
for p in [str(_PROJECT_ROOT), str(_LIB_PARENT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generate_market import PROPERTY_PAGES, GNAV_PAGES
from lib.renderer import create_env, PUBLIC_NAV
from lib.styles.design_tokens import get_base_css, get_css_tokens, get_google_fonts_url

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
INQUIRIES_PATH = DATA_DIR / "inquiries.yaml"

# ---------------------------------------------------------------------------
# Status → Kanban column mapping
# ---------------------------------------------------------------------------
COLUMN_DEFS = [
    {
        "key": "flagged",
        "label": "発見",
        "color": "var(--accent, #6366f1)",
        "statuses": ["discovered", "flagged"],
    },
    {
        "key": "inquired",
        "label": "問合せ",
        "color": "var(--yellow, #eab308)",
        "statuses": ["inquired", "in_discussion"],
    },
    {
        "key": "viewing",
        "label": "内覧",
        "color": "var(--orange, #ff6b35)",
        "statuses": ["viewing", "viewed"],
    },
    {
        "key": "decided",
        "label": "決定",
        "color": "var(--green, #22c55e)",
        "statuses": ["decided", "passed"],
    },
]

CITY_LABELS = {
    "osaka": "大阪",
    "fukuoka": "福岡",
    "tokyo": "東京",
}


def _load_inquiries() -> list[dict]:
    """Load and parse inquiries.yaml."""
    if not INQUIRIES_PATH.exists():
        print(f"  [SKIP] {INQUIRIES_PATH} not found")
        return []
    data = yaml.safe_load(INQUIRIES_PATH.read_text(encoding="utf-8"))
    return data.get("inquiries", []) if data else []


def _item_to_card(item: dict) -> dict:
    """Transform inquiry dict to template-friendly card dict."""
    return {
        "id": item.get("id", ""),
        "name": item.get("name", "Unknown"),
        "url": item.get("url", ""),
        "source": item.get("source", ""),
        "city": item.get("city", ""),
        "city_label": CITY_LABELS.get(item.get("city", ""), item.get("city", "")),
        "score": item.get("score", 0),
        "status": item.get("status", "flagged"),
        "price": item.get("price", 0),
        "area": item.get("area", 0),
        "layout": item.get("layout", ""),
        "station": item.get("station", ""),
        "year_built": item.get("year_built"),
        "pet": item.get("pet", ""),
        "short_term": item.get("short_term", ""),
        "management_fee": item.get("management_fee", 0),
        "agent": item.get("agent", ""),
        "viewing_date": item.get("viewing_date", ""),
        "decision": item.get("decision", ""),
        "notes": item.get("notes", ""),
    }


def main() -> Path | None:
    print("=== Generating Pipeline page ===")

    inquiries = _load_inquiries()
    if not inquiries:
        print("  No inquiries found")
        return None

    # Build columns
    columns = []
    for col_def in COLUMN_DEFS:
        items = [
            _item_to_card(inq)
            for inq in inquiries
            if inq.get("status") in col_def["statuses"]
        ]
        # Sort by score descending
        items.sort(key=lambda x: -(x.get("score") or 0))
        columns.append({
            "key": col_def["key"],
            "label": col_def["label"],
            "color": col_def["color"],
            "count": len(items),
            "cards": items,
        })

    # City filter
    city_counts: dict[str, int] = {}
    for inq in inquiries:
        city = inq.get("city", "")
        city_counts[city] = city_counts.get(city, 0) + 1

    city_filter = [
        {"key": k, "label": CITY_LABELS.get(k, k), "count": v}
        for k, v in sorted(city_counts.items())
    ]

    # Stats
    total = len(inquiries)
    active = sum(
        1 for inq in inquiries
        if inq.get("status") not in ("passed", "decided")
    )
    viewed = sum(1 for inq in inquiries if inq.get("status") in ("viewed", "viewing"))
    passed = sum(1 for inq in inquiries if inq.get("status") == "passed")
    scores = [inq.get("score", 0) for inq in inquiries if inq.get("score")]
    avg_score = int(sum(scores) / len(scores)) if scores else 0

    stats = {
        "total": total,
        "active": active,
        "viewed": viewed,
        "passed": passed,
        "avg_score": avg_score,
    }

    print(f"  Total: {total}, Active: {active}, Viewed: {viewed}, Passed: {passed}")
    for col in columns:
        print(f"    {col['label']}: {col['count']}")

    # Render
    env = create_env(
        extra_dirs=[_PROJECT_ROOT / "lib" / "templates"],
        scope="public",
    )

    template = env.get_template("pages/pipeline.html")
    html = template.render(
        columns=columns,
        city_filter=city_filter,
        stats=stats,
        property_pages=PROPERTY_PAGES,
        property_current="Pipeline",
        gnav_pages=GNAV_PAGES,
        gnav_current="Pipeline",
        nav_items=PUBLIC_NAV,
        current_page="Property",
        css_tokens=get_css_tokens(),
        base_css=get_base_css(),
        google_fonts_url=get_google_fonts_url(),
    )

    out = OUTPUT_DIR / "pipeline.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Generated: {out} ({len(html) // 1024}KB)")
    return out


if __name__ == "__main__":
    main()
