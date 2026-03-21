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


def is_target_location(location: str, city_key: str) -> bool:
    """Check if property location matches target areas."""
    config = AREA_CONFIGS.get(city_key, {})
    wards = config.get("target_wards", [])
    areas = config.get("target_areas", [])
    return any(w in location for w in wards) or any(a in location for a in areas)


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
    """Search 楽待 for 一棟マンション (dim1001) + 一棟アパート (dim1002)."""
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

    for match in url_pattern.finditer(html):
        prop_url = match.group(1)
        prop_id = match.group(2)
        if prop_id in seen_ids:
            continue
        seen_ids.add(prop_id)

        if not prop_url.startswith("http"):
            prop_url = "https://www.rakumachi.jp" + prop_url

        start = max(0, match.start() - 2000)
        end = min(len(html), match.end() + 2000)
        context = html[start:end]

        prop = _extract_ittomono_fields(context, prop_url, prop_id, city_key, dim_label)
        if prop:
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

    # Name
    name = ""
    name_patterns = [
        r"\u4e00\u68df(?:\u30de\u30f3\u30b7\u30e7\u30f3|\u30a2\u30d1\u30fc\u30c8)\s+([^\s]{2,30})",
        r"(?:^|\s)([^\s]{2,}(?:\u30de\u30f3\u30b7\u30e7\u30f3|\u30a2\u30d1\u30fc\u30c8|\u30cf\u30a4\u30c4|\u30b3\u30fc\u30dd|\u30ec\u30b8\u30c7\u30f3\u30b9|\u30d3\u30eb|\u8358))",
    ]
    for pat in name_patterns:
        nm = re.search(pat, text)
        if nm:
            candidate = nm.group(1).strip()
            candidate = re.sub(r"^[})>\s]+", "", candidate)
            candidate = re.sub(r"[({<\s]+$", "", candidate)
            if len(candidate) >= 2 and not candidate.startswith("\u304a\u6c17\u306b\u5165\u308a"):
                name = candidate[:40]
                break
    if not name:
        name = f"\u697d\u5f85\u4e00\u68df#{prop_id}"

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


def enrich_layout_from_detail(properties: list[dict], max_fetches: int = 30) -> None:
    """Fetch detail pages to extract room layout for properties missing layout_detail."""
    missing = [p for p in properties if not p.get("layout_detail")]
    to_fetch = missing[:max_fetches]
    if not to_fetch:
        return
    print(f"  間取り詳細取得中... ({len(to_fetch)}件)")
    for i, prop in enumerate(to_fetch):
        detail_html = fetch_page(prop["url"])
        if not detail_html:
            continue
        # Extract room layout from detail page
        madori_matches = re.findall(
            r"(\d[RKLDKS]+\s*[×xX]\s*\d+\s*(?:戸|室)?)", detail_html
        )
        if madori_matches:
            prop["layout_detail"] = ", ".join(dict.fromkeys(m.strip() for m in madori_matches))
        if (i + 1) % 5 == 0:
            print(f"    {i + 1}/{len(to_fetch)} done")
        time.sleep(1.0)
    enriched = sum(1 for p in to_fetch if p.get("layout_detail"))
    print(f"  間取り詳細: {enriched}/{len(to_fetch)}件取得成功")


def save_results(properties: list[dict], city_key: str) -> Path:
    """Save results to pipe-delimited data file (14-column format for 一棟もの)."""
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"ittomono_{city_key}_raw.txt"

    lines = [
        f"## \u4e00\u68df\u3082\u306e\u691c\u7d22\u7d50\u679c - {AREA_CONFIGS[city_key]['label']}",
        f"## \u6761\u4ef6: {PRICE_MIN}\u4e07\u301c{PRICE_MAX}\u4e07",
        f"## \u53d6\u5f97\u65e5: {datetime.now().strftime('%Y-%m-%d')}",
        f"## \u4ef6\u6570: {len(properties)}\u4ef6",
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

    for city_key in ["osaka", "fukuoka", "tokyo"]:
        props = search_rakumachi_ittomono(city_key)
        if props:
            enrich_layout_from_detail(props, max_fetches=30)
            out = save_results(props, city_key)
            print(f"  \u51fa\u529b: {out}")
        else:
            save_results([], city_key)
            print(f"  \u6761\u4ef6\u306b\u5408\u3046\u7269\u4ef6\u306a\u3057")


if __name__ == "__main__":
    main()
