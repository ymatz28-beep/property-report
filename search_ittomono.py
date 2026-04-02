#!/usr/bin/env python3
"""
一棟もの（一棟マンション・一棟アパート）検索スクリプト
楽待から一棟売り物件を検索し、パイプ区切り形式で出力する。

出力フォーマット (14列):
source|name|price|location|area|built|station|structure|units|yield|layout_detail|pet|brokerage|url

検索条件:
- 価格帯: 1.5億〜2億円
- エリア: 大阪/福岡/東京の主要エリア
- 築年数: フィルタなし
- 物件種別: 一棟マンション (dim1001) + 一棟アパート (dim1002)
"""

import re
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

# Price range: 1.5億〜2億 (in 万円 for Rakumachi)
PRICE_MIN = 15000  # 1.5億 = 15000万
PRICE_MAX = 20000  # 2億 = 20000万

# Area configs — same areas as existing patrol
KENBIYA_REGIONS = {
    "osaka": {"path": "k/osaka", "pref": "大阪府"},
    "fukuoka": {"path": "f/fukuoka", "pref": "福岡県"},
    "tokyo": {"path": "s/tokyo", "pref": "東京都"},
}
# Kenbiya price dropdown: closest to 15000 is 14000
KENBIYA_PRICE_MIN = 14000
KENBIYA_PRICE_MAX = 20000

AREA_CONFIGS = {
    "osaka": {
        "label": "大阪",
        "rakumachi_area": "27",
        "rakumachi_region": "kansai/osaka",
        "target_wards": ["北区", "西区", "中央区", "福島区", "浪速区", "天王寺区"],
        "target_areas": [
            "北堀江", "南堀江", "中津", "中崎町", "南森町", "天神橋", "天満",
            "扇町", "東天満", "梅田", "大淀", "福島", "肥後橋", "淀屋橋",
            "北浜", "江戸堀", "阿波座", "靱公園", "靱本町", "長堀橋",
            "心斎橋", "谷町", "なんば", "日本橋", "新今宮",
        ],
    },
    "fukuoka": {
        "label": "福岡",
        "rakumachi_area": "40",
        "rakumachi_region": "kyushu/fukuoka",
        "target_wards": ["博多区", "中央区", "南区"],
        "target_areas": [
            "天神", "博多", "薬院", "平尾", "住吉", "祇園", "赤坂",
            "大濠", "渡辺通", "中洲", "春吉", "呉服町",
        ],
    },
    "tokyo": {
        "label": "東京",
        "rakumachi_area": "13",
        "rakumachi_region": "kanto/tokyo",
        "target_wards": [
            "渋谷区", "新宿区", "目黒区", "豊島区", "台東区",
            "中野区", "文京区", "港区", "品川区", "墨田区",
            "世田谷区", "杉並区", "板橋区", "北区", "練馬区",
        ],
        "target_areas": [
            "渋谷", "新宿", "中目黒", "恵比寿", "代官山", "神宮前",
            "池袋", "大塚", "巣鴨", "浅草", "上野", "蔵前", "押上",
            "中野", "高円寺", "麻布", "白金", "三田", "五反田",
        ],
    },
}


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


# URL path district → 期待される日本語地名マッピング
_TOKYO_WARD_MAP = {
    "chiyoda-ku": "千代田区", "chuo-ku": "中央区", "minato-ku": "港区",
    "shinjuku-ku": "新宿区", "bunkyo-ku": "文京区", "taito-ku": "台東区",
    "sumida-ku": "墨田区", "koto-ku": "江東区", "shinagawa-ku": "品川区",
    "meguro-ku": "目黒区", "ota-ku": "大田区", "setagaya-ku": "世田谷区",
    "shibuya-ku": "渋谷区", "nakano-ku": "中野区", "suginami-ku": "杉並区",
    "toshima-ku": "豊島区", "kita-ku": "北区", "arakawa-ku": "荒川区",
    "itabashi-ku": "板橋区", "nerima-ku": "練馬区", "adachi-ku": "足立区",
    "katsushika-ku": "葛飾区", "edogawa-ku": "江戸川区",
    "musashino-shi": "武蔵野市", "mitaka-shi": "三鷹市", "hachioji-shi": "八王子市",
    "tachikawa-shi": "立川市", "musashimurayama-shi": "武蔵村山市",
    "kodaira-shi": "小平市", "chofu-shi": "調布市", "fuchu-shi": "府中市",
    "hino-shi": "日野市", "higashimurayama-shi": "東村山市",
    "kunitachi-shi": "国立市", "kokubunji-shi": "国分寺市",
    "nishitokyo-shi": "西東京市",
    "hamura-shi": "羽村市", "akishima-shi": "昭島市", "fussa-shi": "福生市",
    "ome-shi": "青梅市", "machida-shi": "町田市", "inagi-shi": "稲城市",
    "komae-shi": "狛江市", "tama-shi": "多摩市", "hino-shi": "日野市",
}
_OSAKA_CITY_MAP = {
    "osaka-shi": "大阪市", "sakai-shi": "堺市", "kadoma-shi": "門真市",
    "higashiosaka-shi": "東大阪市", "toyonaka-shi": "豊中市",
    "suita-shi": "吹田市", "neyagawa-shi": "寝屋川市",
    "hirakata-shi": "枚方市", "takatsuki-shi": "高槻市",
    "yao-shi": "八尾市", "matsubara-shi": "松原市",
    "daito-shi": "大東市", "moriguchi-shi": "守口市",
    "izumisano-shi": "泉佐野市", "habikino-shi": "羽曳野市",
    "kishiwada-shi": "岸和田市", "ibaraki-shi": "茨木市",
    "settsu-shi": "摂津市", "minoo-shi": "箕面市", "ikeda-shi": "池田市",
    "fujiidera-shi": "藤井寺市", "kashiwara-shi": "柏原市",
}
_FUKUOKA_CITY_MAP = {
    "fukuoka-shi": "福岡市", "kitakyushu-shi": "北九州市",
    "kurume-shi": "久留米市", "kasuga-shi": "春日市",
    "onojo-shi": "大野城市", "dazaifu-shi": "太宰府市",
    "itoshima-shi": "糸島市", "munakata-shi": "宗像市",
}
_DISTRICT_MAPS = {
    "tokyo": _TOKYO_WARD_MAP,
    "osaka": _OSAKA_CITY_MAP,
    "fukuoka": _FUKUOKA_CITY_MAP,
}


