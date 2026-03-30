#!/usr/bin/env python3
"""Yield-focused property search — targets profitable investment properties.

Searches 楽待 with yield-optimized parameters:
- 区分 (dim2001): ≤3000万, ≥15㎡ (investment-grade condos, OC included)
- 一棟 (dim1001/dim1002): 3000-8000万 (small buildings, full-loan candidates)

Output:
- yield_{city}_raw.txt       (12-col, kubun format)
- yield_ittomono_{city}_raw.txt (15-col, ittomono format)
"""

import http.cookiejar
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
COOKIE_FILE = DATA_DIR / "cookies_rakumachi.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

# Cookie-based opener for authenticated requests (楽待 detail pages)
_opener = None


def _get_opener():
    """Get or create a URL opener with cookie support."""
    global _opener
    if _opener is not None:
        return _opener
    if COOKIE_FILE.exists():
        cj = http.cookiejar.MozillaCookieJar()
        try:
            cj.load(str(COOKIE_FILE), ignore_discard=True, ignore_expires=True)
        except (http.cookiejar.LoadError, OSError) as e:
            print(f"  [WARN] Cookie読み込みエラー: {e}")
            # Fallback: parse manually for malformed Netscape files
            cj = _load_cookies_fallback(COOKIE_FILE)
            if cj is None:
                return None
        _opener = build_opener(HTTPCookieProcessor(cj))
        print(f"  [INFO] 楽待Cookie読み込み: {len(cj)}個")
    return _opener


def _load_cookies_fallback(path: Path) -> http.cookiejar.CookieJar | None:
    """Parse Netscape cookie file manually when MozillaCookieJar fails."""
    import re
    cj = http.cookiejar.CookieJar()
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, domain_flag, cpath, secure, expires, name, value = parts[:7]
        cookie = http.cookiejar.Cookie(
            version=0, name=name, value=value,
            port=None, port_specified=False,
            domain=domain, domain_specified=domain.startswith("."),
            domain_initial_dot=domain.startswith("."),
            path=cpath, path_specified=bool(cpath),
            secure=secure == "TRUE",
            expires=int(expires) if expires and expires != "0" else None,
            discard=expires == "0",
            comment=None, comment_url=None,
            rest={}, rfc2109=False,
        )
        cj.set_cookie(cookie)
        count += 1
    if count == 0:
        return None
    return cj

# ── Yield-focused search parameters ──
# 区分: investment condos (smaller, cheaper = higher yield potential)
KUBUN_PRICE_MAX = 3000  # 3000万 (万円)
KUBUN_AREA_MIN = 15  # ㎡ (investment 1R/1K included)

# 一棟: small buildings (full-loan candidates if newer)
ITTOMONO_PRICE_MIN = 3000  # 3000万
ITTOMONO_PRICE_MAX = 8000  # 8000万

AREA_CONFIGS = {
    "osaka": {
        "label": "大阪",
        "rakumachi_area": "27",
        "pref": "大阪府",
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
        "pref": "福岡県",
        "target_wards": ["博多区", "中央区", "南区"],
        "target_areas": [
            "天神", "博多", "薬院", "平尾", "住吉", "祇園", "赤坂",
            "大濠", "渡辺通", "中洲", "春吉", "呉服町",
        ],
    },
    "tokyo": {
        "label": "東京",
        "rakumachi_area": "13",
        "pref": "東京都",
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


_pw_browser = None  # Shared Playwright browser
_pw_context = None


def _get_pw_context():
    """Get or create a Playwright browser context with Cloudflare warmup."""
    global _pw_browser, _pw_context
    if _pw_context is not None:
        return _pw_context
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        _pw_browser = pw.chromium.launch(headless=True)
        _pw_context = _pw_browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="ja-JP",
        )
        # Inject login cookies (session-related, not cf_clearance)
        if COOKIE_FILE.exists():
            cookies = _parse_cookie_file(COOKIE_FILE)
            # Only inject session cookies, not Cloudflare ones (browser needs its own)
            session_cookies = [c for c in cookies if c["name"] not in
                              ("cf_clearance", "__cf_bm", "FPID", "FPAU", "FPGSID", "FPLC")]
            if session_cookies:
                _pw_context.add_cookies(session_cookies)
        # Warm up: visit main page to get Cloudflare clearance
        page = _pw_context.new_page()
        page.goto("https://www.rakumachi.jp/", timeout=30000, wait_until="domcontentloaded")
        time.sleep(2)  # Let Cloudflare JS challenge resolve
        page.close()
        print(f"  [INFO] Playwright起動 + Cloudflare warmup完了")
        return _pw_context
    except Exception as e:
        print(f"  [WARN] Playwright起動失敗: {e}")
        return None


def _parse_cookie_file(path: Path) -> list[dict]:
    """Parse Netscape cookie file to Playwright cookie format."""
    cookies = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _, cpath, secure, expires, name, value = parts[:7]
        if not value:
            continue
        cookie = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": cpath,
            "secure": secure == "TRUE",
        }
        if expires and expires != "0":
            cookie["expires"] = int(expires)
        cookies.append(cookie)
    return cookies


