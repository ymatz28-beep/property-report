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

import sys

sys.path.insert(0, str(BASE_DIR))
from investment_criteria import (
    KODATE_AREA_MIN as _KODATE_AREA_MIN,
    KODATE_PRICE_MAX_MAN as _KODATE_PRICE_MAX_MAN,
    KUBUN_AREA_MIN as _KUBUN_AREA_MIN,
    KUBUN_PRICE_MAX_MAN as _KUBUN_PRICE_MAX_MAN,
)

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

PRICE_MAX_MAN = _KUBUN_PRICE_MAX_MAN
AREA_MIN = _KUBUN_AREA_MIN
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
            if e.code in (429, 503) and attempt < retries:
                time.sleep(8 * (attempt + 1))
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
        # Note: property_unit--osusume was previously treated as sponsored/ad,
        # but SUUMO now uses this class for all recommended (affordable) listings.
        # Do NOT skip it — these are regular properties.

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
            area_text = f"{area_val}㎡"

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
            name = "SUUMO物件"

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
            # STRUCTURAL CANARY: SUUMO reports results but our CSS selector is gone.
            # If SUUMO has listings but 'property_unit' doesn't appear at all,
            # the HTML class name changed — same root cause as the 6-day silent failure.
            if total > 10 and 'class="property_unit' not in html:
                import sys as _sys
                _sys.stderr.write(
                    f"  [CANARY:STRUCTURE_CHANGE] {ward_name}: SUUMO={total}件を表示しているが"
                    f"'property_unit'クラスが消滅 — HTMLクラス名変更の疑い (要パーサー修正)\n"
                )
                print(f"  [CANARY:STRUCTURE_CHANGE] {ward_name}: 0件 (構造変化検知)")

        props = parse_listing_page(html)

        # PARSE CANARY: SUUMO says it has listings but we parsed none.
        # Triggers when class exists but field extraction regexes stopped matching.
        if page == 1 and total > 10 and not props and 'class="property_unit' in html:
            import sys as _sys
            _sys.stderr.write(
                f"  [CANARY:PARSE_ZERO] {ward_name}: property_unitは存在するが"
                f"0件解析 — フィールドの正規表現が壊れた可能性\n"
            )
            print(f"  [CANARY:PARSE_ZERO] {ward_name}: 0件 (解析失敗)")

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
            # Stagger the initial 5 worker slots to avoid burst; subsequent tasks
            # rely on pool cycling cadence (HTTP roundtrip ~2s is spacing enough).
            # Old: idx * 0.2 → O(n²) total sleep; task #300 slept 60s before any request.
            time.sleep(idx * 0.2 if idx < 5 else 0)
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

    # Guard: never overwrite existing data with 0 results (scrape failure).
    # Exits with code 2 so the caller (patrol script) can detect stale data
    # and distinguish it from a clean scrape (exit 0).
    if not properties and out_path.exists():
        existing_lines = [l for l in out_path.read_text(encoding="utf-8").splitlines()
                         if l and not l.startswith("#")]
        if existing_lines:
            # Check how stale the existing data is
            import re as _re
            content = out_path.read_text(encoding="utf-8")
            date_m = _re.search(r"## 取得日: (\d{4}-\d{2}-\d{2})", content)
            stale_days = 0
            if date_m:
                from datetime import date as _date
                last_date = _date.fromisoformat(date_m.group(1))
                stale_days = (_date.today() - last_date).days
            print(f"  [GUARD:STALE] {out_path.name}: 0件取得 — 既存{len(existing_lines)}件を保護 (データ {stale_days}日前)")
            import sys as _sys
            _sys.exit(2)  # exit code 2 = guard fired (stale data preserved)

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


# --- 戸建て (中古一戸建て) — separate URL tree (/chukoikkodate/) and filters ---
# 区分マンションと違い管理規約が無いため、面積帯はマンション枠(40-70㎡)より広め。
# 価格上限は investment_criteria.py が正 (Yuma指定、2026-07-08時点で2999万)
KODATE_PRICE_MAX_MAN = _KODATE_PRICE_MAX_MAN
KODATE_AREA_MIN = _KODATE_AREA_MIN