def _url_location_valid(url: str, location: str, city_key: str) -> bool:
    """URLのdistrictパスと抽出locationが一致するか検証。

    不一致 = クロスリスティング汚染の可能性。
    判定不能（マップにないdistrict）の場合は通過させる（false negative許容）。
    """
    # URLからdistrictを抽出: /pp{N}/{region}/{district}/re_{id}/
    m = re.search(r"/re_\w+/", url)
    if not m:
        return True  # URL解析不能 → 通過
    # districtはre_の2〜3セグメント前
    prefix = url[: m.start()]
    seg = prefix.rstrip("/").split("/")

    district_map = _DISTRICT_MAPS.get(city_key, {})

    # osaka-shi/N の形式を考慮: 末尾が数字なら1つ前がdistrict
    for i in range(len(seg) - 1, max(len(seg) - 4, -1), -1):
        part = seg[i]
        if part.isdigit():
            continue
        if part in district_map:
            expected_jp = district_map[part]
            if expected_jp not in location:
                return False  # 汚染
            return True
        # osaka/tokyo/fukuoka 等の上位パスに達したら終了
        if part in ("osaka", "tokyo", "fukuoka", "k", "s", "f", "pp1", "pp2", "pp3"):
            return True
    return True  # マップにないdistrict → 通過


def is_target_location(location: str, city_key: str) -> bool:
    """Check if property location matches target areas.

    Ward matching requires the correct city prefix to avoid false positives
    (e.g. 堺市西区 matching osaka's 西区 target).
    """
    config = AREA_CONFIGS.get(city_key, {})
    wards = config.get("target_wards", [])
    areas = config.get("target_areas", [])
    # City prefixes for ward matching precision
    city_prefixes = {"osaka": "大阪市", "fukuoka": "福岡市", "tokyo": "東京都"}
    prefix = city_prefixes.get(city_key, "")
    ward_match = any(f"{prefix}{w}" in location or (not prefix and w in location) for w in wards)
    area_match = any(a in location for a in areas)
    return ward_match or area_match


def parse_price_text(text: str) -> int:
    """Parse price text to 万円 integer."""
    text = text.replace(",", "").replace("\u3000", "").strip()
    m_oku = re.search(r"(\d+(?:\.\d+)?)\u5104", text)
    m_man = re.search(r"(\d+(?:\.\d+)?)\u4e07", text)
    total = 0
    if m_oku:
        total += int(float(m_oku.group(1)) * 10000)
    if m_man:
        total += int(float(m_man.group(1)))
    if total == 0:
        m = re.search(r"(\d+)", text)
        if m and len(m.group(1)) >= 7:
            total = int(m.group(1)) // 10000
    return total


def search_rakumachi_ittomono(city_key: str) -> list[dict]:
    """Search 楽待 for 一棟マンション (dim1001) + 一棟アパート (dim1002).

    Note: 一棟もの uses prefecture-wide search (no ward filter).
    Unlike 区分マンション, investment whole-buildings at 1.5-2億 are rare in
    premium wards, so we search the entire prefecture and filter by price only.
    """
    config = AREA_CONFIGS[city_key]
    area_code = config["rakumachi_area"]
    region = config["rakumachi_region"]
    print(f"\n=== 楽待 一棟もの ({config['label']}) 検索中... ===")

    all_properties = []

    for dim_code, dim_label in [("dim1001", "一棟マンション"), ("dim1002", "一棟アパート")]:
        print(f"\n  --- {dim_label} ({dim_code}) ---")
        base_url = f"https://www.rakumachi.jp/syuuekibukken/area/prefecture/{dim_code}/"
        params = {
            "area": area_code,
            "pmin": str(PRICE_MIN),
            "pmax": str(PRICE_MAX),
        }
        url = f"{base_url}?{urlencode(params)}"

        page = 1
        max_pages = 5

        while page <= max_pages:
            page_url = f"{url}&page={page}" if page > 1 else url
            print(f"  Page {page}...")
            html = fetch_page(page_url)
            if not html:
                break

            page_props = _parse_rakumachi_ittomono(html, city_key, dim_label, region, dim_code)
            if not page_props:
                # Log diagnostic info when 0 results from a page with content
                if html and len(html) > 5000:
                    import re as _re
                    url_count = len(_re.findall(r'syuuekibukken/[^"]*?/\d{5,10}/', html))
                    print(f"  [DIAG] HTML={len(html)}B, prop_urls={url_count}, parsed=0 — possible HTML structure change")
                break

            all_properties.extend(page_props)
            print(f"  -> {len(page_props)}件取得 (累計: {len(all_properties)}件)")

            if f"page={page + 1}" not in html and f">{page + 1}<" not in html:
                break

            page += 1
            time.sleep(1.5)

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
    print(f"  楽待一棟もの {config['label']} 合計: {len(deduped)}件")
    return deduped


