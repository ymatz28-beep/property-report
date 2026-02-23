#!/usr/bin/env python3
"""
マルチサイト物件検索スクリプト
楽待・athome・Yahoo不動産等から物件情報を取得し、
SUUMOと同じパイプ区切り形式で出力する。

出力フォーマット (11列):
source|name|price|location|area|built|station|layout|pet|brokerage|url
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

# Area configurations matching CLAUDE.md search conditions
AREA_CONFIGS = {
    "osaka": {
        "label": "大阪",
        "rakumachi_area": "27",  # Osaka prefecture code
        "rakumachi_cities": ["osaka"],  # Osaka city
        "target_wards": ["北区", "西区", "中央区", "福島区"],
        "target_areas": [
            "北堀江", "南堀江", "中津", "中崎町", "南森町", "天神橋", "天満",
            "扇町", "東天満", "梅田", "大淀", "福島", "肥後橋", "淀屋橋",
            "北浜", "江戸堀", "阿波座", "靱公園", "靱本町", "長堀橋",
            "心斎橋", "谷町",
        ],
    },
    "fukuoka": {
        "label": "福岡",
        "rakumachi_area": "40",  # Fukuoka prefecture code
        "rakumachi_cities": ["fukuoka"],
        "target_wards": ["博多区", "中央区", "南区"],
        "target_areas": [
            "天神", "博多", "薬院", "平尾", "住吉", "祇園", "赤坂",
            "大濠", "渡辺通", "中洲",
        ],
    },
    "tokyo": {
        "label": "東京",
        "rakumachi_area": "13",  # Tokyo prefecture code
        "rakumachi_cities": ["tokyo"],
        "target_wards": [
            "渋谷区", "新宿区", "目黒区", "豊島区", "台東区",
            "中野区", "文京区", "港区", "品川区", "墨田区",
        ],
        "target_areas": [
            "渋谷", "新宿", "中目黒", "恵比寿", "代官山", "神宮前",
            "池袋", "大塚", "巣鴨", "浅草", "上野", "蔵前", "押上",
            "中野", "高円寺", "麻布", "白金", "三田", "五反田",
        ],
    },
}

# Price and area criteria from CLAUDE.md
PRICE_MAX = 50000000  # 5000万円
AREA_MIN = 40  # m2
AREA_MAX = 70  # m2


def fetch_page(url: str, retries: int = 2) -> str | None:
    """Fetch a URL with retries and rate limiting."""
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except HTTPError as e:
            if e.code == 403:
                print(f"  [WARN] 403 Forbidden: {url}")
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


def is_target_location(location: str, city_key: str) -> bool:
    """Check if property location matches target areas."""
    config = AREA_CONFIGS.get(city_key, {})
    wards = config.get("target_wards", [])
    areas = config.get("target_areas", [])
    return any(w in location for w in wards) or any(a in location for a in areas)


def parse_price_text(text: str) -> int:
    """Parse price text to 万円 integer."""
    text = text.replace(",", "").replace("　", "").strip()
    # Handle 億
    m_oku = re.search(r"(\d+(?:\.\d+)?)億", text)
    m_man = re.search(r"(\d+(?:\.\d+)?)万", text)
    total = 0
    if m_oku:
        total += int(float(m_oku.group(1)) * 10000)
    if m_man:
        total += int(float(m_man.group(1)))
    if total == 0:
        # Try raw number (in yen)
        m = re.search(r"(\d+)", text)
        if m and len(m.group(1)) >= 7:
            total = int(m.group(1)) // 10000
    return total


def parse_area_text(text: str) -> float:
    """Parse area text to float m2."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else 0


# ============================================================
# Rakumachi (楽待)
# ============================================================

