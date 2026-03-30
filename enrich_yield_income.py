"""Enrich yield data files: fetch 想定年間収入 from 楽待 detail pages for OC properties.

Usage: python enrich_yield_income.py [--dry-run] [--max N] [--city fukuoka|osaka|tokyo]
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# Reuse scraper's fetch + extract logic
sys.path.insert(0, str(Path(__file__).resolve().parent))
from search_yield_focused import fetch_page, _extract_detail_fields, close_pw


def _parse_line(line: str) -> dict | None:
    """Parse a yield data line into parts."""
    if not line or line.startswith("#") or line.startswith("##"):
        return None
    parts = line.split("|")
    if len(parts) < 12:
        return None
    return {
        "source": parts[0],
        "name": parts[1],
        "price": parts[2],
        "location": parts[3],
        "area": parts[4],
        "built": parts[5],
        "station": parts[6],
        "layout": parts[7],
        "oc_flag": parts[8],
        "brokerage": parts[9],
        "maintenance": parts[10],
        "url": parts[11],
        "extra": parts[12:],
    }


def _rebuild_line(p: dict) -> str:
    """Rebuild pipe-delimited line from parts."""
    base = [p["source"], p["name"], p["price"], p["location"], p["area"],
            p["built"], p["station"], p["layout"], p["oc_flag"],
            p["brokerage"], p["maintenance"], p["url"]]
    base.extend(p.get("extra", []))
    return "|".join(base)


def enrich_file(path: Path, max_fetches: int = 50, dry_run: bool = False) -> int:
    """Enrich a single yield data file. Returns count of enriched properties."""
    lines = path.read_text(encoding="utf-8").splitlines()
    enriched = 0
    updated_lines = []

    targets = []
    for i, line in enumerate(lines):
        p = _parse_line(line)
        if p and p["oc_flag"].strip() == "OC" and "年間収入" not in p["brokerage"]:
            url = p["url"].strip()
            if "rakumachi.jp" in url:
                targets.append((i, p))

    print(f"  {path.name}: OC物件{len(targets)}件が年間収入欠落")
    if dry_run:
        return 0

    fetched = 0
    for idx, (line_idx, p) in enumerate(targets):
        if fetched >= max_fetches:
            print(f"  max_fetches={max_fetches}に到達、残り{len(targets)-idx}件は次回")
            break

        url = p["url"].strip()
        html = fetch_page(url)
        if not html:
            continue
        fetched += 1

        # Extract fields using scraper's logic
        prop = {"name": p["name"], "url": url}
        if _extract_detail_fields(html, prop):
            # Update name if better one found
            if prop.get("name") and prop["name"] != p["name"]:
                p["name"] = prop["name"]

            # Update brokerage with annual income
            if prop.get("annual_income_man"):
                brok_parts = []
                # Keep existing yield info
                yield_m = re.search(r"利回り[\d.]+%", p["brokerage"])
                if yield_m:
                    brok_parts.append(yield_m.group())
                brok_parts.append(f"年間収入{prop['annual_income_man']}万円")
                p["brokerage"] = " ".join(brok_parts)
                enriched += 1

            # Update maintenance if found
            if prop.get("maintenance_fee"):
                fee = prop["maintenance_fee"]
                if not p["maintenance"].strip():
                    p["maintenance"] = f"管理費修繕{fee}"

            lines[line_idx] = _rebuild_line(p)

        time.sleep(1.5)  # Rate limit

    if enriched > 0:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  → {enriched}件の年間収入を補完 (fetched={fetched})")
    else:
        print(f"  → 補完対象なし (fetched={fetched})")

    return enriched


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max", type=int, default=50, help="Max fetches per file")
    parser.add_argument("--city", choices=["fukuoka", "osaka", "tokyo"], default=None)
    args = parser.parse_args()

    cities = [args.city] if args.city else ["fukuoka", "osaka", "tokyo"]
    total = 0
    for city in cities:
        path = DATA_DIR / f"yield_{city}_raw.txt"
        if path.exists():
            total += enrich_file(path, max_fetches=args.max, dry_run=args.dry_run)

    close_pw()
    print(f"\n合計: {total}件の年間収入を補完")


if __name__ == "__main__":
    main()