def _parse_rakumachi_ittomono(html: str, city_key: str, dim_label: str, region: str, dim_code: str) -> list[dict]:
    """Parse Rakumachi HTML for 一棟もの property listings."""
    properties = []

    url_pattern = re.compile(
        r'href="((?:https://www\.rakumachi\.jp)?/syuuekibukken/[^"]*?/(\d{5,10})/[^"]*)"'
    )
    seen_ids = set()

    # Pre-collect to use next-URL as end boundary (avoids previous property contamination)
    all_matches = list(url_pattern.finditer(html))

    for i, match in enumerate(all_matches):
        prop_url = match.group(1)
        prop_id = match.group(2)
        if prop_id in seen_ids:
            continue
        seen_ids.add(prop_id)

        if not prop_url.startswith("http"):
            prop_url = "https://www.rakumachi.jp" + prop_url

        # Context: from this URL forward to the next property URL (no lookback)
        start = match.start()
        if i + 1 < len(all_matches):
            end = all_matches[i + 1].start()
        else:
            end = min(len(html), match.end() + 3000)
        context = html[start:end]

        prop = _extract_ittomono_fields(context, prop_url, prop_id, city_key, dim_label)
        if prop:
            if is_target_location(prop["location"], city_key):
                properties.append(prop)

    return properties


def _extract_ittomono_fields(context: str, url: str, prop_id: str, city_key: str, dim_label: str) -> dict | None:
    """Extract 一棟もの fields from surrounding HTML context."""
    text = re.sub(r"<[^>]+>", " ", context)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Price
    price_match = re.search(r"\d+(?:\.\d+)?\u5104\s*\d*\u4e07?\s*\u5186?", text)
    if not price_match:
        price_match = re.search(r"(\d{1,2},?\d{3,4})\s*\u4e07\u5186", text)
    price_text = ""
    price_man = 0
    if price_match:
        raw = price_match.group(0)
        price_man = parse_price_text(raw)
        if price_man >= 10000:
            oku = price_man // 10000
            man = price_man % 10000
            if man > 0:
                price_text = f"{oku}\u5104{man}\u4e07\u5186"
            else:
                price_text = f"{oku}\u5104\u5186"
        else:
            price_text = f"{price_man}\u4e07\u5186"

    if price_man < PRICE_MIN or price_man > PRICE_MAX:
        return None

    # Location
    loc_match = (
        re.search(r"(\u5927\u962a\u5e9c[^\s,\u3002\u3001]{2,20})", text)
        or re.search(r"(\u798f\u5ca1\u770c[^\s,\u3002\u3001]{2,20})", text)
        or re.search(r"(\u6771\u4eac\u90fd[^\s,\u3002\u3001]{2,20})", text)
    )
    location = loc_match.group(1) if loc_match else ""

    if not location:
        return None

    # Building area
    area_text = ""
    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[\u00b22]|\u33a1)", text)
    if area_match:
        area_text = area_match.group(0).strip()

    # Year built
    year_match = re.search(r"(\d{4})\u5e74(?:\s*(\d{1,2})\u6708)?(?:\s*\u7bc9)?", text)
    built_text = year_match.group(0).strip() if year_match else ""

    # Station access
    station_patterns = [
        r"((?:\u5730\u4e0b\u9244|JR|\u962a\u6025|\u962a\u795e|\u5357\u6d77|\u4eac\u962a|\u8fd1\u9244|\u897f\u9244)?[^\s\u300c\u300d]*?\u7dda\s*\u300c[^\u300d]+\u300d\s*(?:\u99c5\s*)?\u5f92\u6b69\s*\d+\s*\u5206)",
        r"(\u300c[^\u300d]+\u300d\s*(?:\u99c5\s*)?\u5f92\u6b69\s*\d+\s*\u5206)",
        r"([^\s]+(?:\u99c5)\s*\u5f92\u6b69\s*\d+\s*\u5206)",
    ]
    station_text = ""
    for pat in station_patterns:
        sm = re.search(pat, text)
        if sm:
            station_text = sm.group(1).strip()
            break

    # Building structure
    structure = ""
    struct_patterns = [
        (r"(RC\u9020|SRC\u9020|\u9244\u7b4b\u30b3\u30f3\u30af\u30ea\u30fc\u30c8\u9020|\u9244\u9aa8\u9244\u7b4b\u30b3\u30f3\u30af\u30ea\u30fc\u30c8\u9020)", None),
        (r"(S\u9020|\u9244\u9aa8\u9020|\u91cd\u91cf\u9244\u9aa8\u9020|\u8efd\u91cf\u9244\u9aa8\u9020)", None),
        (r"(\u6728\u9020)", None),
    ]
    for pat, _ in struct_patterns:
        sm = re.search(pat, text)
        if sm:
            raw_struct = sm.group(1)
            if "\u9244\u7b4b\u30b3\u30f3\u30af\u30ea\u30fc\u30c8" in raw_struct and "\u9244\u9aa8" in raw_struct:
                structure = "SRC\u9020"
            elif "\u9244\u7b4b\u30b3\u30f3\u30af\u30ea\u30fc\u30c8" in raw_struct:
                structure = "RC\u9020"
            elif "\u9244\u9aa8" in raw_struct:
                structure = "S\u9020"
            else:
                structure = raw_struct
            break

    # Total units
    units = ""
    units_match = re.search(r"(\d+)\s*(?:\u6238|\u5ba4|\u90e8\u5c4b|units)", text)
    if units_match:
        units = units_match.group(1) + "\u6238"

    # Yield
    yield_text = ""
    yield_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if yield_match:
        yield_val = float(yield_match.group(1))
        if 1.0 <= yield_val <= 30.0:
            yield_text = f"{yield_val}%"

    # Name — extract building name from context
    # Rakumachi uses "1棟マンション" (ASCII 1) not "一棟" (kanji), handle both
    name = ""
    # Blacklist: property type labels that are NOT names
    _type_labels = {"1棟マンション", "1棟アパート", "一棟マンション", "一棟アパート",
                    "マンション", "アパート"}
    name_patterns = [
        # "1棟マンション 物件名" or "一棟マンション 物件名"
        r"[1一]棟(?:マンション|アパート)\s+([^\s]{2,30})",
        # Standalone building names (ending in common suffixes)
        r"(?:^|\s)([^\s]{3,}(?:ハイツ|コーポ|レジデンス|ビル|荘|パレス|ガーデン|テラス|プラザ|グランド|メゾン|フォレスト))",
        # Katakana-heavy names (likely building names)
        r"(?:^|\s)([ァ-ヶー]{3,}[^\s]*(?:マンション|アパート))",
    ]
    for pat in name_patterns:
        nm = re.search(pat, text)
        if nm:
            candidate = nm.group(1).strip()
            candidate = re.sub(r"^[})>\s]+", "", candidate)
            candidate = re.sub(r"[({<\s]+$", "", candidate)
            if (len(candidate) >= 2
                    and candidate not in _type_labels
                    and not candidate.startswith("お気に入り")
                    and not re.match(r"^\d{2}/\d{2}$", candidate)
                    and not re.match(r"^\d+億", candidate)
                    and not re.match(r"^\d[\d,]*万円?$", candidate)):
                name = candidate[:40]
                break
    if not name:
        # Fallback: use location shorthand for readability
        loc_short = location.split("区")[-1].split("市")[-1][:10] if location else ""
        name = f"楽待 {loc_short}#{prop_id[-4:]}" if loc_short else f"楽待#{prop_id}"

    # Layout detail (room breakdown) — extracted from listing context
    layout_detail = ""
    # Pattern: 1K×6戸, 1LDK×6戸 etc.
    madori_matches = re.findall(
        r"(\d[RKLDKS]+\s*[×xX]\s*\d+\s*(?:戸|室)?)", text
    )
    if madori_matches:
        layout_detail = ", ".join(dict.fromkeys(m.strip() for m in madori_matches))

    return {
        "source": f"\u697d\u5f85({dim_label})",
        "name": name,
        "price_text": price_text,
        "price_man": price_man,
        "location": location,
        "area_text": area_text,
        "built_text": built_text,
        "station_text": station_text,
        "structure": structure,
        "units": units,
        "yield_text": yield_text,
        "layout_detail": layout_detail,
        "url": url,
    }


