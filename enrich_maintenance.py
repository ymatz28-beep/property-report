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


def enrich_suumo(html: str) -> str:
    """Extract maintenance fee from SUUMO detail page. Returns breakdown format."""
    kanri = 0
    shuuzen = 0
    kanri_m = re.search(r'管理費</div>.*?</th>\s*<td[^>]*>(.*?)</td>', html, re.DOTALL)
    if kanri_m:
        kanri = _parse_yen(kanri_m.group(1))
    shuuzen_m = re.search(r'修繕積立金</div>.*?</th>\s*<td[^>]*>(.*?)</td>', html, re.DOTALL)
    if shuuzen_m:
        shuuzen = _parse_yen(shuuzen_m.group(1))
    if kanri > 0 and shuuzen > 0:
        return f"管理費{kanri}+修繕{shuuzen}"
    elif kanri > 0:
        return f"管理費{kanri}"
    elif shuuzen > 0:
        return f"修繕{shuuzen}"
    return ""


def enrich_yahoo(html: str) -> str:
    """Extract maintenance fee from Yahoo不動産 detail page.
    Format: 管理費 4,600円/月 ... 修繕積立金 5,800円/月
    """
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    kanri = 0
    shuuzen = 0

    m = re.search(r"管理費\s*([\d,]+)\s*円", text)
    if m:
        kanri = int(m.group(1).replace(",", ""))

    m = re.search(r"修繕積立金\s*([\d,]+)\s*円", text)
    if m:
        shuuzen = int(m.group(1).replace(",", ""))

    if kanri or shuuzen:
        parts = []
        if kanri:
            parts.append(f"管理費{kanri}")
        if shuuzen:
            parts.append(f"修繕{shuuzen}")
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



def enrich_athome(html: str) -> str:
    """Extract maintenance fee from athome detail page.
    Format: 管理費等 6,900円 ... 修繕積立金 9,600円
    """
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    kanri = 0
    shuuzen = 0

    m = re.search(r"管理費等\s*([\d,]+)\s*円", text)
    if m:
        kanri = int(m.group(1).replace(",", ""))

    m = re.search(r"修繕積立金\s*([\d,]+)\s*円", text)
    if m:
        shuuzen = int(m.group(1).replace(",", ""))

    if kanri or shuuzen:
        parts = []
        if kanri:
            parts.append(f"管理費{kanri}")
        if shuuzen:
            parts.append(f"修繕{shuuzen}")
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

        # Skip if already has breakdown data (管理費+修繕)
        # Re-enrich if only a raw number (no breakdown)
        has_breakdown = "管理" in maintenance or "修繕" in maintenance
        if maintenance and has_breakdown:
            new_lines.append(line)
            continue

        # Only enrich supported sources
        if source not in ("楽待", "カウカモ", "SUUMO", "Yahoo不動産", "athome", "福岡R不動産", "大阪R不動産", "東京R不動産"):
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
        elif source == "SUUMO":
            fee_text = enrich_suumo(html)
        elif source == "Yahoo不動産":
            fee_text = enrich_yahoo(html)
        elif source == "athome":
            fee_text = enrich_athome(html)
        elif source in ("福岡R不動産", "大阪R不動産", "東京R不動産"):
            fee_text = enrich_yahoo(html)  # Same format as Yahoo
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


def _parse_ftakken_fee(text: str) -> str:
    """Parse ふれんず detail page text for 管理費 + 積立金.

    Formats: '9500円', '1万4990円', '1万300円'
    """
    def _parse_yen(s: str) -> int:
        s = s.replace(",", "").strip()
        m = re.match(r"(\d+)万(\d+)円", s)
        if m:
            return int(m.group(1)) * 10000 + int(m.group(2))
        m = re.match(r"(\d+)万円", s)
        if m:
            return int(m.group(1)) * 10000
        m = re.match(r"(\d+)円", s)
        if m:
            return int(m.group(1))
        return 0

    kanri = 0
    tsumitate = 0

    m = re.search(r"管理費\s+([\d万,]+円)", text)
    if m:
        kanri = _parse_yen(m.group(1))

    m = re.search(r"積立金\s+([\d万,]+円)", text)
    if m:
        tsumitate = _parse_yen(m.group(1))

    if kanri > 0 and tsumitate > 0:
        return f"管理費{kanri}+修繕{tsumitate}"
    elif kanri > 0:
        return f"管理費{kanri}"
    elif tsumitate > 0:
        return f"修繕{tsumitate}"
    return ""


def enrich_ftakken_file(filepath: Path) -> int:
    """Enrich ふれんず properties by visiting detail pages with Playwright.

    Requires a browser session via listing page first (detail pages return 403 without cookies).
    """
    if not filepath.exists():
        return 0

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [WARN] playwright not installed, skipping ftakken enrichment")
        return 0

    lines = filepath.read_text(encoding="utf-8").splitlines()

    # Collect indices needing enrichment
    to_enrich = []
    for i, line in enumerate(lines):
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 12:
            continue
        source = parts[0].strip()
        if source != "ふれんず":
            continue
        maintenance = parts[10].strip()
        has_breakdown = "管理" in maintenance and "修繕" in maintenance
        if has_breakdown:
            continue
        url = parts[11].strip()
        if not url or "f-takken.com" not in url:
            continue
        to_enrich.append((i, parts, url))

    if not to_enrich:
        return 0

    print(f"  ふれんず enrichment: {len(to_enrich)}件の詳細ページを巡回")

    updated = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()

        # Visit listing page first to get session cookies
        try:
            page.goto(
                "https://www.f-takken.com/freins/buy/mansion/area?locate[]=40132&data_409=1",
                timeout=60000,
            )
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
        except Exception as e:
            print(f"  [WARN] Failed to load listing page: {e}")
            browser.close()
            return 0

        for idx, parts, url in to_enrich:
            try:
                page.goto(url, timeout=20000)
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(1)
                text = page.inner_text("body")
            except Exception as e:
                print(f"    [WARN] {parts[1][:25]}: {e}")
                time.sleep(1)
                continue

            fee_text = _parse_ftakken_fee(text)
            if fee_text:
                parts[10] = fee_text
                lines[idx] = "|".join(parts)
                updated += 1
                print(f"    {parts[1][:25]} → {fee_text}")
            else:
                print(f"    {parts[1][:25]} → データなし")

            time.sleep(0.5)

        browser.close()

    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def main():
    print("=== 管理費enrichment開始 ===\n")

    targets = sorted(DATA_DIR.glob("*_raw.txt"))

    total = 0
    for f in targets:
        if f.exists():
            print(f"\n--- {f.name} ---")
            if "ftakken" in f.name:
                count = enrich_ftakken_file(f)
            else:
                count = enrich_file(f)
            total += count
            print(f"  → {count}件 enriched")

    print(f"\n=== 完了: {total}件 enriched ===")


if __name__ == "__main__":
    main()