def fetch_page(url: str, retries: int = 2) -> str | None:
    # Use Playwright for rakumachi detail pages (Cloudflare protected)
    if "rakumachi.jp" in url and "/show.html" in url:
        return _fetch_page_pw(url, retries)
    # Standard urllib for everything else
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except HTTPError as e:
            if e.code == 403:
                print(f"  [WARN] 403: {url[:80]}")
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


_pw_403_streak = 0  # Track consecutive 403s for adaptive delay


def _fetch_page_pw(url: str, retries: int = 2) -> str | None:
    """Fetch page using Playwright (bypasses Cloudflare)."""
    global _pw_403_streak
    ctx = _get_pw_context()
    if ctx is None:
        # Fallback to urllib with cookies
        opener = _get_opener()
        try:
            req = Request(url, headers=HEADERS)
            resp = opener.open(req, timeout=20) if opener else urlopen(req, timeout=20)
            data = resp.read().decode("utf-8", errors="ignore")
            resp.close()
            return data
        except (HTTPError, URLError) as e:
            print(f"  [WARN] fetch failed: {e}")
            return None
    for attempt in range(retries + 1):
        try:
            page = ctx.new_page()
            resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
            if resp and resp.status == 403:
                # Check if Cloudflare challenge page (has JS challenge)
                content = page.content()
                page.close()
                if "challenge-platform" in content or "cf-" in content[:2000]:
                    # Cloudflare challenge - wait and retry
                    _pw_403_streak += 1
                    delay = min(10, 3 * _pw_403_streak)
                    if attempt < retries:
                        time.sleep(delay)
                        continue
                print(f"  [WARN] 403: {url[:80]}")
                return None
            _pw_403_streak = 0  # Reset streak on success
            html = page.content()
            page.close()
            return html
        except Exception as e:
            try:
                page.close()
            except Exception:
                pass
            if attempt < retries:
                time.sleep(3)
                continue
            print(f"  [WARN] Playwright error: {e}")
            return None
    return None


def close_pw():
    """Close Playwright context. Call when done with batch operations."""
    global _pw_browser, _pw_context
    if _pw_context:
        try:
            _pw_context.close()
        except Exception:
            pass
        _pw_context = None
    if _pw_browser:
        try:
            _pw_browser.close()
        except Exception:
            pass
        _pw_browser = None


def is_target_location(location: str, city_key: str) -> bool:
    config = AREA_CONFIGS.get(city_key, {})
    wards = config.get("target_wards", [])
    areas = config.get("target_areas", [])
    city_prefixes = {"osaka": "大阪市", "fukuoka": "福岡市", "tokyo": "東京都"}
    prefix = city_prefixes.get(city_key, "")
    # Ward match: require city prefix (e.g., 福岡市博多区)
    ward_match = any(f"{prefix}{w}" in location or (not prefix and w in location) for w in wards)
    # Area match: also require city prefix to avoid false positives
    # e.g., 北九州市小倉北区赤坂 ≠ 福岡市赤坂
    area_match = (prefix in location and any(a in location for a in areas)) if prefix else any(a in location for a in areas)
    return ward_match or area_match


def parse_price_text(text: str) -> int:
    text = text.replace(",", "").replace("\u3000", "").strip()
    m_oku = re.search(r"(\d+(?:\.\d+)?)億", text)
    m_man = re.search(r"(\d+(?:\.\d+)?)万", text)
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


# =====================================================================
# 区分マンション (dim2001) — yield-focused
# =====================================================================