def search_kenbiya_ittomono(city_key: str) -> list[dict]:
    """Search 健美家 for 一棟マンション (pp3) + 一棟アパート (pp2)."""
    config = AREA_CONFIGS[city_key]
    kb = KENBIYA_REGIONS[city_key]
    print(f"\n=== 健美家 一棟もの ({config['label']}) 検索中... ===")

    all_properties = []
    for pp_code, pp_label in [("pp3", "一棟マンション"), ("pp2", "一棟アパート")]:
        print(f"\n  --- {pp_label} ({pp_code}) ---")
        page = 1
        max_pages = 5

        while page <= max_pages:
            if page == 1:
                url = f"https://www.kenbiya.com/{pp_code}/{kb['path']}/p1={KENBIYA_PRICE_MIN}/p2={KENBIYA_PRICE_MAX}/"
            else:
                url = f"https://www.kenbiya.com/{pp_code}/{kb['path']}/n-{page}/p1={KENBIYA_PRICE_MIN}/p2={KENBIYA_PRICE_MAX}/"

            print(f"  Page {page}...")
            html = fetch_page(url)
            if not html:
                break

            page_props = _parse_kenbiya_listings(html, city_key, pp_label, kb["pref"])
            if not page_props:
                break

            all_properties.extend(page_props)
            print(f"  -> {len(page_props)}件取得 (累計: {len(all_properties)}件)")

            # Check next page exists
            if f"/n-{page + 1}/" not in html:
                break
            page += 1
            time.sleep(1.5)

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
    print(f"  健美家一棟もの {config['label']} 合計: {len(deduped)}件")
    return deduped


