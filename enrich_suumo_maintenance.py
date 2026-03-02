#!/usr/bin/env python3
"""SUUMO物件の管理費+修繕積立金を詳細ページから取得し、rawデータを12列化する。"""

import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATA_DIR = Path("data")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def _parse_suumo_yen(text: str) -> int:
    """SUUMO形式の金額をパース。例: '1万5600円', '8,500円', '1万円'"""
    text = text.replace(",", "").replace("，", "")
    m = re.search(r"(\d+)万(\d+)?円", text)
    if m:
        man = int(m.group(1))
        rest = int(m.group(2)) if m.group(2) else 0
        return man * 10000 + rest
    m2 = re.search(r"(\d+)円", text)
    if m2:
        return int(m2.group(1))
    return 0


def fetch_maintenance_from_suumo(url: str) -> str:
    """SUUMOの物件詳細ページから管理費+修繕積立金を取得。内訳形式で返す。"""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"    Fetch error: {e}")
        return ""

    kanri = 0
    shuuzen = 0
    m_kanri = re.search(r"管理費.*?<td[^>]*>(.*?)</td>", html, re.DOTALL)
    if m_kanri:
        kanri = _parse_suumo_yen(m_kanri.group(1))

    m_shuzen = re.search(r"修繕積立金.*?<td[^>]*>(.*?)</td>", html, re.DOTALL)
    if m_shuzen:
        shuuzen = _parse_suumo_yen(m_shuzen.group(1))

    if kanri > 0 and shuuzen > 0:
        return f"管理費{kanri}+修繕{shuuzen}"
    elif kanri > 0:
        return f"管理費{kanri}"
    elif shuuzen > 0:
        return f"修繕{shuuzen}"
    return ""


def enrich_file(filepath: Path) -> int:
    """rawデータファイルを読み、SUUMO URLがある行の管理費を取得して12列化。"""
    lines = filepath.read_text(encoding="utf-8").splitlines()
    updated_lines: list[str] = []
    enriched = 0
    total_data = 0

    for line in lines:
        # Skip headers/comments/empty
        if not line.strip() or line.startswith("#") or line.startswith("##"):
            updated_lines.append(line)
            continue

        parts = line.split("|")

        # Already 12 columns with maintenance data
        if len(parts) == 12 and parts[10].strip():
            updated_lines.append(line)
            total_data += 1
            continue

        # 8-column SUUMO format: name|price|location|area|built|station|layout|url
        if len(parts) == 8:
            url = parts[7].strip()
            total_data += 1
            if "suumo.jp" in url:
                print(f"  Fetching: {parts[0][:20]}...")
                maint_str = fetch_maintenance_from_suumo(url)
                # Convert to 12-col: source|name|price|location|area|built|station|layout|pet|brokerage|maintenance|url
                new_line = f"SUUMO|{parts[0]}|{parts[1]}|{parts[2]}|{parts[3]}|{parts[4]}|{parts[5]}|{parts[6]}|||{maint_str}|{url}"
                updated_lines.append(new_line)
                if maint_str:
                    enriched += 1
                    print(f"    → {maint_str}")
                else:
                    print(f"    → データなし")
                time.sleep(1.5)  # Rate limiting
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
            total_data += 1

    filepath.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return enriched


def main():
    targets = [
        DATA_DIR / "suumo_osaka_v2_raw.txt",
    ]
    for filepath in targets:
        if not filepath.exists():
            print(f"Skip: {filepath} (not found)")
            continue
        print(f"\n=== Enriching {filepath.name} ===")
        count = enrich_file(filepath)
        print(f"  Enriched: {count} properties")


if __name__ == "__main__":
    main()