def search_kubun(city_key: str) -> list[dict]:
    """Search 楽待 for yield-focused 区分マンション."""
    config = AREA_CONFIGS[city_key]
    area_code = config["rakumachi_area"]
    print(f"\n=== 楽待 利回り区分 ({config['label']}) ===")

    base_url = "https://www.rakumachi.jp/syuuekibukken/area/prefecture/dim2001/"
    params = {
        "area": area_code,
        "pmax": str(KUBUN_PRICE_MAX),
        "areamin": str(KUBUN_AREA_MIN),
    }
    url = f"{base_url}?{urlencode(params)}"

    properties = []
    page = 1
    max_pages = 5

    while page <= max_pages:
        page_url = f"{url}&page={page}" if page > 1 else url
        print(f"  Page {page}...")
        html = fetch_page(page_url)
        if not html:
            break

        page_props = _parse_kubun_listings(html, city_key)
        if not page_props:
            break

        properties.extend(page_props)
        print(f"  -> {len(page_props)}件 (累計: {len(properties)})")

        if f"page={page + 1}" not in html and f">{page + 1}<" not in html:
            break
        page += 1
        time.sleep(1.5)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for p in properties:
        if p["url"] not in seen:
            seen.add(p["url"])
            deduped.append(p)

    print(f"  合計: {len(deduped)}件")
    return deduped


def _parse_kubun_listings(html: str, city_key: str) -> list[dict]:
    properties = []
    url_pattern = re.compile(
        r'href="((?:https://www\.rakumachi\.jp)?/syuuekibukken/[^"]*?/(\d{5,10})/[^"]*)"'
    )
    seen_ids = set()
    all_matches = list(url_pattern.finditer(html))

    for i, match in enumerate(all_matches):
        prop_url = match.group(1)
        prop_id = match.group(2)
        if prop_id in seen_ids:
            continue
        seen_ids.add(prop_id)

        if not prop_url.startswith("http"):
            prop_url = "https://www.rakumachi.jp" + prop_url

        start = match.start()
        end = all_matches[i + 1].start() if i + 1 < len(all_matches) else min(len(html), match.end() + 3000)
        context = html[start:end]

        prop = _extract_kubun_fields(context, prop_url, prop_id, city_key)
        if prop:
            properties.append(prop)

    return properties


def _extract_kubun_fields(context: str, url: str, prop_id: str, city_key: str) -> dict | None:
    text = re.sub(r"<[^>]+>", " ", context)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Price
    price_match = re.search(r"\d+(?:\.\d+)?億\s*\d*万?\s*円?", text)
    if not price_match:
        price_match = re.search(r"(\d{1,2},?\d{3})\s*万円", text)
    if not price_match:
        price_match = re.search(r"(\d{3,4})\s*万円", text)
    price_man = 0
    if price_match:
        price_man = parse_price_text(price_match.group(0))
    if price_man <= 0 or price_man > KUBUN_PRICE_MAX:
        return None

    price_text = f"{price_man}万円"

    # Area
    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", text)
    area_text = area_match.group(0).strip() if area_match else ""
    area_sqm = float(area_match.group(1)) if area_match else 0
    if area_sqm > 0 and area_sqm < KUBUN_AREA_MIN:
        return None

    # Location
    pref = AREA_CONFIGS[city_key]["pref"]
    loc_match = re.search(rf"({re.escape(pref)}[^\s,。、]{{2,20}})", text)
    location = loc_match.group(1) if loc_match else ""
    if not location or not is_target_location(location, city_key):
        return None

    # Year built
    year_match = re.search(r"(\d{4})年(?:\s*(\d{1,2})月)?(?:\s*築)?", text)
    built_text = year_match.group(0).strip() if year_match else ""

    # Station
    station_text = ""
    for pat in [
        r"((?:地下鉄|JR|阪急|阪神|南海|京阪|近鉄|西鉄)?[^\s「」]*?線\s*「[^」]+」\s*(?:駅\s*)?徒歩\s*\d+\s*分)",
        r"(「[^」]+」\s*(?:駅\s*)?徒歩\s*\d+\s*分)",
        r"([^\s。、！？]{1,10}駅\s*徒歩\s*\d+\s*分)",
    ]:
        sm = re.search(pat, text)
        if sm:
            station_text = sm.group(1).strip()
            break
    # Clean: remove description prefix and junk patterns
    if "。" in station_text:
        station_text = station_text.split("。")[-1].strip()
    # "最寄駅徒歩X分" is generic, not an actual station name
    if station_text.startswith("最寄駅"):
        station_text = ""

    # Layout
    layout_match = re.search(r"(\d[SLDK]+(?:\+S)?)", text)
    layout = layout_match.group(1) if layout_match else ""

    # Yield (楽待 always shows yield for investment props)
    yield_text = ""
    yield_match = re.search(r"(\d+(?:\.\d+)?)\s*[%％]", text)
    if yield_match:
        yv = float(yield_match.group(1))
        if 1.0 <= yv <= 30.0:
            yield_text = f"{yv}%"

    # Name
    name = ""
    name_patterns = [
        r"(?:区分マンション|マンション)\s+([^\s]{2,30})",
        r"(?:^|\s)([^\s]{3,}(?:ハイツ|コーポ|レジデンス|ビル|荘|パレス|マンション|テラス|プラザ|メゾン))",
    ]
    for pat in name_patterns:
        nm = re.search(pat, text)
        if nm:
            candidate = nm.group(1).strip()
            candidate = re.sub(r"^[})>\s]+", "", candidate)
            candidate = re.sub(r"[({<\s]+$", "", candidate)
            if len(candidate) >= 2 and not candidate.startswith("お気に入り") and not re.match(r"^\d+億", candidate):
                name = candidate[:40]
                break
    if not name:
        loc_short = location.replace(pref, "")[:10]
        name = f"楽待 {loc_short}#{prop_id[-4:]}"

    # OC detection from full listing text (before station cleanup)
    # 楽待の利回り区分: 利回り表示あり = ほぼ賃貸中（詳細ページで確認済み）
    # 明示的に「空室」「現況空」がある場合のみ非OC
    oc_keywords = ["賃貸中", "オーナーチェンジ", "入居者付", "入居中", "月額賃料", "年間収入", "満室"]
    vacant_keywords = ["現況空", "空室", "居住用"]
    is_explicitly_oc = any(kw in text for kw in oc_keywords)
    is_vacant = any(kw in text for kw in vacant_keywords)
    # 楽待 yield listings with yield % shown → default OC unless explicitly vacant
    is_oc = is_explicitly_oc or (yield_text and not is_vacant)

    return {
        "source": "楽待(利回り区分)",
        "name": name,
        "price_text": price_text,
        "price_man": price_man,
        "location": location,
        "area_text": area_text,
        "area_sqm": area_sqm,
        "built_text": built_text,
        "station_text": station_text,
        "layout": layout,
        "yield_text": yield_text,
        "is_oc": is_oc,
        "url": url,
    }