def _parse_kenbiya_listings(html: str, city_key: str, pp_label: str, pref: str) -> list[dict]:
    """Parse 健美家 property listing HTML using structured prop_block parsing.

    Kenbiya search pages have two sections:
    1. PR listings (md-propetyListPr) — sponsor ads, skip these
    2. Main listings (box_table_main) — actual search results with prop_block structure

    Each listing card wraps all data inside:
      <a href="/ppN/.../re_ID/"><ul class="prop_block">
        <li class="main"> — title (h3), location, station
        <li class="price"> — price + yield (structured HTML)
        <li> — area (建/土)
        <li> — built year, floors/units
      </ul></a>

    Previous approach (regex on forward-only text context from URL) caused:
    - Yield extracted from h3 ad-copy text instead of structured <li class="price">
    - Cross-listing contamination from PR/recommended properties
    """
    properties = []
    seen_ids = set()

    # Parse each listing card: <a href="...re_ID/"><ul class="prop_block">...</ul></a>
    card_pattern = re.compile(
        r'<a\s+href="(/pp\d/[^"]*?/re_(\w+)/)"[^>]*>\s*'
        r'<ul\s+class="prop_block">(.*?)</ul>\s*</a>',
        re.DOTALL,
    )

    for card_match in card_pattern.finditer(html):
        prop_path = card_match.group(1)
        prop_id = card_match.group(2)
        block_html = card_match.group(3)

        if prop_id in seen_ids:
            continue
        seen_ids.add(prop_id)

        prop_url = "https://www.kenbiya.com" + prop_path

        prop = _extract_kenbiya_fields_structured(
            block_html, prop_url, prop_id, city_key, pp_label, pref
        )
        if prop:
            if is_target_location(prop["location"], city_key):
                if _url_location_valid(prop_url, prop["location"], city_key):
                    properties.append(prop)
                else:
                    print(
                        f"  [SKIP] URL/location不一致(汚染): {prop_id} "
                        f"URL={prop_url.split('/')[-3]} loc={prop['location']}"
                    )

    return properties


def _extract_kenbiya_fields_structured(
    block_html: str, url: str, prop_id: str, city_key: str, pp_label: str, pref: str
) -> dict | None:
    """Extract fields from 健美家 prop_block structured HTML.

    The prop_block has distinct <li> sections for each data group,
    so we parse each section separately to avoid cross-field contamination.
    """
    # Strip to plain text for location/station/name extraction
    text = re.sub(r"<[^>]+>", " ", block_html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"&sup2;", "m²", text)
    text = re.sub(r"\s+", " ", text).strip()

    # --- Yield: extract from structured <li class="price"> HTML ---
    # Structure: <li class="price"><ul><li>PRICE</li><li>YIELD％</li></ul></li>
    # Use </ul> as boundary since inner <li>s close before the yield line
    yield_text = ""
    price_section = re.search(
        r'<li\s+class="price">(.*?)</ul>', block_html, re.DOTALL
    )
    if price_section:
        ps = price_section.group(1)
        # Yield: nested spans format: <span>6<span>.75</span></span>％
        yield_match = re.search(
            r'<span>(\d+)<span>([.\d]*)</span></span>\s*％', ps
        )
        if yield_match:
            yield_str = yield_match.group(1) + yield_match.group(2)
            try:
                yield_val = float(yield_str)
                if 1.0 <= yield_val <= 30.0:
                    yield_text = f"{yield_val}%"
            except ValueError:
                pass
        if not yield_text:
            # Fallback: plain text ％ in price section only
            ps_text = re.sub(r"<[^>]+>", " ", ps)
            ym = re.search(r"(\d+(?:\.\d+)?)\s*[%％]", ps_text)
            if ym:
                try:
                    yv = float(ym.group(1))
                    if 1.0 <= yv <= 30.0:
                        yield_text = f"{yv}%"
                except ValueError:
                    pass

    # --- Price: from h3 title text or structured price section ---
    # h3 format: "市区町村 1億9,800万円 7.21% 一棟マンション"
    price_man = 0
    price_text = ""
    # Try 億+万 format
    price_match = re.search(r"(\d+)\s*億\s*(?:(\d[\d,]*)\s*万)?円", text)
    if price_match:
        oku = int(price_match.group(1))
        man_part = price_match.group(2)
        man = int(man_part.replace(",", "")) if man_part else 0
        price_man = oku * 10000 + man
    else:
        # Try 万円 only format (e.g. "9,800万円")
        man_match = re.search(r"([\d,]+)\s*万円", text)
        if man_match:
            price_man = int(man_match.group(1).replace(",", ""))

    if price_man < KENBIYA_PRICE_MIN or price_man > KENBIYA_PRICE_MAX:
        return None

    oku_part = price_man // 10000
    man_remainder = price_man % 10000
    if man_remainder > 0:
        price_text = f"{oku_part}億{man_remainder}万円"
    else:
        price_text = f"{oku_part}億円"

    # --- Location ---
    loc_match = re.search(rf"({re.escape(pref)}[^\s,。、]{{2,20}})", text)
    location = loc_match.group(1) if loc_match else ""
    if not location:
        return None

    # --- Area: 建:468.18m² ---
    area_text = ""
    area_match = re.search(r"建[:：]\s*(\d[\d,.]*)\s*m", text)
    if not area_match:
        area_match = re.search(r"延床[面積]*[:：]?\s*(\d[\d,.]*)\s*m", text)
    if not area_match:
        # m² from &sup2; converted text
        area_match = re.search(r"建[:：]?\s*(\d[\d,.]*)\s*m²", text)
    if area_match:
        area_text = area_match.group(1).replace(",", "") + "m²"

    # Land area fallback
    if not area_text:
        land_match = re.search(r"土[:：]\s*(\d[\d,.]*)\s*m", text)
        if not land_match:
            land_match = re.search(r"土[:：]?\s*(\d[\d,.]*)\s*m²", text)
        if land_match:
            area_text = land_match.group(1).replace(",", "") + "m²(土地)"

    # --- Year built ---
    year_match = re.search(r"(\d{4})年(?:\s*(\d{1,2})月)?", text)
    built_text = year_match.group(0).strip() if year_match else ""

    # --- Station ---
    station_text = ""
    st_match = re.search(r"([^\s]+(?:駅)\s*歩\d+分)", text)
    if st_match:
        station_text = st_match.group(1)

    # --- Structure + units ---
    structure = ""
    units = ""
    mat_floor_match = re.search(
        r"(RC造|SRC造|鉄筋コンクリート造|S造|鉄骨造|軽量鉄骨造|木造)\s*(\d+)階建", text
    )
    if mat_floor_match:
        structure = mat_floor_match.group(1) + mat_floor_match.group(2) + "階建"
        units_m = re.search(
            r"(\d+)戸", text[mat_floor_match.end() : mat_floor_match.end() + 50]
        )
        if units_m:
            units = units_m.group(1) + "戸"
    if not structure:
        struct_match = re.search(r"(\d+)階建(?:/(\d+)戸)?", text)
        if struct_match:
            structure = struct_match.group(1) + "階建"
            if struct_match.group(2):
                units = struct_match.group(2) + "戸"
    if not units:
        units_m = re.search(r"(\d+)戸", text)
        if units_m:
            units = units_m.group(1) + "戸"

    # --- Name ---
    name = ""
    # Extract from <li class="main"> h3 first
    main_section = re.search(r'<li\s+class="main">(.*?)</li>', block_html, re.DOTALL)
    if main_section:
        h3_match = re.search(r"<h3>(.*?)</h3>", main_section.group(1))
        if h3_match:
            h3_text = re.sub(r"<[^>]+>", "", h3_match.group(1)).strip()
            # h3 often contains "市区町村 価格 利回り% 種別" — not a building name
            # Try to extract a building name if present
            for pat in [
                r"([ァ-ヶー]{3,}[^\s]*(?:マンション|ハイツ|コーポ|ビル|レジデンス|荘|パレス|テラス))",
                r"(?:^|\s)([^\s]{3,}(?:ハイツ|コーポ|ビル|荘|パレス|マンション|テラス|レジデンス))",
            ]:
                nm = re.search(pat, h3_text)
                if nm:
                    name = nm.group(1).strip()[:40]
                    break
    if not name:
        # Fallback from full text
        for pat in [
            r"([ァ-ヶー]{3,}[^\s]*(?:マンション|ハイツ|コーポ|ビル|レジデンス|荘|パレス|テラス))",
            r"(?:^|\s)([^\s]{3,}(?:ハイツ|コーポ|ビル|荘|パレス|マンション|テラス|レジデンス))",
        ]:
            nm = re.search(pat, text)
            if nm:
                name = nm.group(1).strip()[:40]
                break
    if not name:
        loc_short = location.replace(pref, "")[:10]
        name = f"健美家 {loc_short}#{prop_id[-4:]}"

    return {
        "source": f"健美家({pp_label})",
        "name": name,
        "price_text": price_text,
        "price_man": price_man,
        "location": location,
        "area_text": area_text,
        "built_text": built_text,
        "station_text": station_text,
        "structure": structure,
        "units": units,
        "yield_text": yield_text,
        "layout_detail": "",
        "url": url,
    }


