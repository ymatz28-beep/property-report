#!/usr/bin/env python3
"""
Fix catchphrase names in ftakken_fukuoka_raw.txt by fetching actual building names from detail pages.
"""

import re
import time
import requests

DATA_FILE = "/Users/yumatejima/Documents/Projects/property-analyzer/data/ftakken_fukuoka_raw.txt"
DELAY = 0.5  # seconds between requests

CATCHPHRASE_CHARS = set("。♪！☆◆◇■▲●★「」")

def is_catchphrase(name: str) -> bool:
    """Return True if name looks like a catchphrase rather than a building name."""
    # Contains special catchphrase characters
    if any(c in name for c in CATCHPHRASE_CHARS):
        return True
    # 2+ occurrences of 、
    if name.count("、") >= 2:
        return True
    # Starts with special chars
    if name.startswith(("◆", "☆", "★")):
        return True
    # Too long to be a building name
    if len(name) > 30:
        return True
    return False

def fetch_building_name(url: str) -> str | None:
    """Fetch building name from the detail page title."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 404:
            print(f"  404: {url}")
            return None
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {url}")
            return None

        # Find <title> tag
        m = re.search(r"<title>(.*?)</title>", r.text, re.DOTALL)
        if not m:
            print(f"  No <title> found: {url}")
            return None

        title = m.group(1).strip()

        # Title format: "ふれんず｜{建物名} ({item_id})／{address}／..."
        # Split on full-width pipe ｜
        parts = title.split("｜")
        if len(parts) >= 2:
            after_pipe = parts[1]
            # Extract building name: everything before " (" (space + open paren)
            bm = re.match(r"^(.+?)\s+\(", after_pipe)
            if bm:
                return bm.group(1).strip()

        # Fallback: just return the title
        print(f"  Could not parse title: {title!r}")
        return None

    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_checked = 0
    total_fixed = 0
    total_failed = 0
    updated_lines = []

    for line in lines:
        # Skip header/comment lines and blank lines
        if line.startswith("##") or not line.strip() or not line.startswith("ふれんず|"):
            updated_lines.append(line)
            continue

        fields = line.rstrip("\n").split("|")
        if len(fields) < 12:
            updated_lines.append(line)
            continue

        name = fields[1]
        url = fields[-1]

        if not is_catchphrase(name):
            updated_lines.append(line)
            continue

        total_checked += 1
        print(f"[{total_checked}] Checking: {name[:60]!r}")

        new_name = fetch_building_name(url)
        time.sleep(DELAY)

        if new_name and new_name != name:
            print(f"  FIXED: {name[:60]!r} → {new_name!r}")
            fields[1] = new_name
            updated_lines.append("|".join(fields) + "\n")
            total_fixed += 1
        elif new_name is None:
            print(f"  FAILED: keeping original")
            updated_lines.append(line)
            total_failed += 1
        else:
            # Name unchanged (shouldn't happen often)
            print(f"  UNCHANGED: {new_name!r}")
            updated_lines.append(line)
            total_failed += 1

    # Write back
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    print("\n" + "=" * 60)
    print(f"SUMMARY: checked={total_checked}, fixed={total_fixed}, failed={total_failed}")


if __name__ == "__main__":
    main()