# =====================================================================
# 一棟もの (dim1001/dim1002) — lower price range
# =====================================================================

def search_ittomono(city_key: str) -> list[dict]:
    """Search 楽待 for small 一棟もの (3000-8000万)."""
    config = AREA_CONFIGS[city_key]
    area_code = config["rakumachi_area"]
    print(f"\n=== 楽待 小規模一棟 ({config['label']}) ===")

    all_properties = []

    for dim_code, dim_label in [("dim1001", "一棟マンション"), ("dim1002", "一棟アパート")]:
        print(f"\n  --- {dim_label} ({dim_code}) ---")
        base_url = f"https://www.rakumachi.jp/syuuekibukken/area/prefecture/{dim_code}/"
        params = {
            "area": area_code,
            "pmin": str(ITTOMONO_PRICE_MIN),
            "pmax": str(ITTOMONO_PRICE_MAX),
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

            page_props = _parse_ittomono_listings(html, city_key, dim_label)
            if not page_props:
                break

            all_properties.extend(page_props)
            print(f"  -> {len(page_props)}件 (累計: {len(all_properties)})")

            if f"page={page + 1}" not in html and f">{page + 1}<" not in html:
                break
            page += 1
            time.sleep(1.5)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for p in all_properties:
        if p["url"] not in seen:
            seen.add(p["url"])
            deduped.append(p)

    print(f"  合計: {len(deduped)}件")
    return deduped


def _parse_ittomono_listings(html: str, city_key: str, dim_label: str) -> list[dict]:
    properties = []
    url_pattern = re.compile(
        r'href="((?:https://www\.rakumachi\.jp)?/syuuekibukken/[^"]*?/(\d{5,10})/[^"]*)"'
    )
    seen_ids = set()
    all_matches = list(url_pattern.finditer(html))

    for i, match in enumerate(all_matches):
        prop_url = match.group(1)
        prop_id = match.group(2)
        if prop_id in seen_ids:
            continue
        seen_ids.add(prop_id)

        if not prop_url.startswith("http"):
            prop_url = "https://www.rakumachi.jp" + prop_url

        start = match.start()
        end = all_matches[i + 1].start() if i + 1 < len(all_matches) else min(len(html), match.end() + 3000)
        context = html[start:end]

        prop = _extract_ittomono_fields(context, prop_url, prop_id, city_key, dim_label)
        if prop:
            if is_target_location(prop["location"], city_key):
                properties.append(prop)

    return properties


def _extract_ittomono_fields(context: str, url: str, prop_id: str, city_key: str, dim_label: str) -> dict | None:
    text = re.sub(r"<[^>]+>", " ", context)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Price
    price_match = re.search(r"\d+(?:\.\d+)?億\s*\d*万?\s*円?", text)
    if not price_match:
        price_match = re.search(r"(\d{1,2},?\d{3,4})\s*万円", text)
    price_man = 0
    price_text = ""
    if price_match:
        price_man = parse_price_text(price_match.group(0))
        if price_man >= 10000:
            oku = price_man // 10000
            man = price_man % 10000
            price_text = f"{oku}億{man}万円" if man > 0 else f"{oku}億円"
        else:
            price_text = f"{price_man}万円"

    if price_man < ITTOMONO_PRICE_MIN or price_man > ITTOMONO_PRICE_MAX:
        return None

    # Location
    pref = AREA_CONFIGS[city_key]["pref"]
    loc_match = re.search(rf"({re.escape(pref)}[^\s,。、]{{2,20}})", text)
    location = loc_match.group(1) if loc_match else ""
    if not location:
        return None

    # Area
    area_text = ""
    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m[²2]|㎡)", text)
    if area_match:
        area_text = area_match.group(0).strip()

    # Year built
    year_match = re.search(r"(\d{4})年(?:\s*(\d{1,2})月)?(?:\s*築)?", text)
    built_text = year_match.group(0).strip() if year_match else ""

    # Station
    station_text = ""
    for pat in [
        r"((?:地下鉄|JR|阪急|阪神|南海|京阪|近鉄|西鉄)?[^\s「」]*?線\s*「[^」]+」\s*(?:駅\s*)?徒歩\s*\d+\s*分)",
        r"(「[^」]+」\s*(?:駅\s*)?徒歩\s*\d+\s*分)",
        r"([^\s]+(?:駅)\s*徒歩\s*\d+\s*分)",
    ]:
        sm = re.search(pat, text)
        if sm:
            station_text = sm.group(1).strip()
            break

    # Structure
    structure = ""
    for pat in [
        r"(RC造|SRC造|鉄筋コンクリート造|鉄骨鉄筋コンクリート造)",
        r"(S造|鉄骨造|重量鉄骨造|軽量鉄骨造)",
        r"(木造)",
    ]:
        sm = re.search(pat, text)
        if sm:
            raw_struct = sm.group(1)
            if "鉄骨鉄筋コンクリート" in raw_struct:
                structure = "SRC造"
            elif "鉄筋コンクリート" in raw_struct:
                structure = "RC造"
            elif "鉄骨" in raw_struct:
                structure = "S造"
            else:
                structure = raw_struct
            break
    # Add floors
    floors_m = re.search(r"(\d+)階建", text)
    if floors_m:
        structure = (structure + floors_m.group(0)) if structure else floors_m.group(0)

    # Units
    units = ""
    units_m = re.search(r"(\d+)\s*(?:戸|室|部屋|units)", text)
    if units_m:
        units = units_m.group(1) + "戸"

    # Yield
    yield_text = ""
    yield_match = re.search(r"(\d+(?:\.\d+)?)\s*[%％]", text)
    if yield_match:
        yv = float(yield_match.group(1))
        if 1.0 <= yv <= 30.0:
            yield_text = f"{yv}%"

    # Layout detail
    layout_detail = ""
    madori_matches = re.findall(r"(\d[RKLDKS]+\s*[×xX]\s*\d+\s*(?:戸|室)?)", text)
    if madori_matches:
        layout_detail = ", ".join(dict.fromkeys(m.strip() for m in madori_matches))

    # Name
    name = ""
    _type_labels = {"1棟マンション", "1棟アパート", "一棟マンション", "一棟アパート", "マンション", "アパート"}
    for pat in [
        r"[1一]棟(?:マンション|アパート)\s+([^\s]{2,30})",
        r"(?:^|\s)([^\s]{3,}(?:ハイツ|コーポ|レジデンス|ビル|荘|パレス|ガーデン|テラス|プラザ|グランド|メゾン|フォレスト))",
    ]:
        nm = re.search(pat, text)
        if nm:
            candidate = nm.group(1).strip()
            candidate = re.sub(r"^[})>\s]+", "", candidate)
            candidate = re.sub(r"[({<\s]+$", "", candidate)
            if (len(candidate) >= 2 and candidate not in _type_labels
                    and not candidate.startswith("お気に入り")
                    and not re.match(r"^\d+億", candidate)):
                name = candidate[:40]
                break
    # Strip 【...】prefix from names (e.g., "【価格改定】リッシュハウス伊都" → "リッシュハウス伊都")
    if name:
        name = re.sub(r"^(?:【[^】]*】)+\s*", "", name).strip()
        # Also strip leading ▶▲■◆ etc. and trailing ！
        name = re.sub(r"^[▶▲■◆◇●★☆※◎！]+\s*", "", name).strip()
        name = re.sub(r"[！!]+$", "", name).strip()
    if not name:
        loc_short = location.replace(pref, "")[:10]
        name = f"楽待 {loc_short}#{prop_id[-4:]}"

    return {
        "source": f"楽待({dim_label})",
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


# =====================================================================
# Scoring (simplified — report-level scoring done in generate_market.py)
# =====================================================================

def score_ittomono(prop: dict) -> int:
    """Quick score for pre-save filtering (0-100)."""
    score = 0

    # Yield (30)
    ym = re.search(r"([\d.]+)%", prop.get("yield_text", ""))
    if ym:
        yv = float(ym.group(1))
        score += 30 if yv >= 7 else 25 if yv >= 6 else 20 if yv >= 5 else 15 if yv >= 4 else 5
    else:
        score += 10

    # Structure (20)
    st = prop.get("structure", "")
    if "RC" in st or "SRC" in st:
        score += 20
    elif "S造" in st or "鉄骨" in st:
        score += 15
    elif "木造" in st:
        score += 5
    else:
        score += 8

    # Age (20)
    bm = re.search(r"(\d{4})年", prop.get("built_text", ""))
    if bm:
        age = 2026 - int(bm.group(1))
        score += 20 if age < 10 else 15 if age < 20 else 10 if age < 30 else 5 if age < 40 else 0

    # Units (15)
    um = re.search(r"(\d+)", prop.get("units", ""))
    if um:
        uv = int(um.group(1))
        score += 15 if uv >= 10 else 12 if uv >= 6 else 8 if uv >= 3 else 3
    else:
        score += 5

    # Station (15)
    sm = re.search(r"(\d+)\s*分", prop.get("station_text", ""))
    if sm:
        mins = int(sm.group(1))
        score += 15 if mins <= 5 else 10 if mins <= 10 else 5 if mins <= 15 else 0

    return score


# =====================================================================
# Enrich from detail page
# =====================================================================

def _is_fallback_name(name: str) -> bool:
    """Check if name is ad-copy / not a real building name → needs detail page fetch."""
    if not name:
        return True
    if re.match(r"^楽待\s", name):
        return True
    # Names starting with ad markers
    if re.match(r"^[【▶▲■◆◇●★☆※◎]+", name):
        return True
    # Building name patterns — if present, it's likely a real name
    bldg_suffixes = ["マンション", "ハイツ", "コーポ", "レジデンス", "ビル", "荘",
                     "パレス", "テラス", "プラザ", "メゾン", "ガーデン", "パーク",
                     "ハウス", "ドーム", "タワー", "コート", "シャトー", "グラン",
                     "ステート", "ロイヤル", "エステート", "フォレスト", "シティ",
                     "アーバン", "サンライズ", "サニー", "ライオンズ", "ダイアパレス",
                     "アンピール", "ピュアドーム", "GE"]
    if any(s in name for s in bldg_suffixes):
        return False
    # No building suffix → likely ad-copy → fetch detail page
    return True


def _extract_detail_fields(html: str, prop: dict) -> bool:
    """Extract OC status, annual income, management fees from detail page.

    Returns True if any field was enriched.
    """
    text = re.sub(r"<[^>]+>", "|", html)
    text = re.sub(r"\|+", "|", text)
    text = re.sub(r"\s+", " ", text).strip()
    changed = False

    # Building name from h1
    m_name = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
    if m_name:
        name = m_name.group(1).strip()
        if name and len(name) >= 2 and "楽待" not in name and "物件一覧" not in name:
            prop["name"] = name[:50]
            changed = True

    # 現況: 賃貸中 / 空室 / 賃貸中（満室）
    # Flattened HTML: "現況| |現況| | | | |賃貸中|" — skip whitespace-only pipes
    m_status = re.search(r"現況(?:\| *)*\|(賃貸中[^|]*|空室[^|]*|空[^|]*)", text)
    if m_status:
        status = m_status.group(1).strip()
        if "賃貸中" in status or "満室" in status:
            prop["is_oc"] = True
            changed = True
        elif "空" in status:
            prop["is_oc"] = False
            changed = True

    # 想定年間収入: 90.0万円 (7.5万円/月)
    # Flattened: "想定年間収入| |90.0万円|"
    m_income = re.search(r"想定年間収入(?:\| *)*\|([\d,.]+)万円", text)
    if m_income:
        try:
            annual_man = float(m_income.group(1).replace(",", ""))
            prop["annual_income_man"] = annual_man
            changed = True
        except ValueError:
            pass

    # 管理費（月額）: X円 / 修繕積立金（月額）: X円
    m_kanri = re.search(r"管理費（月額）(?:\| *)*\|([\d,]+)円", text)
    m_shuuzen = re.search(r"修繕積立金（月額）(?:\| *)*\|([\d,]+)円", text)
    if m_kanri or m_shuuzen:
        kanri = int(m_kanri.group(1).replace(",", "")) if m_kanri else 0
        shuuzen = int(m_shuuzen.group(1).replace(",", "")) if m_shuuzen else 0
        prop["maintenance_fee"] = kanri + shuuzen
        changed = True

    return changed


def _build_name_xref() -> dict[str, str]:
    """Build cross-reference of (location_prefix, area) → building name from all data files.

    Uses F宅建, SUUMO, etc. as reliable name sources to fix 楽待 ad-copy names.
    """
    xref: dict[str, str] = {}
    for pattern in ["ftakken_*_raw.txt", "suumo_*_raw.txt", "athome_*_raw.txt",
                     "restate_*_raw.txt", "yahoo_*_raw.txt", "cowcamo_*_raw.txt",
                     "ftakken_*_budget_raw.txt"]:
        for f in sorted(DATA_DIR.glob(pattern)):
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|")
                if len(parts) < 6:
                    continue
                name = parts[1].strip()
                if not name or _is_fallback_name(name):
                    continue
                loc = parts[3].strip()
                area_text = parts[4].strip()
                # Key: first 8 chars of location + area (e.g. "福岡市南区屋形原|63")
                area_m = re.search(r"([\d.]+)", area_text)
                area_int = str(int(float(area_m.group(1)))) if area_m else ""
                if loc and area_int:
                    # Use ward-level location (first ~8 chars after stripping prefecture)
                    loc_key = re.sub(r"^(東京都|大阪府|京都府|北海道|.{2,3}県)", "", loc)[:8]
                    key = f"{loc_key}|{area_int}"
                    if key not in xref:
                        xref[key] = name
    return xref


def enrich_from_detail(properties: list[dict], max_fetches: int = 20) -> None:
    """Fetch detail pages to enrich: name, OC status, annual income, fees.

    Also cross-references other data sources (F宅建, SUUMO) for building names
    when detail page is unavailable (403).
    """
    # Phase 1: Cross-reference names from other data sources (no network needed)
    # Apply to ALL 楽待 properties — listing page names are often wrong
    # (e.g., "博多駅前ビル" should be "メゾン・ド・プレジール")
    xref = _build_name_xref()
    xref_fixed = 0
    for prop in properties:
        loc = prop.get("location", "")
        area_text = prop.get("area_text", "")
        area_m = re.search(r"([\d.]+)", area_text)
        area_int = str(int(float(area_m.group(1)))) if area_m else ""
        # Normalize: strip full prefecture prefix, then first 8 chars
        loc_norm = re.sub(r"^(東京都|大阪府|京都府|北海道|.{2,3}県)", "", loc)
        loc_key = loc_norm[:8]
        key = f"{loc_key}|{area_int}"
        if key in xref:
            xref_name = xref[key]
            old_name = prop.get("name", "")
            # Only replace if xref name is different and looks more reliable
            if xref_name != old_name and (
                _is_fallback_name(old_name) or
                # 楽待 listing names can be wrong even with building suffixes
                ("楽待" in prop.get("source", "") or "rakumachi" in prop.get("url", ""))
            ):
                prop["name"] = xref_name
                xref_fixed += 1
    if xref_fixed:
        print(f"  クロスリファレンス: {xref_fixed}件の物件名を補完")

    # Phase 2: Fetch detail pages for remaining fallback names + all for OC/rent/fees
    fallback = [p for p in properties if _is_fallback_name(p.get("name", ""))]
    non_fallback = [p for p in properties if not _is_fallback_name(p.get("name", ""))]
    to_fetch = (fallback + non_fallback)[:max_fetches]
    if not to_fetch:
        return

    print(f"  詳細取得中... ({len(to_fetch)}件)")
    enriched = 0

    for prop in to_fetch:
        html = fetch_page(prop["url"])
        if not html:
            continue
        if _extract_detail_fields(html, prop):
            enriched += 1
        time.sleep(1.0)

    print(f"  詳細取得: {enriched}件")


# =====================================================================
# Save
# =====================================================================

def save_kubun(properties: list[dict], city_key: str) -> Path:
    """Save kubun results in 12-column pipe format."""
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"yield_{city_key}_raw.txt"

    lines = [
        f"## 利回りフォーカス区分 - {AREA_CONFIGS[city_key]['label']}",
        f"## 条件: ≤{KUBUN_PRICE_MAX}万, ≥{KUBUN_AREA_MIN}㎡",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(properties)}件",
        "",
    ]

    for p in properties:
        # 12-col: source|name|price|location|area|built|station|layout|pet(=OC flag)|brokerage|maintenance|url
        # brokerage: yield + annual income (from detail page)
        brok_parts = []
        if p.get("yield_text"):
            brok_parts.append(f"利回り{p['yield_text']}")
        if p.get("annual_income_man"):
            brok_parts.append(f"年間収入{p['annual_income_man']}万円")
        brokerage = " ".join(brok_parts)
        # maintenance: from detail page or empty
        maint = f"管理費{p['maintenance_fee']}円" if p.get("maintenance_fee") else ""
        line = "|".join([
            p["source"],
            p["name"],
            p["price_text"],
            p["location"],
            p["area_text"],
            p["built_text"],
            p["station_text"],
            p.get("layout", ""),
            "OC" if p.get("is_oc") else "",  # pet column → OC marker
            brokerage,
            maint,
            p["url"],
        ])
        lines.append(line)

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def save_ittomono(properties: list[dict], city_key: str) -> Path:
    """Save ittomono results in 15-column pipe format (with score)."""
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"yield_ittomono_{city_key}_raw.txt"

    # Score and sort
    for p in properties:
        p["score"] = score_ittomono(p)
    properties.sort(key=lambda x: x["score"], reverse=True)
    shortlist = [p for p in properties if p["score"] >= 30][:25]

    lines = [
        f"## 小規模一棟 利回りフォーカス - {AREA_CONFIGS[city_key]['label']}",
        f"## 条件: {ITTOMONO_PRICE_MIN}万〜{ITTOMONO_PRICE_MAX}万",
        f"## 取得日: {datetime.now().strftime('%Y-%m-%d')}",
        f"## 件数: {len(shortlist)}件 (全{len(properties)}件中)",
        "",
    ]

    for p in shortlist:
        # 15-col: score|source|name|price|location|area|built|station|structure|units|yield|layout_detail|pet|brokerage|url
        line = "|".join([
            str(p["score"]),
            p["source"],
            p["name"],
            p["price_text"],
            p["location"],
            p["area_text"],
            p["built_text"],
            p["station_text"],
            p.get("structure", ""),
            p.get("units", ""),
            p.get("yield_text", ""),
            p.get("layout_detail", ""),
            "",  # pet
            "",  # brokerage
            p["url"],
        ])
        lines.append(line)

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# =====================================================================
# Main
# =====================================================================

def main():
    print(f"利回りフォーカス検索 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"区分: ≤{KUBUN_PRICE_MAX}万, ≥{KUBUN_AREA_MIN}㎡")
    print(f"一棟: {ITTOMONO_PRICE_MIN}万〜{ITTOMONO_PRICE_MAX}万")

    for city_key in ["osaka", "fukuoka", "tokyo"]:
        label = AREA_CONFIGS[city_key]["label"]

        # 区分
        kubun_props = search_kubun(city_key)
        if kubun_props:
            enrich_from_detail(kubun_props, max_fetches=40)
        kubun_out = save_kubun(kubun_props, city_key)
        print(f"  区分: {kubun_out} ({len(kubun_props)}件)")

        # 一棟もの
        ittomono_props = search_ittomono(city_key)
        if ittomono_props:
            enrich_from_detail(ittomono_props, max_fetches=15)
        ittomono_out = save_ittomono(ittomono_props, city_key)
        green = sum(1 for p in ittomono_props if p.get("score", 0) >= 30)
        print(f"  一棟: {ittomono_out} ({green}件厳選 / 全{len(ittomono_props)}件)")


if __name__ == "__main__":
    main()