def score_ittomono(prop: dict) -> int:
    """Score 一棟もの property for investment potential (0-100).

    Axes:
      Yield (30): 7%+=30, 6-7=25, 5-6=20, 4-5=15, <4=5, unknown=10
      Structure (20): RC/SRC=20, S造=15, 木造=5, unknown=8
      Age (20): <10yr=20, 10-20=15, 20-30=10, 30-40=5, 40+=0
      Units (15): 10+=15, 6-9=12, 3-5=8, 1-2=3, unknown=5
      Station (15): ≤5min=15, 6-10=10, 11-15=5, >15/unknown=0
    """
    score = 0

    # Yield
    yt = prop.get("yield_text", "")
    ym = re.search(r"([\d.]+)%", yt)
    if ym:
        yv = float(ym.group(1))
        if yv >= 7:
            score += 30
        elif yv >= 6:
            score += 25
        elif yv >= 5:
            score += 20
        elif yv >= 4:
            score += 15
        else:
            score += 5
    else:
        score += 10  # unknown

    # Structure
    st = prop.get("structure", "")
    if "RC" in st or "SRC" in st or "鉄筋コンクリート" in st:
        score += 20
    elif "S造" in st or "鉄骨" in st:
        score += 15
    elif "木造" in st:
        score += 5
    else:
        score += 8  # floors-only or unknown → neutral

    # Building age
    bt = prop.get("built_text", "")
    bm = re.search(r"(\d{4})年", bt)
    if bm:
        age = 2026 - int(bm.group(1))
        if age < 10:
            score += 20
        elif age < 20:
            score += 15
        elif age < 30:
            score += 10
        elif age < 40:
            score += 5
    # 40+ or unknown = 0

    # Units
    ut = prop.get("units", "")
    um = re.search(r"(\d+)", ut)
    if um:
        uv = int(um.group(1))
        if uv >= 10:
            score += 15
        elif uv >= 6:
            score += 12
        elif uv >= 3:
            score += 8
        else:
            score += 3
    else:
        score += 5

    # Station access
    stt = prop.get("station_text", "")
    sm = re.search(r"(\d+)\s*分", stt)
    if sm:
        mins = int(sm.group(1))
        if mins <= 5:
            score += 15
        elif mins <= 10:
            score += 10
        elif mins <= 15:
            score += 5

    return score


