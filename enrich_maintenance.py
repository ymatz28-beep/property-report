#!/usr/bin/env python3
"""
管理費・修繕積立金enrichmentスクリプト
楽待/カウカモの詳細ページから管理費+修繕積立金を取得し、rawデータを更新する。
"""

import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}


def _fetch(url: str) -> str | None:
    """Fetch URL with proper encoding for Japanese paths."""
    parsed = urlparse(url)
    encoded_path = quote(parsed.path, safe="/:@!$&'()*+,;=")
    safe_url = f"{parsed.scheme}://{parsed.netloc}{encoded_path}"
    if parsed.query:
        safe_url += f"?{parsed.query}"
    try:
        req = Request(safe_url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"    [WARN] {e} : {url[:60]}")
        return None


def _parse_yen(text: str) -> int:
    """Parse yen amount like '10,920円' or '1万5600円' to integer."""
    text = text.replace(",", "").replace(" ", "").strip()
    # 1万5600円 format
    m = re.match(r"(\d+)万(\d*)円?", text)
    if m:
        man = int(m.group(1))
        remainder = int(m.group(2)) if m.group(2) else 0
        return man * 10000 + remainder
    # 10920円 format
    m = re.match(r"(\d+)円?", text)
    if m:
        return int(m.group(1))
    return 0


def enrich_rakumachi(html: str) -> str:
    """Extract maintenance fee from rakumachi detail page."""
    kanri = 0
    shuuzen = 0

    # 管理費（月額） followed by amount
    m = re.search(r"管理費（月額）.*?(\d[\d,]*円)", html, re.DOTALL)
    if m:
        kanri = _parse_yen(m.group(1))

    # 修繕積立金（月額） followed by amount
    m = re.search(r"修繕積立金（月額）.*?(\d[\d,]*円)", html, re.DOTALL)
    if m:
        shuuzen = _parse_yen(m.group(1))

    if kanri or shuuzen:
        parts = []
        if kanri:
            parts.append(f"管理費{kanri:,}円")
        if shuuzen:
            parts.append(f"修繕{shuuzen:,}円")
        return "+".join(parts)
    return ""


def enrich_cowcamo(html: str) -> str:
    """Extract maintenance fee from cowcamo detail page.
    Format: 管理費 → (whitespace/tags) → 8,700 円／月
    """
    # Strip HTML tags for easier parsing
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    kanri = 0
    shuuzen = 0

    # Pattern: 管理費 ... N,NNN 円／月
    m = re.search(r"管理費\s+([\d,]+)\s*円", text)
    if m:
        kanri = int(m.group(1).replace(",", ""))

    m = re.search(r"修繕積立金\s+([\d,]+)\s*円", text)
    if m:
        shuuzen = int(m.group(1).replace(",", ""))

    if kanri or shuuzen:
        parts = []
        if kanri:
            parts.append(f"管理費{kanri:,}円")
        if shuuzen:
            parts.append(f"修繕{shuuzen:,}円")
        return "+".join(parts)
    return ""


def enrich_file(filepath: Path) -> int:
    """Enrich a raw data file with maintenance fees. Returns count of enriched rows."""
    if not filepath.exists():
        return 0

    lines = filepath.read_text(encoding="utf-8").splitlines()
    updated = 0
    new_lines = []

    for line in lines:
        if line.startswith("#") or not line.strip():
            new_lines.append(line)
            continue

        parts = line.split("|")
        if len(parts) < 12:
            new_lines.append(line)
            continue

        source = parts[0].strip()
        maintenance = parts[10].strip()
        url = parts[11].strip()

        # Skip if already has maintenance data
        if maintenance:
            new_lines.append(line)
            continue

        # Only enrich rakumachi and cowcamo
        if source not in ("楽待", "カウカモ"):
            new_lines.append(line)
            continue

        print(f"  Enriching: {parts[1][:30]} ({source})")
        html = _fetch(url)
        if not html:
            new_lines.append(line)
            time.sleep(1)
            continue

        if source == "楽待":
            fee_text = enrich_rakumachi(html)
        elif source == "カウカモ":
            fee_text = enrich_cowcamo(html)
        else:
            fee_text = ""

        if fee_text:
            parts[10] = fee_text
            new_lines.append("|".join(parts))
            updated += 1
            print(f"    → {fee_text}")
        else:
            new_lines.append(line)
            print(f"    → データなし")

        time.sleep(0.8)

    filepath.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def main():
    print("=== 管理費enrichment開始 ===\n")

    targets = [
        DATA_DIR / "multi_site_osaka_raw.txt",
        DATA_DIR / "multi_site_fukuoka_raw.txt",
        DATA_DIR / "multi_site_tokyo_raw.txt",
        DATA_DIR / "rakumachi_osaka_raw.txt",
        DATA_DIR / "rakumachi_fukuoka_raw.txt",
        DATA_DIR / "rakumachi_tokyo_raw.txt",
    ]

    total = 0
    for f in targets:
        if f.exists():
            print(f"\n--- {f.name} ---")
            count = enrich_file(f)
            total += count
            print(f"  → {count}件 enriched")

    print(f"\n=== 完了: {total}件 enriched ===")


if __name__ == "__main__":
    main()
