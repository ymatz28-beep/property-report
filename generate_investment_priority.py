"""Cross-city investment priority dashboard.

Reads data/investment_priority/*.json (written per-city by
generate_search_report_common.generate_report(), which runs inside each
generate_{osaka,fukuoka,tokyo}_report.py) and renders a single ranked table
across all cities. Run after the per-city reports so the JSON is current.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_LIB_PARENT = _PROJECT_ROOT.parent
for p in [str(_PROJECT_ROOT), str(_LIB_PARENT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from investment_priority import load_all_priority, tier_for
from lib.renderer import render

TEMPLATE_DIRS = [_PROJECT_ROOT / "lib" / "templates"]
OUTPUT_PATH = _PROJECT_ROOT / "output" / "investment-priority.html"


def _load_patrol_date() -> str:
    import json
    summary_path = _PROJECT_ROOT / "data" / "patrol_summary.json"
    if summary_path.exists():
        try:
            return json.loads(summary_path.read_text(encoding="utf-8")).get("date", "")
        except (ValueError, OSError):
            pass
    return ""


def main() -> None:
    raw_records = load_all_priority()
    records = []
    for r in raw_records:
        label, color = tier_for(r["composite_score"])
        records.append({**r, "tier_label": label, "tier_color": color})

    html = render(
        "pages/investment_priority.html",
        {
            "records": records,
            "generated_at": _load_patrol_date(),
            "total_count": len(records),
            "current_page": "投資優先度",
        },
        extra_dirs=TEMPLATE_DIRS,
        scope="private",
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Generated: {OUTPUT_PATH} ({len(records)}件)")
    if records:
        top = records[0]
        print(f"  Top: [{top['tier_label']}] {top['city_label']} {top['name']} score={top['composite_score']}")
    if sys.stdout.isatty():
        subprocess.run(["open", str(OUTPUT_PATH)])


if __name__ == "__main__":
    main()