def search_rakumachi(city_key: str) -> list[dict]:
    """Search 楽待 for investment properties (区分マンション)."""
    config = AREA_CONFIGS[city_key]
    area_code = config["rakumachi_area"]
    print(f"\n=== 楽待 ({config['label']}) 検索中... ===")

    # dim2001 = 区分マンション
    base_url = f"https://www.rakumachi.jp/syuuekibukken/area/prefecture/dim2001/"
    params = {
        "area": area_code,
        "pmax": str(PRICE_MAX // 10000),  # 楽待は万円単位
        "areamin": str(AREA_MIN),
        "areamax": str(AREA_MAX),
    }
    url = f"{base_url}?{urlencode(params)}"

    properties = []
    page = 1
    max_pages = 5  # Limit to first 5 pages

    while page <= max_pages:
        page_url = f"{url}&page={page}" if page > 1 else url
        print(f"  Page {page}...")
        html = fetch_page(page_url)
        if not html:
            break

        # Parse property listings from HTML
        page_props = _parse_rakumachi_html(html, city_key)
        if not page_props:
            break

        properties.extend(page_props)
        print(f"  → {len(page_props)}件取得 (累計: {len(properties)}件)")

        # Check for next page
        if f"page={page + 1}" not in html and f">{page + 1}<" not in html:
            break

        page += 1
        time.sleep(1)  # Rate limiting

    print(f"  楽待 合計: {len(properties)}件")
    return properties


def _parse_rakumachi_html(html: str, city_key: str) -> list[dict]:
    """Parse Rakumachi HTML page for property listings."""
    properties = []

    # Find property blocks - Rakumachi uses various HTML structures
    # Try to find property links and surrounding data
    # Pattern: property detail pages /syuuekibukken/kansai/osaka/dim2001/XXXXXXX/show.html
    # or /syuuekibukken/area/osaka/dim2001/XXXXXXX/

    # Extract property card blocks
    blocks = re.findall(
        r'<a[^>]*href="(/syuuekibukken/[^"]*?/(\d{5,10})/[^"]*)"[^>]*>.*?</a>',
        html,
        re.DOTALL,
    )

    # Also try table-style listings
    # Look for structured data near property URLs
    seen_ids = set()
    lines = html.split("\n")

    # Find all property detail URLs
    url_pattern = re.compile(r'href="((?:https://www\.rakumachi\.jp)?/syuuekibukken/[^"]*?/(\d{5,10})/[^"]*)"')
    for match in url_pattern.finditer(html):
        prop_url = match.group(1)
        prop_id = match.group(2)
        if prop_id in seen_ids:
            continue
        seen_ids.add(prop_id)

        if not prop_url.startswith("http"):
            prop_url = "https://www.rakumachi.jp" + prop_url

        # Extract surrounding context for this property (500 chars before/after)
        start = max(0, match.start() - 2000)
        end = min(len(html), match.end() + 2000)
        context = html[start:end]

        # Parse fields from context
        prop = _extract_rakumachi_fields(context, prop_url, prop_id, city_key)
        if prop:
            properties.append(prop)

    return properties


def _extract_rakumachi_fields(context: str, url: str, prop_id: str, city_key: str) -> dict | None:
    """Extract property fields from surrounding HTML context."""
    # Clean HTML tags for text extraction
    text = re.sub(r"<[^>]+>", " ", context)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Price - check 億 first to avoid partial match on "1億2500万円" → "2500万円"
    price_match = re.search(r"\d+(?:\.\d+)?億\s*\d*万?\s*円?", text)
    if not price_match:
        price_match = re.search(r"(\d{1,2},?\d{3})\s*万円", text)
    price_text = ""
    price_man = 0
    if price_match:
        raw = price_match.group(0)
        price_man = parse_price_text(raw)
        price_text = f"{price_man}万円"

    # Filter by price
    if price_man <= 0 or price_man > 5000:
        return None

    # Area
    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", text)
    area_text = area_match.group(0).strip() if area_match else ""
    area_sqm = parse_area_text(area_text) if area_text else 0

    # Filter by area
    if area_sqm > 0 and (area_sqm < AREA_MIN or area_sqm > AREA_MAX):
        return None

    # Location
    loc_match = (
        re.search(r"(大阪府大阪市[^\s,。、]{2,15})", text)
        or re.search(r"(福岡県福岡市[^\s,。、]{2,15})", text)
        or re.search(r"(東京都[^\s,。、]{2,15})", text)
    )
    location = loc_match.group(1) if loc_match else ""

    # Filter by target area - require location for quality
    if not location:
        return None
    if not is_target_location(location, city_key):
        return None

    # Year built
    year_match = re.search(r"(\d{4})年(?:\s*(\d{1,2})月)?(?:\s*築)?", text)
    built_text = year_match.group(0).strip() if year_match else ""

    # Station
    station_patterns = [
        r"((?:地下鉄|JR|阪急|阪神|南海|京阪|近鉄|西鉄)?[^\s「」]*?線\s*「[^」]+」\s*(?:駅\s*)?徒歩\s*\d+\s*分)",
        r"(「[^」]+」\s*(?:駅\s*)?徒歩\s*\d+\s*分)",
        r"([^\s]+(?:駅)\s*徒歩\s*\d+\s*分)",
    ]
    station_text = ""
    for pat in station_patterns:
        sm = re.search(pat, text)
        if sm:
            station_text = sm.group(1).strip()
            break

    # Layout
    layout_match = re.search(r"(\d[SLDK]+(?:\+S)?)", text)
    layout = layout_match.group(1) if layout_match else ""

    # Name - extract property/building name
    name = ""
    # Look for common condominium name patterns
    name_patterns = [
        # Full name like "中津リバーサイドコーポ"
        r"区分マンション\s+([^\s]{2,25}(?:マンション|コーポ|ハイツ|パレス|レジデンス|プレサンス|朝日プラザ|コープ|タワー|パーク|コート|ヒルズ|グラン|シティ|ロイヤル|メゾン|ビュー|プラザ|テラス|フォーレ)[^\s]{0,10})",
        r"区分マンション\s+([^\s]{3,30})",
        # Name with katakana
        r"(?:^|\s)([ァ-ヶー・]{3,}[^\s]{0,15}(?:マンション|コーポ|ハイツ|パレス|レジデンス|タワー))",
        r"(?:^|\s)([^\s]{2,}(?:マンション|コーポ|ハイツ|パレス|レジデンス|タワー|パーク|コート)[^\s]{0,8})",
    ]
    for pat in name_patterns:
        nm = re.search(pat, text)
        if nm:
            candidate = nm.group(1).strip()
            # Clean up common artifacts
            candidate = re.sub(r"^[})>\s]+", "", candidate)
            candidate = re.sub(r"[({<\s]+$", "", candidate)
            if len(candidate) >= 3 and not candidate.startswith("お気に入り"):
                name = candidate[:40]
                break
    if not name:
        name = f"楽待物件#{prop_id}"

    # Brokerage info
    brokerage = ""
    if "手数料無料" in text or "仲介手数料なし" in text:
        brokerage = "無料"
    elif "手数料半額" in text:
        brokerage = "半額"
    elif "売主" in text and "売主から" not in text:
        brokerage = "無料"

    # Pet info
    pet = ""
    if "ペット可" in text:
        pet = "可"
    elif "ペット相談" in text:
        pet = "相談可"
    elif "ペット不可" in text:
        pet = "不可"

    return {
        "source": "楽待",
        "name": name,
        "price_text": price_text,
        "location": location,
        "area_text": area_text,
        "built_text": built_text,
        "station_text": station_text,
        "layout": layout,
        "pet": pet,
        "brokerage": brokerage,
        "url": url,
    }


# ============================================================
# Yahoo! Real Estate (Yahoo!不動産)
# ============================================================

def search_yahoo_realestate(city_key: str) -> list[dict]:
    """Search Yahoo!不動産 for used condos."""
    config = AREA_CONFIGS[city_key]
    print(f"\n=== Yahoo!不動産 ({config['label']}) 検索中... ===")

    # Yahoo Real Estate search URLs by area
    area_codes = {
        "osaka": {
            "北区": "27127", "西区": "27106", "中央区": "27128",
        },
        "fukuoka": {
            "博多区": "40132", "中央区": "40133",
        },
        "tokyo": {
            "渋谷区": "13113", "新宿区": "13104", "目黒区": "13110",
        },
    }

    properties = []
    codes = area_codes.get(city_key, {})

    for ward, code in codes.items():
        url = (
            f"https://realestate.yahoo.co.jp/used/mansion/search/"
            f"?area={code}&priceMax={PRICE_MAX // 10000}"
            f"&areaMin={AREA_MIN}&areaMax={AREA_MAX}"
        )
        print(f"  {ward} 検索中...")
        html = fetch_page(url)
        if not html:
            print(f"  [SKIP] {ward}: アクセス不可")
            continue

        ward_props = _parse_yahoo_html(html, city_key)
        properties.extend(ward_props)
        print(f"  → {len(ward_props)}件")
        time.sleep(1)

    print(f"  Yahoo!不動産 合計: {len(properties)}件")
    return properties


def _parse_yahoo_html(html: str, city_key: str) -> list[dict]:
    """Parse Yahoo Real Estate listing page."""
    properties = []
    text = re.sub(r"<[^>]+>", "\n", html)

    # Find property blocks by URL pattern
    url_pattern = re.compile(r'href="(https://realestate\.yahoo\.co\.jp/used/mansion/detail_corp/[^"]+)"')
    for match in url_pattern.finditer(html):
        prop_url = match.group(1)
        start = max(0, match.start() - 1500)
        end = min(len(html), match.end() + 1500)
        context = html[start:end]
        ctx_text = re.sub(r"<[^>]+>", " ", context)
        ctx_text = re.sub(r"\s+", " ", ctx_text)

        # Extract fields — check 億 first to avoid partial match
        price_m = re.search(r"\d+(?:\.\d+)?億\s*\d*万?\s*円?", ctx_text)
        if not price_m:
            price_m = re.search(r"(\d{1,2},?\d{3})\s*万円", ctx_text)
        if not price_m:
            continue
        price_man = parse_price_text(price_m.group(0))
        if price_man <= 0 or price_man > 5000:
            continue

        area_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", ctx_text)
        area_text = area_m.group(0) if area_m else ""

        loc_m = re.search(r"(?:大阪府|福岡県|東京都)[^\s,]{3,20}", ctx_text)
        location = loc_m.group(0) if loc_m else ""

        year_m = re.search(r"(\d{4})年(?:\s*(\d{1,2})月)?", ctx_text)
        built_text = year_m.group(0) if year_m else ""

        station_m = re.search(r"[^\s]*(?:線|電鉄)\s*「?[^」\s]+」?\s*(?:駅?\s*)?徒歩\s*\d+\s*分", ctx_text)
        station_text = station_m.group(0) if station_m else ""

        layout_m = re.search(r"(\d[SLDK]+(?:\+S)?)", ctx_text)
        layout = layout_m.group(1) if layout_m else ""

        name_m = re.search(r"(?:マンション名|物件名)?[：:]?\s*([^\s]{2,30}(?:マンション|コーポ|ハイツ|タワー|パーク|レジデンス|プラザ|コート)[^\s]{0,10})", ctx_text)
        name = name_m.group(1) if name_m else ""
        if not name:
            name = f"Yahoo物件"

        # Skip entries with insufficient data
        if not location and not station_text:
            continue

        properties.append({
            "source": "Yahoo不動産",
            "name": name,
            "price_text": f"{price_man}万円",
            "location": location,
            "area_text": area_text,
            "built_text": built_text,
            "station_text": station_text,
            "layout": layout,
            "pet": "",
            "brokerage": "",
            "url": prop_url,
        })

    return properties


# ============================================================
# at home (アットホーム)
# ============================================================

def search_athome(city_key: str) -> list[dict]:
    """Search athome for used condos."""
    config = AREA_CONFIGS[city_key]
    print(f"\n=== athome ({config['label']}) 検索中... ===")

    ward_slugs = {
        "osaka": {
            "北区": "osakashi-kita-ku",
            "西区": "osakashi-nishi-ku",
            "中央区": "osakashi-chuo-ku",
        },
        "fukuoka": {
            "博多区": "fukuokashi-hakata-ku",
            "中央区": "fukuokashi-chuo-ku",
        },
        "tokyo": {
            "渋谷区": "shibuya-ku",
            "新宿区": "shinjuku-ku",
            "目黒区": "meguro-ku",
        },
    }

    pref_slug = {
        "osaka": "osaka",
        "fukuoka": "fukuoka",
        "tokyo": "tokyo",
    }

    properties = []
    slugs = ward_slugs.get(city_key, {})
    pref = pref_slug.get(city_key, "")

    for ward, slug in slugs.items():
        url = (
            f"https://www.athome.co.jp/mansion/chuko/{pref}/{slug}/list/"
            f"?PRICE_MAX={PRICE_MAX // 10000}"
            f"&MENSEKI_FROM={AREA_MIN}&MENSEKI_TO={AREA_MAX}"
        )
        print(f"  {ward} 検索中...")
        html = fetch_page(url)
        if not html:
            print(f"  [SKIP] {ward}: アクセス不可")
            continue

        ward_props = _parse_athome_html(html, city_key)
        properties.extend(ward_props)
        print(f"  → {len(ward_props)}件")
        time.sleep(1)

    print(f"  athome 合計: {len(properties)}件")
    return properties


def _parse_athome_html(html: str, city_key: str) -> list[dict]:
    """Parse athome listing page."""
    properties = []

    # Find property detail URLs
    url_pattern = re.compile(r'href="(https://www\.athome\.co\.jp/mansion/chuko/[^"]*?/\d+/[^"]*)"')
    seen_urls = set()

    for match in url_pattern.finditer(html):
        prop_url = match.group(1)
        if prop_url in seen_urls:
            continue
        seen_urls.add(prop_url)

        start = max(0, match.start() - 2000)
        end = min(len(html), match.end() + 2000)
        context = html[start:end]
        ctx_text = re.sub(r"<[^>]+>", " ", context)
        ctx_text = re.sub(r"\s+", " ", ctx_text)

        # Check 億 first to avoid partial match
        price_m = re.search(r"\d+(?:\.\d+)?億\s*\d*万?\s*円?", ctx_text)
        if not price_m:
            price_m = re.search(r"(\d{1,2},?\d{3})\s*万円", ctx_text)
        if not price_m:
            continue
        price_man = parse_price_text(price_m.group(0))
        if price_man <= 0 or price_man > 5000:
            continue

        area_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", ctx_text)
        area_text = area_m.group(0) if area_m else ""

        loc_m = re.search(r"(?:大阪府|福岡県|東京都)[^\s,]{3,20}", ctx_text)
        location = loc_m.group(0) if loc_m else ""

        year_m = re.search(r"(\d{4})年(?:\s*(\d{1,2})月)?", ctx_text)
        built_text = year_m.group(0) if year_m else ""

        station_m = re.search(r"[^\s]*(?:線|電鉄)?\s*「?[^」\s]+」?\s*(?:駅?\s*)?徒歩\s*\d+\s*分", ctx_text)
        station_text = station_m.group(0) if station_m else ""

        layout_m = re.search(r"(\d[SLDK]+(?:\+S)?)", ctx_text)
        layout = layout_m.group(1) if layout_m else ""

        # Try to extract name
        name = ""
        name_patterns = [
            r"([^\s<>]{2,}(?:マンション|コーポ|ハイツ|タワー|パーク|レジデンス|プラザ|コート|ハウス)[^\s<>]{0,10})",
            r"([ァ-ヶー]{3,}[^\s<>]{0,10})",
        ]
        for np in name_patterns:
            nm = re.search(np, ctx_text)
            if nm:
                name = nm.group(1)[:40]
                break

        pet = ""
        if "ペット可" in ctx_text:
            pet = "可"
        elif "ペット相談" in ctx_text:
            pet = "相談可"

        brokerage = ""
        if "手数料無料" in ctx_text or "仲介手数料不要" in ctx_text:
            brokerage = "無料"
        elif "手数料半額" in ctx_text:
            brokerage = "半額"

        properties.append({
            "source": "athome",
            "name": name or "athome物件",
            "price_text": f"{price_man}万円",
            "location": location,
            "area_text": area_text,
            "built_text": built_text,
            "station_text": station_text,
            "layout": layout,
            "pet": pet,
            "brokerage": brokerage,
            "url": prop_url,
        })

    return properties


# ============================================================
# Output
# ============================================================

def save_results(properties: list[dict], city_key: str, source_name: str) -> Path:
    """Save results to pipe-delimited data file."""
    DATA_DIR.mkdir(exist_ok=True)
    filename = f"{source_name}_{city_key}_raw.txt"
    out_path = DATA_DIR / filename

    lines = [
        f"## {source_name} 検索結果 - {AREA_CONFIGS[city_key]['label']}",
        f"## 条件: {PRICE_MAX // 10000}万以下, {AREA_MIN}-{AREA_MAX}㎡",
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
            prop["url"],
        ])
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def save_combined(all_properties: list[dict], city_key: str) -> Path:
    """Save combined results from all sources to a single file."""
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"multi_site_{city_key}_raw.txt"

    # Collect source names
    sources = sorted(set(p["source"] for p in all_properties))

    lines = [
        f"## マルチサイト検索結果 - {AREA_CONFIGS[city_key]['label']}",
        f"## ソース: {', '.join(sources)}",
        f"## 条件: {PRICE_MAX // 10000}万以下, {AREA_MIN}-{AREA_MAX}㎡",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(all_properties)}件",
        "",
    ]

    for prop in all_properties:
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
            prop["url"],
        ])
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


