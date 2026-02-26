#!/usr/bin/env python3
"""
ふれんず（f-takken.com）物件検索スクリプト
Playwrightでヘッドレスブラウザを使い、JS描画のページからデータを取得。
"""

import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

SEARCH_CONFIGS = {
    "fukuoka": {
        "label": "福岡",
        "wards": {
            "博多区": "40132",
            "中央区": "40133",
            "南区": "40134",
        },
        # Form action URL that returns actual property listings
        "items_url": "https://www.f-takken.com/freins/buy/mansion/area/items",
    },
}

PRICE_MAX = 5000  # 万円
AREA_MIN = 40
AREA_MAX = 70


def _parse_property_blocks(page_text: str, ward_name: str, detail_urls: list[str]) -> list[dict]:
    """Parse structured property listing text from f-takken items page.

    The text structure is:
      [header/description] 物件の詳細を見る [details: 所在地, 交通, 専有面積, 価格...]
      [next description] 物件の詳細を見る [next details...]

    So after splitting by "物件の詳細を見る", the property DETAILS are at the
    START of blocks[1], blocks[2], etc. The description is at the END of each block.
    """
    properties = []

    blocks = page_text.split("物件の詳細を見る")

    # blocks[0] = header + first property description (no details)
    # blocks[1] = first property details + second property description
    # blocks[N] = Nth property details + (N+1)th description
    # blocks[-1] = last property details + footer

    for idx in range(1, len(blocks)):
        try:
            block = blocks[idx]
            # Also include the description from the previous block (end part)
            prev_desc = blocks[idx - 1].split("\n")[-10:]  # Last 10 lines = description
            full_block = "\n".join(prev_desc) + "\n" + block

            prop = _parse_single_block(full_block, ward_name, detail_urls, idx - 1)
            if prop:
                properties.append(prop)
        except Exception:
            continue

    return properties


def _parse_single_block(block: str, ward_name: str, detail_urls: list[str], idx: int) -> dict | None:
    """Parse a single property block text."""
    # Price - match "価格\t1,980万円" or "価格\t320万円" etc.
    price_m = re.search(r"価格\s+(\d[\d,]+)\s*万円", block)
    if not price_m:
        price_m = re.search(r"(\d[\d,]+)\s*万円", block)
    if not price_m:
        return None

    price_str = price_m.group(1).replace(",", "")
    try:
        price_man = int(price_str)
    except ValueError:
        return None

    if price_man > PRICE_MAX or price_man <= 100:
        return None

    # Area (専有面積)
    area_m = re.search(r"専有面積\s*(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", block)
    if not area_m:
        area_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", block)
    if not area_m:
        return None

    area_val = float(area_m.group(1))
    if area_val < AREA_MIN or area_val > AREA_MAX:
        return None
    area_text = f"{area_val}㎡"

    # Location (所在地)
    loc_m = re.search(r"所在地\s*(福岡[^\s\n\t]+?)(?:\s+\S+\s*mapを見る|\s*map)", block)
    if not loc_m:
        loc_m = re.search(r"所在地\s*([^\n\t]+?)(?:\s*mapを見る|\s*map|\t)", block)
    if loc_m:
        location = loc_m.group(1).strip()
        # Extract building name from location line
        # Format: "福岡市博多区美野島２丁目 メゾン・ド・ルソール"
        loc_parts = location.split()
        address = loc_parts[0] if loc_parts else location
        building_name = " ".join(loc_parts[1:]) if len(loc_parts) > 1 else ""
    else:
        location = f"福岡市{ward_name}"
        address = location
        building_name = ""

    # Station/access (交通)
    station_m = re.search(r"交通\s*([^\n]+)", block)
    station_text = ""
    if station_m:
        station_info = station_m.group(1).strip()
        # Extract first line of station info (primary access)
        station_text = station_info.split("\n")[0].strip()
        # Clean up: extract "LINE STATION 徒歩N分" pattern
        walk_m = re.search(r"([^\s]+(?:駅|線)[^\n]*?徒歩\s*\d+\s*分)", station_text)
        if walk_m:
            station_text = walk_m.group(1)

    # Year built (築年月)
    built_m = re.search(r"築年月\s*(\d{4})\s*\[.*?\]\s*年\s*(\d{1,2})\s*月", block)
    if not built_m:
        built_m = re.search(r"築年月\s*(\d{4}).*?年\s*(\d{1,2})\s*月", block)
    if built_m:
        built_text = f"{built_m.group(1)}年{built_m.group(2)}月"
    else:
        year_m = re.search(r"(\d{4})\s*(?:\[.*?\])?\s*年", block)
        built_text = f"{year_m.group(1)}年" if year_m else ""

    # Layout (間取り)
    layout_m = re.search(r"(\d[SLDK]+(?:\+S)?)", block)
    if not layout_m:
        # Also match ワンルーム
        if "ワンルーム" in block:
            layout = "ワンルーム"
        else:
            layout = ""
    else:
        layout = layout_m.group(1)

    # Property name: use building name from location, or first descriptive line
    name = building_name
    if not name:
        lines = block.strip().split("\n")
        for line in lines:
            line = line.strip()
            if (len(line) >= 3 and not line.startswith("中古") and not line.startswith("新築")
                    and "万円" not in line and "㎡" not in line and "坪" not in line
                    and "閲覧回数" not in line and "所在地" not in line
                    and "交通" not in line and "築年月" not in line
                    and "チェック" not in line and "お気に入り" not in line):
                name = line[:50]
                break
    if not name:
        name = f"ふれんず物件({ward_name})"

    # URL
    url = ""
    if idx < len(detail_urls):
        url = detail_urls[idx]
    if not url:
        url = f"https://www.f-takken.com/freins/buy/mansion/area/items?locate[]={ward_name}"

    # Pet info
    pet = ""
    if "ペット可" in block or "ペット飼育可" in block:
        pet = "可"
    elif "ペット相談" in block:
        pet = "相談可"
    elif "ペット不可" in block or "ペット飼育不可" in block:
        pet = "不可"

    # Maintenance fee (管理費+修繕積立金)
    maintenance = ""
    total_fee = 0
    kanri_m = re.search(r"管理費[^\d]*?([\d,]+)\s*円", block)
    shuuzen_m = re.search(r"修繕積立金[^\d]*?([\d,]+)\s*円", block)
    if kanri_m:
        total_fee += int(kanri_m.group(1).replace(",", ""))
    if shuuzen_m:
        total_fee += int(shuuzen_m.group(1).replace(",", ""))
    if total_fee > 0:
        maintenance = str(total_fee)

    return {
        "source": "ふれんず",
        "name": name,
        "price_text": f"{price_man}万円",
        "location": address,
        "area_text": area_text,
        "built_text": built_text,
        "station_text": station_text,
        "layout": layout,
        "pet": pet,
        "brokerage": "",
        "maintenance": maintenance,
        "url": url,
    }