def build_search_url_kodate(pref_slug: str, ward_slug: str, page: int = 1) -> str:
    """Build SUUMO 中古一戸建て ward-based search URL."""
    return f"https://suumo.jp/chukoikkodate/{pref_slug}/{ward_slug}/?pc=100&page={page}"


def parse_listing_page_kodate(html: str) -> list[dict]:
    """Parse SUUMO 中古一戸建て listing page for property cards."""
    properties = []
    cards = re.split(r'<div class="property_unit[ "]', html)

    for card in cards[1:]:
        url_m = re.search(r'href="(/chukoikkodate/[^"]+/nc_\d+/)"', card)
        if not url_m:
            continue
        detail_url = f"https://suumo.jp{url_m.group(1)}"

        name = ""
        name_m = re.search(r'物件名</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if name_m:
            name = name_m.group(1).strip()

        price_m = re.search(r'class="dottable-value">\s*([^<]+)</span>', card)
        if not price_m:
            continue
        price_text = price_m.group(1).strip()
        price_man = _parse_price_man(price_text)
        if price_man <= 0 or price_man > KODATE_PRICE_MAX_MAN:
            continue

        location = ""
        loc_m = re.search(r'所在地</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if loc_m:
            location = loc_m.group(1).strip()

        station = ""
        sta_m = re.search(r'沿線・駅</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if sta_m:
            station = sta_m.group(1).strip()

        # 建物面積 (building floor area) — houses list land + building area separately;
        # building area is the closer analog to マンション's 専有面積.
        area_text = ""
        area_m = re.search(r'建物面積</dt>\s*<dd[^>]*>([\d.]+)\s*m', card, re.DOTALL)
        if area_m:
            area_val = float(area_m.group(1))
            if area_val < KODATE_AREA_MIN:
                continue
            area_text = f"{area_val}㎡"

        layout = ""
        layout_m = re.search(r'間取り</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if layout_m:
            layout = layout_m.group(1).strip()

        built = ""
        built_m = re.search(r'築年月</dt>\s*<dd[^>]*>([^<]+)</dd>', card, re.DOTALL)
        if built_m:
            built = built_m.group(1).strip()

        if not name:
            name = "SUUMO戸建て"

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
            # 戸建ては区分所有と違い管理規約が存在しない(建物を丸ごと所有)ため、
            # ペット可否は所有者判断。「不明=不可寄り」のスコア減点対象から外すため明示的に可とする。
            "pet": "可",
        })

    return properties


def check_kodate_land_rights(url: str) -> str:
    """Fetch 戸建て detail page and return the 土地の権利形態 text.

    List-page cards never expose this field (confirmed empty on a live
    fetch); it only appears in the detail page's spec table, so a filter
    on it requires this extra request per candidate.
    """
    html = fetch_page(url)
    if not html:
        return ""
    m = re.search(r"土地の権利形態</div>.*?</th>\s*<td[^>]*>(.*?)</td>", html, re.DOTALL)
    if not m:
        return ""
    return re.sub(r"\s+", "", m.group(1))


def scrape_ward_kodate(pref_slug: str, ward_slug: str, ward_name: str) -> list[dict]:
    """Scrape all pages of 中古一戸建て listings for a single ward."""
    print(f"\n  {ward_name} ({ward_slug}) 戸建て検索中...")
    all_props = []
    page = 1
    max_pages = 10

    while page <= max_pages:
        url = build_search_url_kodate(pref_slug, ward_slug, page)
        html = fetch_page(url)
        if not html:
            break

        props = parse_listing_page_kodate(html)
        if not props:
            break

        for prop in props:
            land_rights = check_kodate_land_rights(prop["url"])
            time.sleep(1.0)
            if any(kw in land_rights for kw in ("賃借権", "借地権", "地上権")):
                print(f"    除外(借地権): {prop['name']} {prop['price_text']} — {land_rights}")
                continue
            all_props.append(prop)

        print(f"    Page {page}: {len(props)}件 (累計: {len(all_props)}件)")

        if f"page={page + 1}" not in html:
            break

        page += 1
        time.sleep(1.5)

    return all_props


def search_suumo_kodate(city_key: str) -> list[dict]:
    """Search SUUMO 中古一戸建て for all wards in a city."""
    config = WARD_CONFIGS.get(city_key)
    if not config:
        print(f"No SUUMO config for {city_key}")
        return []

    pref_slug = config["pref_slug"]
    print(f"\n=== SUUMO戸建て ({city_key}) 検索中... ===")

    all_properties = []
    for ward_slug, ward_name in config["wards"].items():
        props = scrape_ward_kodate(pref_slug, ward_slug, ward_name)
        all_properties.extend(props)
        time.sleep(2)

    seen_urls = set()
    deduped = []
    for p in all_properties:
        if p["url"] not in seen_urls:
            seen_urls.add(p["url"])
            deduped.append(p)

    dup_count = len(all_properties) - len(deduped)
    if dup_count > 0:
        print(f"  重複除外: {dup_count}件")
    print(f"  SUUMO戸建て {city_key} 合計: {len(deduped)}件")
    return deduped


def save_results_kodate(properties: list[dict], city_key: str) -> Path:
    """Save 戸建て results to pipe-delimited data file (12-column format, source=SUUMO(戸建))."""
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"suumo_kodate_{city_key}_raw.txt"

    if not properties and out_path.exists():
        existing_lines = [l for l in out_path.read_text(encoding="utf-8").splitlines()
                         if l and not l.startswith("#")]
        if existing_lines:
            import re as _re
            content = out_path.read_text(encoding="utf-8")
            date_m = _re.search(r"## 取得日: (\d{4}-\d{2}-\d{2})", content)
            stale_days = 0
            if date_m:
                from datetime import date as _date
                last_date = _date.fromisoformat(date_m.group(1))
                stale_days = (_date.today() - last_date).days
            print(f"  [GUARD:STALE] {out_path.name}: 0件取得 — 既存{len(existing_lines)}件を保護 (データ {stale_days}日前)")
            import sys as _sys
            _sys.exit(2)

    lines = [
        f"## SUUMO戸建て検索結果 - {city_key}",
        f"## 条件: {KODATE_PRICE_MAX_MAN}万以下, {KODATE_AREA_MIN}㎡以上",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(properties)}件",
        "",
    ]

    for prop in properties:
        line = "|".join([
            "SUUMO(戸建)",
            prop["name"],
            prop["price_text"],
            prop["location"],
            prop["area_text"],
            prop["built_text"],
            prop["station_text"],
            prop["layout"],
            prop.get("pet", ""),
            "",  # brokerage
            "",  # maintenance — 戸建ては管理費/修繕積立金の概念なし
            prop["url"],
        ])
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main():
    """Search target cities. Optional first arg: city key (osaka/fukuoka/tokyo).

    Optional --mode kodate: search 中古一戸建て instead of マンション.
    """
    import sys as _sys
    args = _sys.argv[1:]
    mode = "mansion"
    if "--mode" in args:
        idx = args.index("--mode")
        mode = args[idx + 1]
        del args[idx:idx + 2]
    target_cities = [args[0]] if args and args[0] in WARD_CONFIGS else ["osaka", "fukuoka", "tokyo"]

    if mode == "kodate":
        print(f"SUUMO戸建て検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"条件: {KODATE_PRICE_MAX_MAN}万以下, {KODATE_AREA_MIN}㎡以上")
        print(f"対象都市: {', '.join(target_cities)}")
        for city_key in target_cities:
            props = search_suumo_kodate(city_key)
            if props:
                out = save_results_kodate(props, city_key)
                print(f"  出力: {out}")
            else:
                save_results_kodate([], city_key)
                print("  条件に合う物件なし")
        return

    print(f"SUUMO物件検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"条件: {PRICE_MAX_MAN}万以下, {AREA_MIN}-{AREA_MAX}㎡")
    print(f"対象都市: {', '.join(target_cities)}")

    for city_key in target_cities:
        props = search_suumo(city_key)
        if props:
            out = save_results(props, city_key)
            print(f"  出力: {out}")
        else:
            save_results([], city_key)
            print("  条件に合う物件なし")


if __name__ == "__main__":
    main()