# ============================================================
# f-takken.com (ふれんず / 福岡県宅建協会) - URL generator only
# ============================================================

FTAKKEN_SEARCH_URLS = {
    "fukuoka": {
        "博多区": "https://www.f-takken.com/freins/buy/mansion/area?locate[]=40132",
        "中央区": "https://www.f-takken.com/freins/buy/mansion/area?locate[]=40133",
        "南区": "https://www.f-takken.com/freins/buy/mansion/area?locate[]=40134",
    },
}


def get_ftakken_urls(city_key: str) -> dict[str, str]:
    """Return f-takken.com search URLs (JS-rendered site, manual search required)."""
    return FTAKKEN_SEARCH_URLS.get(city_key, {})


def search_city(city_key: str) -> Path:
    """Run all site searches for a city and save combined results."""
    print(f"\n{'='*60}")
    print(f" マルチサイト物件検索: {AREA_CONFIGS[city_key]['label']}")
    print(f"{'='*60}")

    all_properties = []

    # Search each site
    searchers = [
        ("rakumachi", search_rakumachi),
        ("yahoo", search_yahoo_realestate),
        ("athome", search_athome),
    ]

    for source_key, search_fn in searchers:
        try:
            props = search_fn(city_key)
            if props:
                all_properties.extend(props)
                save_results(props, city_key, source_key)
        except Exception as e:
            print(f"  [ERROR] {source_key}: {e}")

    # Save combined
    if all_properties:
        out_path = save_combined(all_properties, city_key)
        print(f"\n合計: {len(all_properties)}件 → {out_path}")
        return out_path
    else:
        print("\n物件が見つかりませんでした。")
        return DATA_DIR / f"multi_site_{city_key}_raw.txt"


def main():
    """Search all target cities."""
    print(f"マルチサイト物件検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"条件: {PRICE_MAX // 10000}万以下, {AREA_MIN}-{AREA_MAX}㎡")

    for city_key in ["osaka", "fukuoka"]:
        search_city(city_key)

    print("\n完了。レポート生成は以下を実行:")
    print("  python generate_osaka_report.py")
    print("  python generate_fukuoka_report.py")


if __name__ == "__main__":
    main()
