#!/usr/bin/env python3
"""
LIFULL HOME'S (homes.co.jp) 中古マンション検索スクリプト
Playwrightでヘッドレスブラウザを使用（403ブロック対策）。

出力フォーマット (12列):
source|name|price|location|area|built|station|layout|pet|brokerage|maintenance|url
"""

import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

PRICE_MAX = 5000  # 万円
AREA_MIN = 40
AREA_MAX = 70

WARD_SLUGS = {
    "osaka": {
        "北区": "osaka_kita-city",
        "西区": "osaka_nishi-city",
        "中央区": "osaka_chuo-city",
        "福島区": "osaka_fukushima-city",
    },
    "fukuoka": {
        "博多区": "fukuoka_hakata-city",
        "中央区": "fukuoka_chuo-city",
        "南区": "fukuoka_minami-city",
    },
    "tokyo": {
        "渋谷区": "shibuya-city",
        "新宿区": "shinjuku-city",
        "目黒区": "meguro-city",
        "豊島区": "toshima-city",
        "台東区": "taito-city",
        "中野区": "nakano-city",
        "文京区": "bunkyo-city",
        "港区": "minato-city",
        "品川区": "shinagawa-city",
        "墨田区": "sumida-city",
    },
}

PREF_SLUG = {
    "osaka": "osaka",
    "fukuoka": "fukuoka",
    "tokyo": "tokyo",
}

CITY_LABELS = {
    "osaka": "大阪",
    "fukuoka": "福岡",
    "tokyo": "東京",
}

TARGET_WARDS = {
    "osaka": ["北区", "西区", "中央区", "福島区"],
    "fukuoka": ["博多区", "中央区", "南区"],
    "tokyo": ["渋谷区", "新宿区", "目黒区", "豊島区", "台東区", "中野区", "文京区", "港区", "品川区", "墨田区"],
}


def _parse_lifull_page(page) -> list[dict]:
    """Parse LIFULL HOME'S listing page using Playwright page object."""
    properties = []

    # Get full page text for regex parsing
    page_text = page.inner_text("body") if page.query_selector("body") else ""
    if not page_text or len(page_text) < 100:
        return []

    # Get all property detail links
    links = page.query_selector_all('a[href*="/mansion/chuko/"]')
    seen_urls = set()

    for link in links:
        try:
            href = link.get_attribute("href") or ""
            # Property detail URLs contain a numeric ID segment
            if not re.search(r"/\d{8,}/", href):
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Get surrounding text from the card
            parent = link
            for _ in range(5):
                p = parent.evaluate("el => el.parentElement ? el.parentElement.outerHTML : ''")
                if len(p) > 200:
                    break
                parent_el = parent.evaluate_handle("el => el.parentElement")
                if parent_el:
                    parent = parent_el
            card_text = link.evaluate("el => { let p = el; for(let i=0;i<6;i++){if(p.parentElement)p=p.parentElement;} return p.innerText; }")
        except Exception:
            continue

        if not card_text or len(card_text) < 30:
            continue

        # Extract price
        price_m = re.search(r"([\d,]+)万円", card_text)
        if not price_m:
            continue
        price_man = int(price_m.group(1).replace(",", ""))
        if price_man <= 0 or price_man > PRICE_MAX:
            continue

        # Extract area
        area_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", card_text)
        area_text = f"{area_m.group(1)}㎡" if area_m else ""
        if area_m:
            area_val = float(area_m.group(1))
            if area_val < AREA_MIN or area_val > AREA_MAX:
                continue

        # Extract location
        loc_m = re.search(r"((?:大阪府|福岡県|東京都)[^\s\n]{3,25})", card_text)
        location = loc_m.group(1) if loc_m else ""

        # Extract year built
        year_m = re.search(r"(\d{4})年(?:\s*(\d{1,2})月)?(?:\s*築)?", card_text)
        built_text = year_m.group(0).strip() if year_m else ""

        # Extract station
        station_m = re.search(r"([^\s\n]*?(?:駅|線)[^\n]*?徒歩\s*\d+\s*分)", card_text)
        station_text = station_m.group(1).strip() if station_m else ""

        # Extract layout
        layout_m = re.search(r"(\d[SLDK]+(?:\+S)?)", card_text)
        layout = layout_m.group(1) if layout_m else ""

        # Extract name
        name = ""
        name_patterns = [
            r"([^\s\n]{2,}(?:マンション|コーポ|ハイツ|タワー|パーク|レジデンス|プラザ|コート|ハウス|ヒルズ|グラン|シティ|メゾン|ロイヤル|テラス)[^\s\n]{0,10})",
            r"([ァ-ヶー]{3,}[^\s\n]{0,15})",
        ]
        for pat in name_patterns:
            nm = re.search(pat, card_text)
            if nm:
                candidate = nm.group(1).strip()
                if len(candidate) >= 3:
                    name = candidate[:40]
                    break
        if not name:
            name = "LIFULL物件"

        # Pet
        pet = ""
        if "ペット可" in card_text:
            pet = "可"
        elif "ペット相談" in card_text:
            pet = "相談可"
        elif "ペット不可" in card_text:
            pet = "不可"

        # Maintenance fee
        maintenance = ""
        total_fee = 0
        kanri_m = re.search(r"管理費[^\d]*?([\d,]+)\s*円", card_text)
        shuuzen_m = re.search(r"修繕積立金[^\d]*?([\d,]+)\s*円", card_text)
        if kanri_m:
            total_fee += int(kanri_m.group(1).replace(",", ""))
        if shuuzen_m:
            total_fee += int(shuuzen_m.group(1).replace(",", ""))
        if total_fee > 0:
            maintenance = str(total_fee)

        # Full URL
        prop_url = href
        if not prop_url.startswith("http"):
            prop_url = f"https://www.homes.co.jp{prop_url}"

        properties.append({
            "source": "LIFULL",
            "name": name,
            "price_text": f"{price_man}万円",
            "location": location,
            "area_text": area_text,
            "built_text": built_text,
            "station_text": station_text,
            "layout": layout,
            "pet": pet,
            "brokerage": "",
            "maintenance": maintenance,
            "url": prop_url,
        })

    return properties


