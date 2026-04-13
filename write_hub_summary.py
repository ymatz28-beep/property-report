#!/usr/bin/env python3
"""Generate data/hub_summary.json for the property-report hub KPI strip.

Reads live state from property-analyzer data files and writes a compact
JSON consumed by property-report/index.html::loadKpi().

Output: output/data/hub_summary.json (picked up by deploy_to_gh_pages()).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_LIB_PARENT = _PROJECT_ROOT.parent
for p in [str(_PROJECT_ROOT), str(_LIB_PARENT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import yaml  # noqa: E402

DATA_DIR = _PROJECT_ROOT / "data"
OUTPUT_DIR = _PROJECT_ROOT / "output" / "data"


def _active_inquiries(inquiries_yaml: Path) -> int:
    if not inquiries_yaml.exists():
        return 0
    data = yaml.safe_load(inquiries_yaml.read_text(encoding="utf-8")) or {}
    items = data.get("items") or data if isinstance(data, list) else (data.get("inquiries") or [])
    # Tolerate both dict-with-list and list-at-root
    if isinstance(items, dict):
        items = items.get("items", [])
    active_states = {"inquired", "in_discussion", "viewing", "viewed"}
    return sum(1 for it in items if it.get("status") in active_states)


def _properties_total(properties_yaml: Path) -> int:
    if not properties_yaml.exists():
        return 0
    data = yaml.safe_load(properties_yaml.read_text(encoding="utf-8")) or {}
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        items = data.get("items") or data.get("properties") or []
        return len(items) if isinstance(items, list) else 0
    return 0


def _top_score(patrol_summary_json: Path) -> int | None:
    """Best-effort top score from patrol output. Returns None if unknown."""
    if not patrol_summary_json.exists():
        return None
    try:
        data = json.loads(patrol_summary_json.read_text(encoding="utf-8"))
        return data.get("top_score")
    except Exception:
        return None


def _last_patrol_iso(patrol_summary_json: Path) -> str:
    if not patrol_summary_json.exists():
        return datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        data = json.loads(patrol_summary_json.read_text(encoding="utf-8"))
        raw = data.get("date")
        if raw:
            # "2026-04-10 18:54" → ISO with +09:00
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
            return dt.isoformat(timespec="seconds") + "+09:00"
    except Exception:
        pass
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> int:
    total = _properties_total(DATA_DIR / "properties.yaml")
    inquiries = _active_inquiries(DATA_DIR / "inquiries.yaml")
    patrol = DATA_DIR / "patrol_summary.json"
    top = _top_score(patrol)

    summary = {
        "candidates": f"{total:,}" if total else None,
        "top_score": top,
        "inquiries": inquiries,
        "updated_at": _last_patrol_iso(patrol),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "hub_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  hub_summary.json written: candidates={summary['candidates']} "
          f"inquiries={summary['inquiries']} top_score={summary['top_score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
