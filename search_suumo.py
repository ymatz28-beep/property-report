#!/usr/bin/env python3
"""
SUUMOスクレイパー（大阪・福岡・東京共通）
区ごとの一覧ページから物件情報を取得し、詳細ページから管理費+修繕積立金も取得。

出力フォーマット (12列):
source|name|price|location|area|built|station|layout|pet|brokerage|maintenance|url
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

# Ward configurations: slug -> display name
WARD_CONFIGS = {
    "osaka": {
        "area_code": "060",  # Kinki
        "pref_code": "27",
        "wards": {
            "sc_osakashikita": "北区",
            "sc_osakashinishi": "西区",
            "sc_osakashichuo": "中央区",
            "sc_osakashifukushima": "福島区",
        },
        "pref_slug": "osaka",
    },
    "fukuoka": {
        "area_code": "090",  # Kyushu
        "pref_code": "40",
        "wards": {
            "sc_fukuokashihakata": "博多区",
            "sc_fukuokashichuo": "中央区",
            "sc_fukuokashiminami": "南区",
        },
        "pref_slug": "fukuoka",
    },
    "tokyo": {
        "area_code": "030",  # Kanto
        "pref_code": "13",
        "wards": {
            "sc_shibuya": "渋谷区",
            "sc_shinjuku": "新宿区",
            "sc_meguro": "目黒区",
            "sc_toshima": "豊島区",
            "sc_taito": "台東区",
            "sc_nakano": "中野区",
            "sc_bunkyo": "文京区",
            "sc_minato": "港区",
            "sc_shinagawa": "品川区",
            "sc_sumida": "墨田区",
        },
        "pref_slug": "tokyo",
    },
}

PRICE_MAX_MAN = 5000
AREA_MIN = 40
AREA_MAX = 70


def fetch_page(url: str, retries: int = 2) -> str | None:
    """Fetch URL with retries and rate limiting."""
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except HTTPError as e:
            if e.code == 403:
                print(f"  [WARN] 403 Forbidden: {url[:80]}")
                return None
            if e.code == 429 and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            print(f"  [WARN] HTTP {e.code}: {url[:80]}")
            return None
        except (URLError, TimeoutError, ConnectionResetError, OSError) as e:
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            print(f"  [WARN] Connection error: {e}")
            return None
    return None


def build_search_url(pref_slug: str, ward_slug: str, page: int = 1) -> str:
    """Build SUUMO ward-based search URL with pet filter."""
    base = f"https://suumo.jp/ms/chuko/{pref_slug}/{ward_slug}/"
    params = f"?pc=100&page={page}"
    # Note: SUUMO ward-based URLs don't support inline price/area filters.
    # We filter client-side after parsing.
    return base + params


def parse_listing_page(html: str) -> list[dict]:
    """Parse SUUMO listing page for property cards."""
    properties = []
    cards = re.split(r'<div class="property_unit[ "]', html)

    for card in cards[1:]:  # Skip first (before first card)
        # Skip sponsored/ad listings
        if 'property_unit--osusume' in card[:100]:
            continue

        # Detail URL
        url_m = re.search(r'href="(/ms/chuko/[^"]+/nc_\d+/)"', card)
        if not url_m:
            continue
        detail_path = url_m.group(1)
        detail_url = f"https://suumo.jp{detail_path}"

        # Property name
        name = ""
        name_m = re.search(r'物件名</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if name_m:
            name = name_m.group(1).strip()

        # Price
        price_m = re.search(r'class="dottable-value">\s*([^<]+)</span>', card)
        if not price_m:
            continue
        price_text = price_m.group(1).strip()
        price_man = _parse_price_man(price_text)
        if price_man <= 0 or price_man > PRICE_MAX_MAN:
            continue

        # Location
        location = ""
        loc_m = re.search(r'所在地</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if loc_m:
            location = loc_m.group(1).strip()

        # Station
        station = ""
        sta_m = re.search(r'沿線・駅</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if sta_m:
            station = sta_m.group(1).strip()

        # Area (m<sup>2</sup> pattern)
        area_text = ""
        area_m = re.search(r'専有面積</dt>\s*<dd[^>]*>([\d.]+)\s*m', card, re.DOTALL)
        if area_m:
            area_val = float(area_m.group(1))
            if area_val < AREA_MIN or area_val > AREA_MAX:
                continue
            # Get full text including 坪 etc.
            area_full_m = re.search(r'専有面積</dt>\s*<dd[^>]*>(.+?)</dd>', card, re.DOTALL)
            if area_full_m:
                area_text = re.sub(r'<[^>]+>', '', area_full_m.group(1)).strip()
            else:
                area_text = f"{area_val}m2"

        # Layout
        layout = ""
        layout_m = re.search(r'間取り</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if layout_m:
            layout = layout_m.group(1).strip()

        # Built year
        built = ""
        built_m = re.search(r'築年月</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if built_m:
            built = built_m.group(1).strip()

        if not name:
            name = f"SUUMO物件"

        properties.append({
            "name": name,
            "price_text": f"{price_man}万円",
            "price_man": price_man,
            "location": location,
            "area_text": area_text,
            "built_text": built,
            "station_text": station,
            "layout": layout,
            "url": detail_url,
        })

    return properties


def enrich_detail(url: str) -> dict:
    """Fetch detail page and extract management fee + pet status."""
    result = {"maintenance": "", "pet": ""}
    html = fetch_page(url)
    if not html:
        return result

    # Management fee (管理費) + Repair reserve (修繕積立金)
    # HTML structure: 管理費</div>...(hints etc)...</th><td class="...">1万3210円／月...</td>
    def _parse_suumo_yen(text: str) -> int:
        text = text.replace(",", "").replace("，", "").strip()
        m = re.search(r"(\d+)万(\d*)円", text)
        if m:
            return int(m.group(1)) * 10000 + (int(m.group(2)) if m.group(2) else 0)
        m2 = re.search(r"(\d+)円", text)
        return int(m2.group(1)) if m2 else 0

    kanri = 0
    shuuzen = 0
    kanri_m = re.search(r'管理費</div>.*?</th>\s*<td[^>]*>(.*?)</td>', html, re.DOTALL)
    if kanri_m:
        kanri = _parse_suumo_yen(kanri_m.group(1))
    shuuzen_m = re.search(r'修繕積立金</div>.*?</th>\s*<td[^>]*>(.*?)</td>', html, re.DOTALL)
    if shuuzen_m:
        shuuzen = _parse_suumo_yen(shuuzen_m.group(1))
    if kanri > 0 and shuuzen > 0:
        result["maintenance"] = f"管理費{kanri}+修繕{shuuzen}"
    elif kanri > 0:
        result["maintenance"] = f"管理費{kanri}"
    elif shuuzen > 0:
        result["maintenance"] = f"修繕{shuuzen}"

    # Pet status from tokuchoPickupList
    tokucho_m = re.search(r'tokuchoPickupList\s*:\s*\[([^\]]+)\]', html)
    if tokucho_m:
        tokucho = tokucho_m.group(1)
        if "ペット可" in tokucho:
            result["pet"] = "可"
        elif "ペット相談" in tokucho:
            result["pet"] = "相談可"

    return result


def _parse_price_man(text: str) -> int:
    """Parse SUUMO price text to 万円 integer. Handles 億 format."""
    text = text.replace(",", "").replace("　", "").strip()
    # Handle 億 format: "1億1000万円" -> 11000, "2億円" -> 20000
    oku_m = re.search(r"(\d+)\s*億\s*(?:(\d+)\s*万)?円?", text)
    if oku_m:
        oku = int(oku_m.group(1)) * 10000
        man = int(oku_m.group(2)) if oku_m.group(2) else 0
        return oku + man
    m = re.search(r"(\d+)\s*万円", text)
    if m:
        return int(m.group(1))
    return 0


def get_total_count(html: str) -> int:
    """Extract total result count from pagination."""
    m = re.search(r'class="pagination_set-hit">\s*([\d,]+)\s*<span>件', html)
    if m:
        return int(m.group(1).replace(",", ""))
    return 0


def scrape_ward(pref_slug: str, ward_slug: str, ward_name: str, enrich: bool = True) -> list[dict]:
    """Scrape all pages for a single ward."""
    print(f"\n  {ward_name} ({ward_slug}) 検索中...")
    all_props = []
    page = 1
    max_pages = 10  # Safety limit

    while page <= max_pages:
        url = build_search_url(pref_slug, ward_slug, page)
        html = fetch_page(url)
        if not html:
            break

        if page == 1:
            total = get_total_count(html)
            print(f"    合計: {total}件")

        props = parse_listing_page(html)
        if not props:
            break

        all_props.extend(props)
        print(f"    Page {page}: {len(props)}件 (累計: {len(all_props)}件)")

        # Check for next page
        if f"page={page + 1}" not in html:
            break

        page += 1
        time.sleep(1.5)

    # Enrich with detail page (management fee + pet)
    if enrich and all_props:
        print(f"    詳細ページから管理費取得中... ({len(all_props)}件)")
        enriched_count = 0

        def _fetch_detail(idx_prop):
            idx, prop = idx_prop
            time.sleep(idx * 0.2)  # stagger to avoid burst (0.2s * worker_count ≒ 1s effective)
            return idx, enrich_detail(prop["url"])

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_fetch_detail, (i, p)): i for i, p in enumerate(all_props)}
            done = 0
            for future in as_completed(futures):
                idx, detail = future.result()
                all_props[idx]["maintenance"] = detail["maintenance"]
                all_props[idx]["pet"] = detail["pet"]
                if detail["maintenance"]:
                    enriched_count += 1
                done += 1
                if done % 10 == 0:
                    print(f"      {done}/{len(all_props)} 完了 (管理費: {enriched_count}件)")
        print(f"    管理費取得: {enriched_count}/{len(all_props)}件")

    return all_props


def search_suumo(city_key: str, enrich: bool = True) -> list[dict]:
    """Search SUUMO for all wards in a city."""
    config = WARD_CONFIGS.get(city_key)
    if not config:
        print(f"No SUUMO config for {city_key}")
        return []

    pref_slug = config["pref_slug"]
    print(f"\n=== SUUMO ({city_key}) 検索中... ===")

    all_properties = []
    for ward_slug, ward_name in config["wards"].items():
        props = scrape_ward(pref_slug, ward_slug, ward_name, enrich=enrich)
        all_properties.extend(props)
        time.sleep(2)  # Delay between wards

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for p in all_properties:
        if p["url"] not in seen_urls:
            seen_urls.add(p["url"])
            deduped.append(p)

    dup_count = len(all_properties) - len(deduped)
    if dup_count > 0:
        print(f"  重複除外: {dup_count}件")
    print(f"  SUUMO {city_key} 合計: {len(deduped)}件")
    return deduped


def save_results(properties: list[dict], city_key: str) -> Path:
    """Save results to pipe-delimited data file (12-column format)."""
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"suumo_{city_key}_raw.txt"

    lines = [
        f"## SUUMO検索結果 - {city_key}",
        f"## 条件: {PRICE_MAX_MAN}万以下, {AREA_MIN}-{AREA_MAX}㎡",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(properties)}件",
        "",
    ]

    for prop in properties:
        line = "|".join([
            "SUUMO",
            prop["name"],
            prop["price_text"],
            prop["location"],
            prop["area_text"],
            prop["built_text"],
            prop["station_text"],
            prop["layout"],
            prop.get("pet", ""),
            "",  # brokerage
            prop.get("maintenance", ""),
            prop["url"],
        ])
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main():
    """Search all target cities."""
    print(f"SUUMO物件検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"条件: {PRICE_MAX_MAN}万以下, {AREA_MIN}-{AREA_MAX}㎡")

    for city_key in ["osaka", "fukuoka", "tokyo"]:
        props = search_suumo(city_key)
        if props:
            out = save_results(props, city_key)
            print(f"  出力: {out}")
        else:
            save_results([], city_key)
            print(f"  条件に合う物件なし")


if __name__ == "__main__":
    main()