def scrape_ward(page, items_url: str, ward_code: str, ward_name: str) -> list[dict]:
    """Scrape property listings for a specific ward."""
    # Use the items URL with limit=100 and price/area filters
    # data_22=price upper, data_30=area min, data_31=area max, data_409=1 exclude owner-change
    url = (f"{items_url}?locate[]={ward_code}&limit=100"
           f"&data_22={PRICE_MAX}&data_30={AREA_MIN}&data_31={AREA_MAX}"
           f"&data_409=1")
    print(f"  {ward_name} ({url})")

    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=45000)
        time.sleep(3)
    except PlaywrightTimeout:
        print(f"    [WARN] Timeout loading {ward_name}")
        return []

    all_properties = []
    page_num = 1
    max_pages = 10  # Safety limit

    while page_num <= max_pages:
        # Get page text and detail URLs
        page_text = page.inner_text("body") if page.query_selector("body") else ""
        if not page_text or len(page_text) < 100:
            break

        # Extract detail URLs via data-id attributes on property list items
        property_items = page.query_selector_all('li.item.list-tpl[data-id]')
        detail_urls = []
        seen = set()
        for item in property_items:
            try:
                bno = item.get_attribute("data-id") or ""
                if bno and bno not in seen:
                    seen.add(bno)
                    detail_urls.append(f"https://www.f-takken.com/freins/items/{bno}")
            except Exception:
                continue

        # Parse property blocks
        properties = _parse_property_blocks(page_text, ward_name, detail_urls)
        print(f"    Page {page_num}: {len(properties)}件 (detail URLs: {len(detail_urls)})")

        if not properties:
            break

        all_properties.extend(properties)

        # Check for next page
        next_page = page_num + 1
        next_btn = page.query_selector(f'a[href="#page-{next_page}"]')
        if not next_btn:
            break

        try:
            next_btn.click()
            time.sleep(2)
            # Wait for content update
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)
        except Exception:
            break

        page_num += 1

    return all_properties


def search_ftakken(city_key: str = "fukuoka") -> list[dict]:
    """Search f-takken.com using Playwright headless browser."""
    config = SEARCH_CONFIGS.get(city_key)
    if not config:
        print(f"No config for {city_key}")
        return []

    print(f"\n=== ふれんず ({config['label']}) 検索中... ===")

    all_properties = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = context.new_page()

        for ward_name, ward_code in config["wards"].items():
            try:
                props = scrape_ward(page, config["items_url"], ward_code, ward_name)
                all_properties.extend(props)
                print(f"    → 合計 {len(props)}件")
            except Exception as e:
                print(f"    [ERROR] {ward_name}: {e}")
            time.sleep(2)

        browser.close()

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for prop in all_properties:
        url = prop["url"]
        if url not in seen_urls:
            seen_urls.add(url)
            unique.append(prop)

    print(f"\n  ふれんず 合計: {len(unique)}件 (重複除去前: {len(all_properties)}件)")
    return unique


def save_results(properties: list[dict], city_key: str) -> Path:
    """Save results to pipe-delimited data file."""
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"ftakken_{city_key}_raw.txt"

    config = SEARCH_CONFIGS[city_key]
    lines = [
        f"## ふれんず(f-takken.com) 検索結果 - {config['label']}",
        f"## 条件: {PRICE_MAX}万以下, {AREA_MIN}-{AREA_MAX}㎡",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(properties)}件",
        "",
    ]

    for prop in properties:
        line = "|".join([
            prop["source"],
            prop["name"],
            prop["price_text"],
            prop["location"],
            prop["area_text"],
            prop["built_text"],
            prop["station_text"],
            prop["layout"],
            prop["pet"],
            prop["brokerage"],
            prop.get("maintenance", ""),
            prop["url"],
        ])
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main():
    print(f"ふれんず物件検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    props = search_ftakken("fukuoka")
    if props:
        out = save_results(props, "fukuoka")
        print(f"\n出力: {out}")
    else:
        print("\n物件データが取得できませんでした")
        # Save empty file to clear stale data
        DATA_DIR.mkdir(exist_ok=True)
        out_path = DATA_DIR / "ftakken_fukuoka_raw.txt"
        out_path.write_text(
            f"## ふれんず(f-takken.com) 検索結果 - 福岡\n"
            f"## 条件: {PRICE_MAX}万以下, {AREA_MIN}-{AREA_MAX}㎡\n"
            f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"## 件数: 0件\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