def _is_floors_only(structure: str) -> bool:
    """True if structure has no material info (e.g. '3階建' but not 'RC造3階建')."""
    if not structure:
        return True
    return not any(m in structure for m in ["RC", "SRC", "鉄骨", "木造", "S造"])


def _is_fallback_name(name: str) -> bool:
    """Check if the name is a scraper-generated fallback (address-based, not building name)."""
    if not name:
        return True
    # Explicit fallback patterns: "楽待 xxx#xxxx", "健美家 xxx#xxxx"
    if re.match(r"^(楽待|健美家)\s", name):
        return True
    # Address-only: starts with 市/区 or prefecture pattern
    if re.match(r"^(福岡市|大阪市|東京都|神奈川県|埼玉県|千葉県)", name):
        return True
    # Generic labels that aren't building names
    generic = {"投資用マンション", "一棟売マンション", "一棟売りマンション",
                "一棟マンション", "一棟アパート", "収益マンション", "収益物件"}
    if name in generic:
        return True
    return False


def _extract_building_name_from_detail(html: str, source: str) -> str:
    """Extract building name from detail page HTML.

    Rakumachi: <h1> tag contains building name directly.
    Kenbiya: <h2> heading contains building name.
    """
    if "rakumachi" in source or "楽待" in source:
        # Rakumachi: building name is in <h1>
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if m:
            name = m.group(1).strip()
            # Filter out generic page titles
            if name and len(name) >= 2 and "楽待" not in name and "物件一覧" not in name:
                return name[:50]

    if "kenbiya" in source or "健美家" in source:
        # Kenbiya: building name often in <h2> or page title
        # Try <title> first: "物件名 - 健美家"
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html)
        if title_m:
            title = title_m.group(1).strip()
            # Remove site suffix: "ホワイトシャトー大橋 壱番館 - 健美家(けんびや)"
            title = re.sub(r"\s*[-–—|]\s*健美家.*$", "", title)
            title = re.sub(r"\s*[-–—|]\s*けんびや.*$", "", title)
            if title and len(title) >= 2 and "健美家" not in title and "物件一覧" not in title:
                return title[:50]
        # Fallback: <h2>
        h2_m = re.search(r"<h2[^>]*>([^<]+)</h2>", html)
        if h2_m:
            name = h2_m.group(1).strip()
            if name and len(name) >= 2:
                return name[:50]

    return ""


def enrich_from_detail(properties: list[dict], max_fetches: int = 30) -> None:
    """Fetch detail pages to extract: building name, room layout, building material.

    ALL properties are candidates for name enrichment (fallback names → real names).
    Layout/structure enrichment targets properties missing that data.
    """
    # Prioritize: properties needing name enrichment first, then layout/structure
    needs_name = [p for p in properties if _is_fallback_name(p.get("name", ""))]
    needs_layout = [p for p in properties if not p.get("layout_detail") or _is_floors_only(p.get("structure", ""))]

    # Build unique fetch list (name-needing first, then layout-needing, deduped)
    seen_urls: set[str] = set()
    to_fetch: list[dict] = []
    for p in needs_name + needs_layout:
        if p["url"] not in seen_urls and len(to_fetch) < max_fetches:
            seen_urls.add(p["url"])
            to_fetch.append(p)

    if not to_fetch:
        return

    name_needs = sum(1 for p in to_fetch if _is_fallback_name(p.get("name", "")))
    layout_needs = sum(1 for p in to_fetch if not p.get("layout_detail") or _is_floors_only(p.get("structure", "")))
    print(f"  詳細取得中... ({len(to_fetch)}件: 物件名{name_needs} + 間取り/構造{layout_needs})")
    enriched_name = 0
    enriched_layout = 0
    enriched_struct = 0

    for i, prop in enumerate(to_fetch):
        detail_html = fetch_page(prop["url"])
        if not detail_html:
            continue

        # Building name (from detail page title/heading)
        if _is_fallback_name(prop.get("name", "")):
            real_name = _extract_building_name_from_detail(detail_html, prop.get("source", ""))
            if real_name:
                prop["name"] = real_name
                enriched_name += 1

        # Room layout
        if not prop.get("layout_detail"):
            madori_matches = re.findall(
                r"(\d[RKLDKS]+\s*[×xX]\s*\d+\s*(?:戸|室)?)", detail_html
            )
            if madori_matches:
                prop["layout_detail"] = ", ".join(dict.fromkeys(m.strip() for m in madori_matches))
                enriched_layout += 1

        # Building material (RC/SRC/S造/木造) — only if currently floors-only
        if _is_floors_only(prop.get("structure", "")):
            mat_m = re.search(
                r"(RC造|SRC造|鉄筋コンクリート造|鉄骨鉄筋コンクリート造|S造|鉄骨造|軽量鉄骨造|木造)\s*\d*階建?",
                detail_html,
            )
            if mat_m:
                raw = mat_m.group(1)
                if "鉄骨鉄筋コンクリート" in raw or "SRC" in raw:
                    mat = "SRC造"
                elif "鉄筋コンクリート" in raw or raw == "RC造":
                    mat = "RC造"
                elif "鉄骨" in raw or raw in ("S造", "S造"):
                    mat = "S造"
                else:
                    mat = raw  # 木造 etc.
                floors_m = re.search(r"(\d+)階建", prop.get("structure", ""))
                prop["structure"] = f"{mat}{floors_m.group(0)}" if floors_m else mat
                enriched_struct += 1

        if (i + 1) % 5 == 0:
            print(f"    {i + 1}/{len(to_fetch)} done")
        time.sleep(1.0)

    print(f"  詳細取得: 物件名{enriched_name}件 / 間取り{enriched_layout}件 / 構造材質{enriched_struct}件")