def search_lifull(city_key: str) -> list[dict]:
    """Search LIFULL HOME'S using Playwright headless browser."""
    slugs = WARD_SLUGS.get(city_key, {})
    pref = PREF_SLUG.get(city_key, "")
    label = CITY_LABELS.get(city_key, city_key)

    if not slugs:
        return []

    print(f"\n=== LIFULL HOME'S ({label}) 検索中... ===")
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

        for ward_name, ward_slug in slugs.items():
            url = (
                f"https://www.homes.co.jp/mansion/chuko/{pref}/{ward_slug}/list/"
                f"?PRICE_MAX={PRICE_MAX}&MENSEKI_FROM={AREA_MIN}&MENSEKI_TO={AREA_MAX}"
            )
            print(f"  {ward_name} 検索中...")

            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=20000)
                time.sleep(2)
            except PlaywrightTimeout:
                print(f"    [WARN] Timeout: {ward_name}")
                continue
            except Exception as e:
                print(f"    [ERROR] {ward_name}: {e}")
                continue

            ward_props = _parse_lifull_page(page)
            all_properties.extend(ward_props)
            print(f"    → {len(ward_props)}件")
            time.sleep(2)

        browser.close()

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for prop in all_properties:
        if prop["url"] not in seen_urls:
            seen_urls.add(prop["url"])
            unique.append(prop)

    print(f"  LIFULL 合計: {len(unique)}件")
    return unique


def save_results(properties: list[dict], city_key: str) -> Path:
    """Save results to pipe-delimited data file."""
    DATA_DIR.mkdir(exist_ok=True)
    label = CITY_LABELS.get(city_key, city_key)
    out_path = DATA_DIR / f"lifull_{city_key}_raw.txt"

    lines = [
        f"## LIFULL HOME'S 検索結果 - {label}",
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
    print(f"LIFULL HOME'S物件検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    for city_key in ["osaka", "fukuoka", "tokyo"]:
        props = search_lifull(city_key)
        if props:
            out = save_results(props, city_key)
            print(f"  出力: {out}")


if __name__ == "__main__":
    main()
