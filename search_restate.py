#!/usr/bin/env python3
"""
R不動産スクレイパー（東京・大阪・福岡共通）
各都市のR不動産サイトから売買物件を取得し、パイプ区切り形式で出力。

出力フォーマット (12列):
source|name|price|location|area|built|station|layout|pet|brokerage|maintenance|url
"""

import re
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

SITE_CONFIGS = {
    "osaka": {
        "label": "大阪",
        "source": "大阪R不動産",
        "base_url": "https://www.realosakaestate.jp",
    },
    "fukuoka": {
        "label": "福岡",
        "source": "福岡R不動産",
        "base_url": "https://www.realfukuokaestate.jp",
    },
    "tokyo": {
        "label": "東京",
        "source": "東京R不動産",
        "base_url": "https://www.realtokyoestate.co.jp",
    },
}

PRICE_MAX = 5000  # 万円
AREA_MIN = 40
AREA_MAX = 70


def fetch_page(url: str, retries: int = 2) -> str | None:
    """Fetch a URL with retries."""
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except HTTPError as e:
            if e.code == 403:
                print(f"  [WARN] 403: {url}")
                return None
            if e.code == 429 and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            print(f"  [WARN] HTTP {e.code}: {url}")
            return None
        except (URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(2)
                continue
            print(f"  [WARN] Connection error: {e}")
            return None
    return None


def parse_listing_page(html: str, base_url: str) -> list[dict]:
    """Parse property links from the listing page."""
    soup = BeautifulSoup(html, "html.parser")
    properties = []

    # Find all property links: <a href="/estate.php?n=...">
    links = soup.find_all("a", href=re.compile(r"/estate\.php\?n=\d+"))
    seen_ids = set()

    for link in links:
        href = link.get("href", "")
        m = re.search(r"n=(\d+)", href)
        if not m:
            continue
        prop_id = m.group(1)
        if prop_id in seen_ids:
            continue
        seen_ids.add(prop_id)

        # Check if it's a sale property (look for sale badge or price format)
        text = link.get_text(separator=" ", strip=True)

        # Skip rental-only listings (price like ¥XX,000/月 or 万円/月)
        if re.search(r"\d+円/月|賃料|/月", text):
            continue

        full_url = f"{base_url}/estate.php?n={prop_id}"
        properties.append({
            "id": prop_id,
            "url": full_url,
            "listing_text": text,
        })

    return properties


def parse_detail_page(html: str, prop_url: str, source_name: str) -> dict | None:
    """Parse property details from the detail page."""
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(separator="\n", strip=True)

    # Property name: prefer the descriptive h2/h3 title, fallback to <title>
    name = ""
    # R不動産 pages often have the listing name in a heading
    for heading in soup.find_all(["h1", "h2"]):
        text = heading.get_text(strip=True)
        # Skip generic headings
        if text and len(text) > 2 and "R不動産" not in text and "物件情報" not in text:
            name = text[:50]
            break
    if not name:
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Format: "【大阪R不動産】ADDRESS の売買物件/STATION" → clean it
            name = title_text.split("｜")[0].split("|")[0].strip()
            # Remove 【...R不動産】 prefix
            name = re.sub(r"【[^】]*R不動産】\s*", "", name)
            # Remove "の売買物件/..." suffix
            name = re.sub(r"の(?:売買|賃貸)物件.*", "", name).strip()

    # Price
    price_man = 0
    # Match: ¥26,500,000 or 2,650万円 or 26,500,000円
    price_m = re.search(r"(?:価格|販売価格)[^\d]*?([\d,]+)\s*万円", body_text)
    if price_m:
        try:
            price_man = int(price_m.group(1).replace(",", ""))
        except ValueError:
            pass
    if not price_man:
        price_m = re.search(r"(?:価格|販売価格)[^\d]*?[¥￥]?\s*([\d,]+)\s*円", body_text)
        if price_m:
            try:
                price_man = int(price_m.group(1).replace(",", "")) // 10000
            except ValueError:
                pass
    if not price_man:
        # Try broader pattern
        price_m = re.search(r"([\d,]+)\s*万円", body_text)
        if price_m:
            try:
                val = int(price_m.group(1).replace(",", ""))
                if 100 <= val <= PRICE_MAX:
                    price_man = val
            except ValueError:
                pass

    if not price_man or price_man > PRICE_MAX:
        return None

    # Area
    area_val = 0.0
    area_m = re.search(r"(?:専有面積|面積)[^\d]*?([\d.]+)\s*(?:m[²2]|㎡)", body_text)
    if area_m:
        area_val = float(area_m.group(1))
    if not area_val:
        area_m = re.search(r"([\d.]+)\s*(?:m[²2]|㎡)", body_text)
        if area_m:
            area_val = float(area_m.group(1))

    if area_val and (area_val < AREA_MIN or area_val > AREA_MAX):
        return None

    area_text = f"{area_val}㎡" if area_val else ""

    # Location
    location = ""
    loc_m = re.search(r"(?:所在地|住所)[^\n]*?\n\s*(.+?)(?:\n|$)", body_text)
    if loc_m:
        location = loc_m.group(1).strip()[:50]

    # Station/access
    station = ""
    sta_m = re.search(r"(?:交通|最寄駅|アクセス)[^\n]*?\n\s*(.+?)(?:\n|$)", body_text)
    if sta_m:
        station = sta_m.group(1).strip()[:60]
    if not station:
        # Try to find "駅 徒歩X分" pattern
        walk_m = re.search(r"([^\n]{2,30}駅[^\n]*?徒歩\s*\d+\s*分)", body_text)
        if walk_m:
            station = walk_m.group(1).strip()

    # Year built
    built = ""
    built_m = re.search(r"(?:築年|竣工|築年月)[^\d]*?(\d{4})\s*年", body_text)
    if built_m:
        built = f"{built_m.group(1)}年"

    # Layout
    layout = ""
    layout_m = re.search(r"(?:間取り)[^\n]*?\n?\s*(\d[SLDK]+(?:\+\S+)?|ワンルーム)", body_text)
    if layout_m:
        layout = layout_m.group(1)
    if not layout:
        layout_m = re.search(r"(\d[SLDK]+(?:\+\S+)?)", body_text)
        if layout_m:
            layout = layout_m.group(1)

    # Pet policy — check 不可 BEFORE 可 to avoid "ペット可否" label false positive
    pet = ""
    if "ペット不可" in body_text or "ペット飼育不可" in body_text:
        pet = "不可"
    elif "ペット相談" in body_text:
        pet = "相談可"
    elif re.search(r"ペット(?:飼育)?可(?!否)", body_text):
        pet = "可"

    # Maintenance fee (管理費+修繕積立金)
    maintenance = ""
    total_fee = 0
    kanri_m = re.search(r"管理費[^\d]*?([\d,]+)\s*円", body_text)
    shuuzen_m = re.search(r"修繕積立金[^\d]*?([\d,]+)\s*円", body_text)
    if kanri_m:
        total_fee += int(kanri_m.group(1).replace(",", ""))
    if shuuzen_m:
        total_fee += int(shuuzen_m.group(1).replace(",", ""))
    if total_fee > 0:
        maintenance = str(total_fee)

    return {
        "source": source_name,
        "name": name,
        "price_text": f"{price_man}万円",
        "location": location,
        "area_text": area_text,
        "built_text": built,
        "station_text": station,
        "layout": layout,
        "pet": pet,
        "brokerage": "",
        "maintenance": maintenance,
        "url": prop_url,
    }


def scrape_restate(city_key: str) -> list[dict]:
    """Scrape R不動産 sale listings for a city."""
    config = SITE_CONFIGS.get(city_key)
    if not config:
        print(f"No config for {city_key}")
        return []

    base_url = config["base_url"]
    source_name = config["source"]
    print(f"\n=== {source_name} 検索中... ===")

    # Fetch sale listings with pagination (type[]=2)
    candidates = []
    seen_ids = set()
    max_pages = 15

    for page_num in range(1, max_pages + 1):
        listing_url = f"{base_url}/estate_search.php?mode=all&type[]=2&page={page_num}"
        if page_num == 1:
            print(f"  Listing: {listing_url}")

        html = fetch_page(listing_url)
        if not html:
            break

        page_candidates = parse_listing_page(html, base_url)
        # Deduplicate across pages
        new_candidates = []
        for c in page_candidates:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                new_candidates.append(c)

        if not new_candidates:
            break

        candidates.extend(new_candidates)
        print(f"  Page {page_num}: {len(new_candidates)}件")
        time.sleep(1)

    print(f"  売買物件リンク合計: {len(candidates)}件")

    properties = []
    for i, cand in enumerate(candidates):
        time.sleep(1)  # Rate limiting
        print(f"  [{i + 1}/{len(candidates)}] {cand['url']}")

        detail_html = fetch_page(cand["url"])
        if not detail_html:
            continue

        prop = parse_detail_page(detail_html, cand["url"], source_name)
        if prop:
            properties.append(prop)
            print(f"    → {prop['name']} / {prop['price_text']} / {prop['area_text']}")
        else:
            print(f"    → スキップ (条件外)")

    print(f"  {source_name} 合計: {len(properties)}件")
    return properties


def save_results(properties: list[dict], city_key: str) -> Path:
    """Save results to pipe-delimited data file."""
    DATA_DIR.mkdir(exist_ok=True)
    config = SITE_CONFIGS[city_key]
    out_path = DATA_DIR / f"restate_{city_key}_raw.txt"

    lines = [
        f"## {config['source']} 検索結果",
        f"## 条件: {PRICE_MAX}万以下, {AREA_MIN}-{AREA_MAX}㎡",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(properties)}件",
        "",
    ]

    for prop in properties:
        line = "|".join([
            prop["source"], prop["name"], prop["price_text"],
            prop["location"], prop["area_text"], prop["built_text"],
            prop["station_text"], prop["layout"], prop["pet"],
            prop["brokerage"], prop.get("maintenance", ""), prop["url"],
        ])
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main():
    """Search all R不動産 sites."""
    print(f"R不動産 物件検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    for city_key in SITE_CONFIGS:
        props = scrape_restate(city_key)
        if props:
            out = save_results(props, city_key)
            print(f"  出力: {out}")
        else:
            save_results([], city_key)
            print(f"  条件に合う物件なし")


if __name__ == "__main__":
    main()