def deduplicate_by_content(properties: list[dict]) -> list[dict]:
    """Deduplicate by (normalized_location, price_man, area_numeric).

    健美家 lists the same property under multiple 区 with different URLs.
    URL-based dedup misses these — content signature catches them.
    When duplicates are found, keep the one with the most specific address.
    """
    seen: dict[tuple, dict] = {}
    for p in properties:
        # Normalize location: strip to city+ward+町名 level
        loc = re.sub(r"[\d０-９]+[-ー丁番地号].*", "", p.get("location", "")).strip()
        # Use numeric price for comparison (text varies: "1億4,000万" vs "1億4000万")
        price = p.get("price_man", 0)
        # Extract numeric area for comparison ("295.46m²" → 295.46)
        area_m = re.search(r"([\d.]+)", p.get("area_text", ""))
        area_num = float(area_m.group(1)) if area_m else 0
        sig = (loc, price, round(area_num, 0))
        if sig in seen:
            existing = seen[sig]
            if len(p.get("location", "")) > len(existing.get("location", "")):
                seen[sig] = p
        else:
            seen[sig] = p
    deduped = list(seen.values())
    dup_count = len(properties) - len(deduped)
    if dup_count > 0:
        print(f"  コンテンツ重複除外: {dup_count}件 (同一物件・異なるURL)")
    return deduped


def save_results(properties: list[dict], city_key: str) -> Path:
    """Save results to pipe-delimited data file (15-column: score prepended).

    Properties are scored, sorted by score desc, and only Green (70+) are saved.
    """
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"ittomono_{city_key}_raw.txt"

    # Guard: never overwrite existing data with 0 results (scrape failure)
    if not properties and out_path.exists():
        existing_lines = [l for l in out_path.read_text(encoding="utf-8").splitlines()
                         if l and not l.startswith("#")]
        if existing_lines:
            print(f"  [GUARD] {out_path.name}: 0件取得 — 既存{len(existing_lines)}件を保護、上書きスキップ")
            return out_path

    # Content-based dedup (cross-source: same property, different URLs)
    properties = deduplicate_by_content(properties)

    # Score, sort, and keep top 25 with score >= 40
    # Threshold 40 (was 55) because pre-save scorer lacks price/location/CF axes
    # that report-time scorer has. Old buildings (築40+) get 0 for age → drop to 48
    # even with good station/units. Report scorer compensates with earthquake(+10)
    # and location(+10), so pre-save should not over-filter.
    for p in properties:
        p["score"] = score_ittomono(p)
    properties.sort(key=lambda x: x["score"], reverse=True)
    shortlist = [p for p in properties if p["score"] >= 40][:25]

    lines = [
        f"## 一棟もの検索結果 - {AREA_CONFIGS[city_key]['label']}",
        f"## 条件: {PRICE_MIN}万〜{PRICE_MAX}万",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(shortlist)}件 (全{len(properties)}件中スコア40+上位25)",
        "",
    ]

    for prop in shortlist:
        line = "|".join([
            str(prop["score"]),
            prop["source"],
            prop["name"],
            prop["price_text"],
            prop["location"],
            prop["area_text"],
            prop["built_text"],
            prop["station_text"],
            prop.get("structure", ""),
            prop.get("units", ""),
            prop.get("yield_text", ""),
            prop.get("layout_detail", ""),
            "",  # pet placeholder
            "",  # brokerage placeholder
            prop["url"],
        ])
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main():
    """Search all target cities for 一棟もの."""
    print(f"\u4e00\u68df\u3082\u306e\u7269\u4ef6\u691c\u7d22 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"\u6761\u4ef6: {PRICE_MIN}\u4e07\u301c{PRICE_MAX}\u4e07 (1.5\u5104\u301c2\u5104\u5186)")

    # In GHA, limit enrichment to avoid timeout (300s budget for entire script)
    import os
    is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
    enrich_limit = 10 if is_ci else 30

    for city_key in ["osaka", "fukuoka", "tokyo"]:
        # Search both sources
        rakumachi_props = search_rakumachi_ittomono(city_key)
        kenbiya_props = search_kenbiya_ittomono(city_key)

        # Merge and deduplicate (by location + price heuristic)
        props = rakumachi_props + kenbiya_props
        if props:
            # Enrich all sources: building name + layout + structure material
            enrich_from_detail(props, max_fetches=enrich_limit)
        out = save_results(props, city_key)
        green_count = sum(1 for p in props if p.get("score", 0) >= 40)
        print(f"  出力: {out} ({green_count}件厳選 / 全{len(props)}件 = 楽待{len(rakumachi_props)} + 健美家{len(kenbiya_props)})")


if __name__ == "__main__":
    main()
