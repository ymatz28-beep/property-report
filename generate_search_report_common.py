from __future__ import annotations

import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Make the shared lib importable
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_LIB_ROOT = _THIS_DIR.parent  # …/Documents/Projects (local)
for p in [str(_THIS_DIR), str(_LIB_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from lib.renderer import create_env  # noqa: E402
from revenue_calc import InvestmentParams, analyze as revenue_analyze  # noqa: E402

# ── ハードフィルタ定数 ──
# サブリース: 賃料改定不可 → 投資対象外（中野さん知見 2026-04-02）
_SUBLEASE_KEYWORDS = ["サブリース", "家賃保証", "一括借上", "借上げ", "マスターリース"]
# ペット不可: 区分はハード除外（チワワ3kg必須）。一棟はオーナー判断なので除外しない
_PET_NG_KEYWORDS = ["ペット不可", "ペット飼育不可", "ペット禁止", "動物不可", "犬猫不可"]


# ── ハードフィルタ関数（テスト可能 + Noneガード） ──

def is_sublease(r) -> bool:
    """サブリース物件判定。PropertyRow or dict対応。"""
    name = getattr(r, "name", "") or (r.get("name", "") if isinstance(r, dict) else "") or ""
    minpaku = getattr(r, "minpaku_status", "") or (r.get("minpaku_status", "") if isinstance(r, dict) else "") or ""
    raw = getattr(r, "raw_line", "") or (r.get("raw_line", "") if isinstance(r, dict) else "") or ""
    text = f"{name} {minpaku} {raw}"
    return any(kw in text for kw in _SUBLEASE_KEYWORDS)


def is_pet_ng(r) -> bool:
    """ペット不可判定（区分用）。PropertyRow or dict対応。"""
    pet = getattr(r, "pet_status", "") or (r.get("pet_status", "") if isinstance(r, dict) else "") or ""
    name = getattr(r, "name", "") or (r.get("name", "") if isinstance(r, dict) else "") or ""
    minpaku = getattr(r, "minpaku_status", "") or (r.get("minpaku_status", "") if isinstance(r, dict) else "") or ""
    raw = getattr(r, "raw_line", "") or (r.get("raw_line", "") if isinstance(r, dict) else "") or ""
    text = f"{pet} {name} {minpaku} {raw}"
    return pet == "不可" or any(kw in text for kw in _PET_NG_KEYWORDS)


def site_header_css() -> str:
    return """
/* ── Shared Gnav ── */
.site-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: var(--gnav-height, 52px);
  background: rgba(22,24,31,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  position: sticky; top: 0; z-index: var(--z-nav, 100);
}
.site-nav { display: flex; gap: 4px; }
.site-nav a {
  color: #71717a; text-decoration: none; font-size: 13px; font-weight: 500;
  padding: 6px 14px; border-radius: 6px; transition: background .15s, color .15s;
}
.site-nav a:hover, .site-nav a[aria-current="page"] {
  background: rgba(255,255,255,0.065); color: #f5f5f7;
}
.nav-toggle { display: none; }
.nav-toggle-label { display: none; cursor: pointer; padding: 8px; }
.nav-toggle-label span,
.nav-toggle-label span::before,
.nav-toggle-label span::after {
  display: block; background: #f5f5f7; height: 2px; width: 20px;
  border-radius: 2px; position: relative; transition: .3s;
}
.nav-toggle-label span::before,
.nav-toggle-label span::after { content: ''; position: absolute; }
.nav-toggle-label span::before { top: -6px; }
.nav-toggle-label span::after { top: 6px; }
@media (max-width: 640px) {
  .nav-toggle-label { display: flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; }
  .site-nav {
    display: none; flex-direction: column; gap: 0;
    position: absolute; top: var(--gnav-height, 52px); left: 0; right: 0; z-index: var(--z-modal, 200);
    background: rgba(22,24,31,0.95); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    padding: 8px 0;
  }
  .site-nav a { padding: 12px 24px; border-radius: 0; font-size: 14px; }
  .nav-toggle:checked ~ .site-nav { display: flex; }
  .nav-toggle:checked ~ .nav-toggle-label span { background: transparent; }
  .nav-toggle:checked ~ .nav-toggle-label span::before { top: 0; transform: rotate(45deg); }
  .nav-toggle:checked ~ .nav-toggle-label span::after { top: 0; transform: rotate(-45deg); }
}
"""


def site_header_html() -> str:
    from lib.renderer import get_nav_html  # SSoT: lib/renderer.PUBLIC_NAV
    return get_nav_html(scope="public", current_page="Property")


def global_nav_css() -> str:
    return """
.gnav{position:sticky;top:var(--gnav-height,52px);z-index:var(--z-subnav,90);background:rgba(10,12,18,.92);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.08);padding:0;font-family:'Inter','Noto Sans JP',sans-serif;scrollbar-width:none}
.gnav-inner{max-width:1280px;margin:0 auto;display:flex;align-items:center;gap:0;padding:0 16px;overflow-x:auto;white-space:nowrap}
.gnav::-webkit-scrollbar{display:none}
.gnav a{display:inline-block;padding:8px 14px;font-size:11px;font-weight:600;color:rgba(255,255,255,.5);text-decoration:none;letter-spacing:.04em;transition:color .2s}
.gnav a:hover{color:#fff}
.gnav a.cur{color:#fff;border-bottom:2px solid #3b9eff}
@media(max-width:640px){.gnav a{padding:10px 10px;font-size:10px;min-height:44px;display:inline-flex;align-items:center}}
"""


def global_nav_html(current: str = "") -> str:
    links = []
    for p in _NAV_PAGES:
        cls = ' class="cur"' if p["href"] == current else ""
        links.append(f'<a href="{p["href"]}"{cls}>{p["label"]}</a>')
    return f'<div class="gnav"><div class="gnav-inner">{"".join(links)}</div></div>'


OSAKA_R_ROWS = [
    "扇町公園の近くでペットと暮らす|4580万円|北区天神橋3丁目|66.21m2|1976年|天満/扇町 徒歩6分|1LDK+FS|民泊可否未確認|https://www.realosaka.jp/estate/2816/",
    "贅沢な二人暮らし|4100万円|中央区谷町5丁目|67.15m2|1980年|谷町六丁目 徒歩2分|1LDK|民泊禁止|https://www.realosaka.jp/estate/2823/",
    "暮らしが教える、この魅力。|3480万円|北区東天満2丁目|60.39m2|1980年|天満宮 徒歩5分|LDK|民泊禁止|https://www.realosaka.jp/estate/2732/",
    "立ち止まる余白|5980万円|中央区谷町5丁目|60.46m2|2005年|谷町六丁目 徒歩3分|1LDK|民泊可否未確認（予算超過）|https://www.realosaka.jp/estate/2847/",
]


@dataclass
class ReportConfig:
    city_key: str
    city_label: str
    accent: str
    accent_rgb: str
    data_path: Path
    output_path: Path
    hero_conditions: list[str]
    search_condition_bullets: list[str]
    investor_notes: list[str]
    include_osaka_r: bool = False
    extra_data_paths: list[Path] = field(default_factory=list)  # Additional site data files
    deepdive_links: list[dict] = field(default_factory=list)  # [{title, url, desc}] pinned individual deep-dive reports


@dataclass
class PropertyRow:
    source: str
    name: str
    price_text: str
    location: str
    area_text: str
    built_text: str
    station_text: str
    layout: str
    url: str
    minpaku_status: str = ""
    pet_status: str = ""  # "可", "相談可", "不可", ""
    brokerage_text: str = ""  # "無料", "半額", "割引", "3%+6.6万", ""
    maintenance_fee_text: str = ""  # "管理費8,000円+修繕5,400円" or total yen/月
    raw_line: str = ""
    maintenance_fee: int = 0  # Total monthly fee in yen (管理費+修繕積立金)
    price_man: int = 0
    area_sqm: float | None = None
    built_year: int | None = None
    built_month: int | None = None
    walk_min: int | None = None
    bucket_label: str = "Other"
    score_breakdown: dict[str, int] = field(default_factory=dict)
    total_score: int = 0
    tier_label: str = ""
    tier_class: str = ""
    tier_color: str = ""
    detail_comment: str = ""
    pet_score: int = 0
    structure: str = ""  # RC造, SRC造, S造, 木造, etc.
    yield_text: str = ""
    rent_source: str = ""
    est_monthly_rent: str = ""
    rent_per_sqm: int = 0
    price_per_sqm: str = ""
    revenue: dict | None = None


def parse_price_man(text: str) -> int:
    m = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not m:
        return 0
    return int(float(m.group(1)))


def parse_area_sqm(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*m2", text, re.IGNORECASE)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def parse_built(text: str) -> tuple[int | None, int | None]:
    y = re.search(r"(\d{4})年", text)
    m = re.search(r"年\s*(\d{1,2})月", text)
    if y:
        year = int(y.group(1))
        # Sanity check: SUUMO等の掲載側入力ミスで明治期等の非現実的な年が入ることがある
        # (実例: chukoikkodate/osaka/nc_20908754 が「1868年1月」と表記, 2026-07-08)
        if not (1900 <= year <= 2026):
            return None, None
        return year, int(m.group(1)) if m else 1
    return None, None


def parse_maintenance_fee(text: str) -> int:
    """Parse maintenance fee text to total monthly yen.

    Handles formats like:
    - "15400" (raw yen)
    - "15,400円/月"
    - "管理費8,000円+修繕5,400円"
    - "8000+5400"
    - "5830" (very low total for older properties)
    """
    if not text:
        return 0
    text = text.replace(",", "").replace("　", "").replace(" ", "")
    # Try sum of multiple amounts: "管理費8000円+修繕積立金5400円" or "8000+5400"
    amounts = re.findall(r"(\d+)\s*円?", text)
    if amounts:
        total = sum(int(a) for a in amounts)
        # Sanity check: monthly fee should be 500-200,000 yen
        # (some old/small condos have fees under 1000 per component)
        if 500 <= total <= 200000:
            return total
    # Single number
    m = re.search(r"(\d+)", text)
    if m:
        val = int(m.group(1))
        if 500 <= val <= 200000:
            return val
    return 0


def parse_walk_minutes(station_text: str) -> int | None:
    if "バス" in station_text:
        return None
    # 複数駅対応: 全ての「徒歩N分」から最小値を返す
    matches = re.findall(r"徒歩\s*(\d+)\s*分", station_text)
    if matches:
        return min(int(m) for m in matches)
    return None


def extract_search_meta(data_path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in data_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("##"):
            continue
        if "取得日:" in s:
            meta["search_date"] = s.split("取得日:", 1)[1].strip()
        elif "条件:" in s:
            meta["conditions"] = s.split("条件:", 1)[1].strip()
        elif "件数:" in s:
            meta["raw_count"] = s.split("件数:", 1)[1].strip()
        elif "検索結果" in s:
            meta["title"] = s.lstrip("# ").strip()
    return meta


_STATION_NAME_RE = re.compile(r"(?:駅」?|バス停)\s*徒歩[約]?\s*\d+分")
# Name is ONLY station/access info — no real building name embedded
_STATION_ONLY_RE = re.compile(
    r"^[\s☆◆◇●■★▲▼※♪\u3000]*"  # leading decorations
    r"(?:(?:JR|西鉄|地下鉄|福岡市|東海道|九州|鹿児島|博多南|篠栗|香椎|東武|東急|京王|小田急|"
    r"都営|東京メトロ|ＪＲ|ゆりかもめ)?"
    r"[\u4e00-\u9fff\uff08\uff09\u300c\u300d（）「」\w]*"
    r"(?:駅|バス停)[\s「」]*徒歩[約]?\s*\d+分[！!]?"
    r"[\s,、]*)+$"
)


def _has_building_name(name: str) -> bool:
    """Check if name contains a real building/mansion name (katakana or known suffixes)."""
    # 3+ consecutive katakana chars = likely a building name
    if re.search(r"[\u30A0-\u30FF]{3,}", name):
        return True
    # Known building name suffixes in kanji
    if re.search(r"[\u4e00-\u9fff](?:荘|館|邸|苑|棟|号棟)", name):
        return True
    return False


def _fix_station_name_property(row: "PropertyRow") -> None:
    """If the name field is ONLY a station access description (ftakken scraper artifact),
    replace it with '{区/市名} {layout}' fallback per UIラベル日本語化ルール.
    Skip if a real building name (katakana 3+ chars) is embedded."""
    if not _STATION_NAME_RE.search(row.name):
        return
    # If name contains a real building name, keep it
    if _has_building_name(row.name):
        return
    loc = row.location.strip()
    area_m = re.search(r"([\u4e00-\u9fff]{2,6}[区市町村])", loc)
    area_label = area_m.group(1) if area_m else loc[:6] if loc else "物件"
    layout = row.layout.strip() if hasattr(row, "layout") and row.layout else ""
    fallback = f"{area_label} {layout}".strip() if layout else area_label
    print(f"  [FIX] 駅名→物件名修正(区分): '{row.name}' → '{fallback}'")
    row.name = fallback


def parse_data_file(data_path: Path, default_source: str = "SUUMO") -> list[PropertyRow]:
    rows: list[PropertyRow] = []
    for line in data_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) == 8:
            # Standard SUUMO format: name|price|location|area|built|station|layout|url
            row = PropertyRow(
                source=default_source,
                name=parts[0],
                price_text=parts[1],
                location=parts[2],
                area_text=parts[3],
                built_text=parts[4],
                station_text=parts[5],
                layout=parts[6],
                url=parts[7],
                raw_line=s,
            )
        elif len(parts) == 10:
            # Extended format: source|name|price|location|area|built|station|layout|pet|url
            row = PropertyRow(
                source=parts[0] or default_source,
                name=parts[1],
                price_text=parts[2],
                location=parts[3],
                area_text=parts[4],
                built_text=parts[5],
                station_text=parts[6],
                layout=parts[7],
                pet_status=parts[8],
                url=parts[9],
                raw_line=s,
            )
        elif len(parts) == 11:
            # Full format: source|name|price|location|area|built|station|layout|pet|brokerage|url
            row = PropertyRow(
                source=parts[0] or default_source,
                name=parts[1],
                price_text=parts[2],
                location=parts[3],
                area_text=parts[4],
                built_text=parts[5],
                station_text=parts[6],
                layout=parts[7],
                pet_status=parts[8],
                brokerage_text=parts[9],
                url=parts[10],
                raw_line=s,
            )
        elif len(parts) == 12:
            # Extended format with maintenance fee: source|name|price|location|area|built|station|layout|pet|brokerage|maintenance|url
            row = PropertyRow(
                source=parts[0] or default_source,
                name=parts[1],
                price_text=parts[2],
                location=parts[3],
                area_text=parts[4],
                built_text=parts[5],
                station_text=parts[6],
                layout=parts[7],
                pet_status=parts[8],
                brokerage_text=parts[9],
                maintenance_fee_text=parts[10],
                url=parts[11],
                raw_line=s,
            )
        elif len(parts) in (13, 14):
            # 13-col: ...|structure  /  14-col: ...|structure|conditions
            row = PropertyRow(
                source=parts[0] or default_source,
                name=parts[1],
                price_text=parts[2],
                location=parts[3],
                area_text=parts[4],
                built_text=parts[5],
                station_text=parts[6],
                layout=parts[7],
                pet_status=parts[8],
                brokerage_text=parts[9],
                maintenance_fee_text=parts[10],
                url=parts[11],
                structure=parts[12],
                raw_line=s,
            )
        else:
            continue
        _fix_station_name_property(row)
        hydrate_parsed_fields(row)
        rows.append(row)
    return rows


def parse_osaka_r_rows(lines: Iterable[str]) -> list[PropertyRow]:
    rows: list[PropertyRow] = []
    for s in lines:
        parts = [p.strip() for p in s.split("|")]
        if len(parts) != 9:
            continue
        row = PropertyRow(
            source="大阪R不動産",
            name=parts[0],
            price_text=parts[1],
            location=parts[2],
            area_text=parts[3],
            built_text=parts[4],
            station_text=parts[5],
            layout=parts[6],
            minpaku_status=parts[7],
            url=parts[8],
            raw_line=s,
        )
        hydrate_parsed_fields(row)
        rows.append(row)
    return rows


def _clean_one_station(text: str) -> str:
    """Clean a single station entry."""
    if not text:
        return text
    # Strip description prefix before station info (split on 。)
    if "。" in text:
        text = text.split("。")[-1].strip()
    # "最寄駅徒歩X分" is generic, not an actual station name
    if "最寄駅" in text and not re.search(r"[^\s最寄駅]{2,}駅", text):
        return ""
    # No station-like content — clear junk
    if not re.search(r"駅|徒歩", text):
        return ""
    # Extract station name from 「」brackets
    m = re.search(r"「(.+?)」", text)
    if m:
        station = m.group(1)
        station = re.sub(r"駅$", "", station)
        walk = re.search(r"(徒歩\s*\d+\s*分)", text)
        bus = re.search(r"(バス\s*\d+\s*分)", text)
        suffix = walk.group(1) if walk else (bus.group(1) if bus else "")
        return f"{station} {suffix}".strip()
    # No brackets — try to strip route prefix (e.g. "西鉄天神大牟田線高宮駅 徒歩12分")
    m2 = re.search(r"線(.+?)駅\s*(徒歩\s*\d+\s*分|バス\s*\d+\s*分)?", text)
    if m2:
        station = m2.group(1)
        suffix = m2.group(2) or ""
        return f"{station} {suffix}".strip()
    # Fallback: just remove 駅
    return re.sub(r"駅(\s)", r"\1", text)


def _clean_station_text(text: str) -> str:
    """Clean station text: remove route names and description junk, keep station name + walk time.

    Supports multiple stations separated by " / ".

    Examples:
      "地下鉄堺筋線「天神橋筋六丁目」徒歩10分" → "天神橋筋六丁目 徒歩10分"
      "西鉄平尾駅 徒歩13分 / 渡辺通駅 徒歩9分" → "西鉄平尾 徒歩13分 / 渡辺通 徒歩9分"
    """
    if not text:
        return text
    # Handle multiple stations separated by " / "
    if " / " in text:
        parts = [_clean_one_station(p.strip()) for p in text.split(" / ")]
        parts = [p for p in parts if p]
        # Sort by walk minutes (shortest first) for display
        def _walk_sort(s: str) -> int:
            m = re.search(r"徒歩\s*(\d+)\s*分", s)
            return int(m.group(1)) if m else 999
        parts.sort(key=_walk_sort)
        return " / ".join(parts) if parts else ""
    return _clean_one_station(text)


def hydrate_parsed_fields(row: PropertyRow) -> None:
    row.price_man = parse_price_man(row.price_text)
    row.area_sqm = parse_area_sqm(row.area_text)
    # Normalize area_text: "55.04m2（16.64坪）（壁芯）" → "55.04㎡"
    if row.area_sqm:
        row.area_text = f"{row.area_sqm}㎡"
    row.built_year, row.built_month = parse_built(row.built_text)
    if row.built_year is None and re.search(r"\d{4}年", row.built_text):
        row.built_text = "築年不明（要確認）"
    row.walk_min = parse_walk_minutes(row.station_text)
    # Clean station text: "地下鉄堺筋線「天神橋筋六丁目」徒歩10分" → "天神橋筋六丁目 徒歩10分"
    row.station_text = _clean_station_text(row.station_text)
    row.maintenance_fee = parse_maintenance_fee(row.maintenance_fee_text)
    # Normalize layout: "ワンルーム" → "1R"
    if row.layout and "ワンルーム" in row.layout:
        row.layout = row.layout.replace("ワンルーム", "1R")


def _normalize_name(name: str) -> str:
    """Normalize property name for dedup (handles katakana variants like シティ/シテイ)."""
    s = re.sub(r"[\s　]+", "", name)
    s = s.replace("テイ", "ティ").replace("ヴィ", "ビ")
    s = re.sub(r"[Ⅰ-Ⅻ]", lambda m: str("ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ".index(m.group()) + 1), s)
    return s


def _row_data_richness(row: PropertyRow) -> int:
    """Score how much useful data a row has (higher = richer)."""
    score = 0
    if row.maintenance_fee_text:
        score += 3
    if "管理費" in row.maintenance_fee_text and "修繕" in row.maintenance_fee_text:
        score += 2  # Prefer rows with breakdown detail
    if row.pet_status:
        score += 1
    if row.brokerage_text:
        score += 1
    return score


def _normalize_location(location: str) -> str:
    """Normalize location string for dedup (strip whitespace, common punctuation variants)."""
    s = re.sub(r"[\s　]+", "", location)
    # Normalize full-width numbers to half-width
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return s


def dedupe_properties(rows: list[PropertyRow]) -> tuple[list[PropertyRow], int]:
    seen: dict[tuple, int] = {}  # key -> index in out
    out: list[PropertyRow] = []
    dup_count = 0
    for row in rows:
        norm = _normalize_name(row.name)
        loc_norm = _normalize_location(row.location)
        key_physical = (norm, row.area_sqm)
        key_name_price = (row.name, row.price_man)
        # Third key: same address + same price = same property even if names differ (cross-listings)
        key_loc_price = (loc_norm, row.price_man) if loc_norm and row.price_man > 0 else None
        # Fourth key: same price + same area = likely same property (catches cross-source dupes with different names/addresses)
        key_price_area = (row.price_man, row.area_sqm) if row.price_man > 0 and row.area_sqm and row.area_sqm > 0 else None
        # Use sentinel-based lookup to avoid 0-index truthiness bug
        idx_phys = seen.get(key_physical)
        idx_name = seen.get(key_name_price)
        idx_loc = seen.get(key_loc_price) if key_loc_price is not None else None
        idx_pa = seen.get(key_price_area) if key_price_area is not None else None
        existing_idx = idx_phys if idx_phys is not None else (idx_name if idx_name is not None else (idx_loc if idx_loc is not None else idx_pa))
        if existing_idx is not None:
            # Prefer the row with richer data (maintenance fee, pet status, etc.)
            existing = out[existing_idx]
            if _row_data_richness(row) > _row_data_richness(existing):
                out[existing_idx] = row
            dup_count += 1
            continue
        idx = len(out)
        seen[key_physical] = idx
        seen[key_name_price] = idx
        if key_loc_price is not None:
            seen[key_loc_price] = idx
        if key_price_area is not None:
            seen[key_price_area] = idx
        out.append(row)
    return out, dup_count


def budget_score(price_man: int) -> int:
    if price_man <= 3500:
        return 20
    if price_man <= 4000:
        return 15
    if price_man <= 5000:
        return 10
    return 0


def area_score(area_sqm: float | None) -> int:
    """Area scoring for investment properties. Sweet spot = 40-60㎡ (1LDK-2LDK).

    Smaller units (25-40㎡) are viable for short-term rental.
    Larger units (70㎡+) have lower yield but appeal to families.
    """
    if area_sqm is None:
        return 0
    if 40 <= area_sqm < 60:
        return 15
    if 25 <= area_sqm < 40:
        return 10  # Studio/1K — short-term rental viable
    if 60 <= area_sqm < 70:
        return 10
    if area_sqm >= 70:
        return 5
    if area_sqm < 25:
        return -5  # Too small — limited use
    return 0


def earthquake_score(year: int | None, month: int | None) -> int:
    if year is None:
        return 0
    if year > 1981:
        return 15
    if year < 1981:
        return 0
    return 15 if (month or 1) >= 7 else 0


def station_score(walk_min: int | None) -> int:
    if walk_min is None:
        return 0
    if walk_min <= 5:
        return 15
    if walk_min <= 10:
        return 10
    if walk_min <= 15:
        return 3
    if walk_min <= 20:
        return -10
    return -15  # 20分超


def layout_score(layout: str) -> int:
    if re.search(r"[23]LDK", layout):
        return 10
    if "1LDK" in layout:
        return 5
    return 0


def classify_location_osaka(text: str) -> tuple[str, int]:
    checks = [
        ("北堀江/南堀江", 15, ["北堀江", "南堀江"]),
        ("中津/中崎町", 12, ["中津", "中崎町"]),
        ("南森町/天神橋/天満/扇町/東天満", 12, ["南森町", "天神橋", "天満", "扇町", "東天満"]),
        ("長堀橋/心斎橋", 12, ["長堀橋", "心斎橋"]),
        ("梅田/大淀/福島", 10, ["梅田", "大淀", "福島"]),
        ("肥後橋/淀屋橋/北浜/江戸堀", 10, ["肥後橋", "淀屋橋", "北浜", "江戸堀"]),
        ("阿波座/靱公園/靱本町", 10, ["阿波座", "靱公園", "靱本町"]),
        ("谷町", 8, ["谷町"]),
    ]
    for label, score, kws in checks:
        if any(kw in text for kw in kws):
            return label, score
    return "Other", 0


def classify_location_fukuoka(text: str) -> tuple[str, int]:
    # Strip railway line names to avoid false matches (e.g. "天神大牟田線" → "天神")
    cleaned = re.sub(
        r"(西鉄天神大牟田線|地下鉄空港線|地下鉄箱崎線|地下鉄七隈線|ＪＲ鹿児島本線|ＪＲ篠栗線|JR鹿児島本線|JR篠栗線)",
        "", text,
    )
    checks = [
        ("博多駅/祇園", 20, ["博多駅", "祇園町", "祇園"]),
        ("天神/中洲/春吉", 20, ["天神", "中洲", "春吉"]),
        ("薬院", 18, ["薬院"]),
        ("赤坂/大濠/大手門", 15, ["赤坂", "大濠", "大手門"]),
        ("渡辺通/住吉/上川端", 15, ["渡辺通", "住吉", "上川端"]),
        ("呉服町/古門戸", 12, ["呉服町", "古門戸"]),
        ("平尾/舞鶴", 10, ["平尾", "舞鶴"]),
        ("六本松", 10, ["六本松"]),
        ("西新/唐人町/藤崎", 5, ["西新", "唐人町", "藤崎"]),
        ("大橋/高宮", 5, ["大橋", "高宮"]),
        ("箱崎", 5, ["箱崎"]),
        ("姪浜", 5, ["姪浜"]),
    ]
    for label, score, kws in checks:
        if any(kw in cleaned for kw in kws):
            return label, score
    return "Other", 0  # Unknown area — neutral (was -5, asymmetric with Osaka +5)


def pet_score_for_row(row: PropertyRow) -> int:
    """Pet scoring: 可=15, 相談可=10, 不可=-5, unknown=-5(ほぼ不可+要確認フラグ).

    Unknown pet status = probably 不可 (most properties without explicit pet info
    don't allow pets). Score same as 不可, but flag for confirmation at inquiry.
    """
    text = f"{row.pet_status} {row.name} {row.minpaku_status}"
    # Check 不可 BEFORE 可 to avoid false positives
    if "ペット不可" in text or row.pet_status == "不可":
        return -5
    if "ペット可" in text or row.pet_status == "可":
        return 15
    if "ペット相談" in text or row.pet_status == "相談可":
        return 10
    return -5  # Unknown = probably 不可 + flagged for inquiry confirmation


def maintenance_fee_score(fee: int) -> int:
    """Maintenance fee scoring: lower is better. fee = total monthly yen (管理費+修繕積立金).

    Symmetric scale: max +10 (≤1万) / max -10 (>5万).
    Unknown (fee=0) gets -3 penalty to avoid unverified properties ranking high.
    """
    if fee == 0:
        return -3  # Unknown - mild penalty to incentivize data verification
    if fee <= 10000:
        return 10
    if fee <= 15000:
        return 7
    if fee <= 20000:
        return 5
    if fee <= 25000:
        return 3
    if fee <= 30000:
        return 0
    if fee <= 40000:
        return -5
    if fee <= 50000:
        return -8
    return -10  # 50,000円超


def brokerage_score(row: PropertyRow) -> int:
    """Brokerage fee scoring: 無料=5, 半額=3, 割引=2, normal=0"""
    text = row.brokerage_text
    if not text:
        return 0
    if "無料" in text or "0円" in text:
        return 5
    if "半額" in text or "50%" in text:
        return 3
    if "割引" in text or "値引" in text:
        return 2
    return 0


def kodate_bonus(row: PropertyRow) -> int:
    """戸建て加点: 区分所有と違い管理規約が無く、民泊運営の自由度が高い(Yuma要望2026-07-08)。"""
    return 20 if "戸建" in row.source else 0


def renovation_score(row: PropertyRow) -> int:
    """Renovation scoring: unrenovated=+5, renovated=-5, R不動産 renovated=0 (exception)"""
    text = f"{row.name} {row.raw_line}".lower()
    renovated_keywords = [
        "リノベーション済", "リノベ済", "リフォーム済", "フルリノベ",
        "フルリフォーム", "新装", "内装済", "室内リフォーム",
        "リノベーション済み", "リフォーム済み",
    ]
    is_restate = "R不動産" in row.source or "realosakaestate" in row.url or "realfukuokaestate" in row.url or "realtokyoestate" in row.url
    if any(kw.lower() in text for kw in renovated_keywords):
        if is_restate:
            return 0  # R不動産: renovated is OK (no penalty)
        return -5  # Renovated - no DIY opportunity, price premium
    unrenovated_keywords = [
        "現況", "現状渡し", "そのまま", "古い",
    ]
    if any(kw in text for kw in unrenovated_keywords):
        return 5  # Clearly unrenovated - DIY opportunity
    return 0  # Unknown - neutral (no data = no bonus)


def minpaku_penalty(row: PropertyRow) -> int:
    # 民泊禁止はハードフィルタで除外済みなので、ここでは確認不能=0
    return 0


def grade_tier(total: int) -> tuple[str, str, str]:
    if total >= 80:
        return "強く推奨", "tier-strong", "var(--accent-green)"
    if total >= 65:
        return "推奨", "tier-good", "#facc15"
    if total >= 50:
        return "条件付き", "tier-conditional", "#fb923c"
    return "見送り", "tier-pass", "var(--accent-red)"


def build_comment(row: PropertyRow) -> str:
    strengths: list[str] = []
    cautions: list[str] = []
    b = row.score_breakdown
    if b.get("pet", 0) >= 15:
        strengths.append("ペット可確定")
    elif b.get("pet", 0) >= 10:
        strengths.append("ペット相談可")
    if b.get("budget", 0) >= 15:
        strengths.append("予算適合")
    if b.get("station", 0) >= 10:
        strengths.append("駅近")
    if b.get("location", 0) >= 12:
        strengths.append("観光導線が強い立地")
    if b.get("earthquake", 0) == 15:
        strengths.append("新耐震")
    if b.get("layout", 0) == 10:
        strengths.append("2-3LDKで運用幅あり")
    if b.get("maintenance", 0) >= 7:
        strengths.append("管理費修繕積立金が安い")
    if b.get("renovation", 0) >= 5:
        strengths.append("リノベ余地あり")
    if b.get("brokerage", 0) >= 3:
        strengths.append(f"仲介手数料{row.brokerage_text}")
    if row.maintenance_fee == 0:
        cautions.append("管理費修繕データなし（要確認）")
    elif b.get("maintenance", 0) < 0:
        cautions.append("管理費修繕積立金が高い")
    if b.get("renovation", 0) < 0:
        cautions.append("リノベ済み（DIY余地なし・割高）")
    if b.get("pet", 0) <= 0:
        cautions.append("ペット条件要確認")
    # 民泊不可はハードフィルタで除外済みなのでコメント不要
    if row.walk_min is None:
        cautions.append("バス便で駅距離評価は低い")
    elif row.walk_min > 10:
        cautions.append("駅距離はやや弱い")
    if row.price_man > 5000:
        cautions.append("予算超過")
    if not strengths:
        strengths.append("個別要件次第で再評価余地")
    msg = " / ".join(strengths[:4])
    if cautions:
        msg += "。注意: " + "、".join(cautions[:3])
    return msg


def classify_location_tokyo(text: str) -> tuple[str, int]:
    checks = [
        ("渋谷/恵比寿/代官山", 20, ["渋谷", "恵比寿", "代官山"]),
        ("新宿/神宮前", 20, ["新宿", "神宮前"]),
        ("中目黒/代々木", 18, ["中目黒", "代々木"]),
        ("浅草/蔵前/押上", 18, ["浅草", "蔵前", "押上"]),
        ("上野/御徒町", 15, ["上野", "御徒町"]),
        ("池袋/大塚", 15, ["池袋", "大塚"]),
        ("麻布/六本木/白金", 15, ["麻布", "六本木", "白金"]),
        ("三田/品川/五反田", 12, ["三田", "品川", "五反田"]),
        ("中野/高円寺", 10, ["中野", "高円寺"]),
        ("巣鴨/駒込/文京", 10, ["巣鴨", "駒込", "文京"]),
        ("目黒/学芸大学", 10, ["目黒", "学芸大学"]),
    ]
    for label, score, kws in checks:
        if any(kw in text for kw in kws):
            return label, score
    return "Other", 0  # Unknown area — neutral (was -5)


def score_row(row: PropertyRow, config: ReportConfig) -> None:
    # Clean location text: remove address patterns like "博多駅南6丁目" that false-match station names
    _clean_loc = re.sub(r"駅[南北東西前][^\s]*", "", row.location)
    text_for_loc = f"{_clean_loc} {row.station_text} {row.name}"
    if config.city_key == "osaka":
        bucket, loc_score = classify_location_osaka(text_for_loc)
    elif config.city_key == "tokyo":
        bucket, loc_score = classify_location_tokyo(text_for_loc)
    else:
        bucket, loc_score = classify_location_fukuoka(text_for_loc)
    row.bucket_label = bucket
    row.pet_score = pet_score_for_row(row)
    breakdown = {
        "budget": budget_score(row.price_man),
        "area": area_score(row.area_sqm),
        "earthquake": earthquake_score(row.built_year, row.built_month),
        "station": station_score(row.walk_min),
        "location": loc_score,
        "layout": layout_score(row.layout),
        "pet": row.pet_score,
        "maintenance": maintenance_fee_score(row.maintenance_fee),
        "renovation": renovation_score(row),
        "brokerage": brokerage_score(row),
        "kodate": kodate_bonus(row),
        "minpaku_penalty": minpaku_penalty(row),
    }
    row.score_breakdown = breakdown
    row.total_score = sum(v for k, v in breakdown.items() if k != "minpaku_penalty") + breakdown["minpaku_penalty"]
    row.tier_label, row.tier_class, row.tier_color = grade_tier(row.total_score)
    row.detail_comment = build_comment(row)


def format_area(area: float | None) -> str:
    return "-" if area is None else f"{area:.2f}㎡"


def format_price_man(price_man: int) -> str:
    return f"{price_man:,}万円"


def safe_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)


_RENT_PER_SQM_BY_WARD: dict[str, dict[str, int]] = {
    "fukuoka": {
        "中央区": 3200,
        "博多区": 3000,
        "東区": 2600,
        "南区": 2400,
        "早良区": 2300,
        "西区": 2200,
        "城南区": 2000,
    },
    "osaka": {
        "中央区": 3400,
        "西区": 3300,
        "北区": 3200,
        "浪速区": 3100,
        "福島区": 3000,
        "天王寺区": 2900,
        "淀川区": 2800,
        "都島区": 2800,
        "東淀川区": 2300,
    },
    "tokyo": {
        "中央区": 3900,
        "新宿区": 4000,
        "渋谷区": 4000,
        "港区": 3500,
        "豊島区": 3800,
        "品川区": 3600,
        "目黒区": 3100,
        "文京区": 3200,
        "台東区": 3100,
        "中野区": 3600,
        "墨田区": 3700,
        "板橋区": 3400,
        "練馬区": 3100,
        "北区": 3200,
        "足立区": 3400,
        "葛飾区": 3400,
    },
}

_RENT_PER_SQM_BY_STATION: dict[str, dict[str, int]] = {
    "fukuoka": {
        "博多": 3000, "祇園": 2900, "呉服町": 2800, "東比恵": 2400,
        "中洲川端": 2800, "千代県庁口": 2400, "吉塚": 2200,
        "天神": 3200, "赤坂": 3000, "薬院": 2800, "大濠公園": 2800,
        "唐人町": 2600, "六本松": 2600, "渡辺通": 2800, "西鉄福岡": 3200,
        "桜坂": 2500, "西鉄平尾": 2400, "舞鶴": 2800, "大手門": 2800,
        "大橋": 2000, "高宮": 1500, "井尻": 1700, "笹原": 1600,
        "雑餉隈": 1200, "春日": 1800, "姪浜": 1800, "室見": 2000,
        "西新": 2200, "藤崎": 2100, "箱崎": 2000, "箱崎宮前": 2000,
        "箱崎九大前": 1900, "千早": 2100, "香椎": 1900,
    },
    "osaka": {
        "梅田": 3400, "福島": 3200, "中津": 3100, "天満": 2900,
        "南森町": 3000, "北浜": 3100, "淀屋橋": 3200, "肥後橋": 3100,
        "本町": 3000, "心斎橋": 3300, "長堀橋": 3100, "なんば": 3200,
        "堺筋本町": 2900, "谷町四丁目": 2800, "天王寺": 2800,
        "阿波座": 2800, "西長堀": 2700, "九条": 2500,
        "新大阪": 2600, "東三国": 2300, "京橋": 2600,
    },
    "tokyo": {
        "渋谷": 4200, "恵比寿": 4000, "代官山": 4000, "中目黒": 3800,
        "新宿": 4000, "新宿三丁目": 3800, "池袋": 3600, "大塚": 3200,
        "上野": 3200, "御徒町": 3200, "浅草": 3000, "蔵前": 3000,
        "押上": 2800, "錦糸町": 3000, "両国": 2900,
        "品川": 3600, "五反田": 3400, "大崎": 3300, "目黒": 3600,
        "三田": 3400, "麻布十番": 4000, "六本木": 4200, "白金": 3800,
        "中野": 3400, "高円寺": 3000, "荻窪": 2800, "東中野": 3200,
        "野方": 2600, "沼袋": 2500, "赤羽": 2800, "王子": 2700,
        "田端": 2800, "練馬": 2800, "東武練馬": 2400,
    },
}

_ESTIMATED_RENT_PER_SQM: dict[str, int] = {
    "osaka": 2800,
    "fukuoka": 2400,
    "tokyo": 3200,
}


def _age_discount(built_year: int | None) -> float:
    if not built_year:
        return 0.80
    age = 2026 - built_year
    if age <= 10:
        return 1.00
    if age <= 20:
        return 0.92
    if age <= 30:
        return 0.82
    if age <= 40:
        return 0.72
    return 0.65


def _get_rent_per_sqm(city_key: str, location: str, built_year: int | None = None, station_text: str = "") -> tuple[int, str]:
    walk_match = re.search(r"徒歩\s*(\d+)\s*分", station_text)
    walk_min = int(walk_match.group(1)) if walk_match else 5
    station_data = _RENT_PER_SQM_BY_STATION.get(city_key, {})
    if station_text and station_data and walk_min < 10:
        cleaned = re.sub(
            r"(西鉄天神大牟田線|地下鉄空港線|地下鉄箱崎線|地下鉄七隈線|ＪＲ鹿児島本線|ＪＲ篠栗線|JR鹿児島本線|JR篠栗線|ＪＲ中央線|JR中央線|東京メトロ[^\s]*線|都営[^\s]*線|西武[^\s]*線|東武[^\s]*線)",
            "",
            station_text,
        )
        for stn in sorted(station_data.keys(), key=len, reverse=True):
            if stn in cleaned:
                return int(station_data[stn] * _age_discount(built_year)), stn
    if station_data and location:
        for stn in sorted(station_data.keys(), key=len, reverse=True):
            if stn in location:
                return int(station_data[stn] * _age_discount(built_year)), stn
    ward_match = re.search(r"([^\s市県都府]+区)", location)
    ward = ward_match.group(1) if ward_match else ""
    ward_data = _RENT_PER_SQM_BY_WARD.get(city_key, {})
    if ward and ward in ward_data:
        return int(ward_data[ward] * _age_discount(built_year)), ward
    return int(_ESTIMATED_RENT_PER_SQM.get(city_key, 2800) * _age_discount(built_year)), ""


def enrich_revenue(row: PropertyRow, config: ReportConfig) -> None:
    """Attach market-rent-based revenue analysis for card rendering."""
    if not row.price_man or row.price_man <= 0 or not row.area_sqm or row.area_sqm <= 0:
        row.revenue = None
        return
    rent_per_sqm, label = _get_rent_per_sqm(config.city_key, row.location, row.built_year, row.station_text)
    monthly_rent_yen = rent_per_sqm * row.area_sqm
    annual_rent_man = monthly_rent_yen * 12 / 10000
    yield_pct = annual_rent_man / row.price_man * 100
    row.rent_per_sqm = rent_per_sqm
    row.rent_source = f"相場{label}" if label else "相場"
    row.est_monthly_rent = f"{monthly_rent_yen / 10000:.1f}万"
    row.yield_text = f"≈{yield_pct:.1f}%"
    row.price_per_sqm = f"{row.price_man / row.area_sqm:.1f}万/㎡"
    try:
        ra = revenue_analyze(
            price_man=row.price_man,
            yield_pct=yield_pct,
            structure=row.structure or "RC造",
            built_year=row.built_year,
            units_count=1,
            area_sqm=row.area_sqm,
            maintenance_fee_monthly=row.maintenance_fee or 0,
        )
        scenario_cf = {}
        for scenario_years in (15, 20):
            ra_s = revenue_analyze(
                price_man=row.price_man,
                yield_pct=yield_pct,
                structure=row.structure or "RC造",
                built_year=row.built_year,
                units_count=1,
                area_sqm=row.area_sqm,
                maintenance_fee_monthly=row.maintenance_fee or 0,
                params=InvestmentParams(loan_years=scenario_years),
            )
            scenario_cf[f"cf_{scenario_years}y"] = round(ra_s.after_tax_cf / 12, 1)
    except Exception:
        row.revenue = None
        return
    row.revenue = {
        "noi": round(ra.noi, 1),
        "net_yield": round(ra.net_yield_pct, 2),
        "monthly_cf": round(ra.monthly_cf, 1),
        "after_tax_monthly_cf": round(ra.after_tax_cf / 12, 1),
        "ccr": round(ra.ccr_pct, 1),
        "payback_years": round(ra.payback_years, 1) if ra.payback_years != float("inf") else None,
        "depreciation_annual": round(ra.depreciation_annual, 1),
        "tax_benefit": round(ra.tax_benefit, 1),
        "verdict": ra.verdict,
        "down_payment": round(ra.down_payment, 1),
        "acquisition_cost": round(ra.acquisition_cost, 1),
        "total_equity": round(ra.total_equity, 1),
        "loan_amount": round(ra.loan_amount, 1),
        "loan_years": ra.loan_years,
        "loan_rate": ra.params.loan_rate_annual * 100,
        "annual_debt_service": round(ra.annual_debt_service, 1),
        "taxable_income": round(ra.taxable_income, 1),
        "after_tax_cf": round(ra.after_tax_cf, 1),
        "est_monthly_rent": row.est_monthly_rent,
        "rent_source": row.rent_source,
        "rent_per_sqm": rent_per_sqm,
        "structure_used": row.structure or "RC造",
        **scenario_cf,
    }


def _format_maintenance_disp(r: PropertyRow) -> str:
    """Format maintenance fee display with breakdown (管理費 + 修繕).

    Always shows something explicit:
    - Full breakdown: "13,400円 管理8,000 + 修繕5,400"
    - Total only: "18,500円/月 (内訳なし)"
    - No data: "データなし" with score penalty indicator
    """
    if r.maintenance_fee <= 0:
        return '<span class="maint-na">データなし</span>'
    text = r.maintenance_fee_text.replace(",", "")
    kanri_m = re.search(r"管理費(\d+)", text)
    shuuzen_m = re.search(r"修繕(\d+)", text)
    if kanri_m and shuuzen_m:
        k = int(kanri_m.group(1))
        s = int(shuuzen_m.group(1))
        return f'<span title="管理費{k:,}円 + 修繕{s:,}円">{k + s:,}円</span><span class="maint-detail">管理{k:,} + 修繕{s:,}</span>'
    if kanri_m:
        k = int(kanri_m.group(1))
        return f'<span title="管理費{k:,}円（修繕不明）">{k:,}円</span><span class="maint-detail">管理のみ</span>'
    if shuuzen_m:
        s = int(shuuzen_m.group(1))
        return f'<span title="修繕{s:,}円（管理費不明）">{s:,}円</span><span class="maint-detail">修繕のみ</span>'
    # Bare number (common in Osaka SUUMO data) - show as total
    return f'<span title="管理費+修繕 合計">{r.maintenance_fee:,}円/月</span><span class="maint-detail">内訳なし</span>'


def _score_cell(val: int, label: str = "") -> str:
    short = label[:2] if label else ""
    if val > 0:
        return f'<span class="sc-pill sc-pos">{short}+{val}</span>'
    if val < 0:
        return f'<span class="sc-pill sc-neg">{short}{val}</span>'
    return f'<span class="sc-pill sc-zero">{short}0</span>'


def load_first_seen() -> dict[str, str]:
    """Load first_seen.json registry. Returns {url: 'YYYY-MM-DD'}."""
    first_seen_file = Path(__file__).parent / "data" / "first_seen.json"
    if not first_seen_file.exists():
        return {}
    try:
        return json.loads(first_seen_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _format_first_seen(url: str, first_seen: dict[str, str]) -> str:
    """Format first-seen date for display. 'NEW' if within 3 days, else 'M/D'."""
    date_str = first_seen.get(url, "")
    if not date_str:
        return ""
    try:
        d = dt.date.fromisoformat(date_str)
        days_ago = (dt.date.today() - d).days
        if days_ago <= 3:
            return "NEW"
        return f"{d.month}/{d.day}"
    except ValueError:
        return date_str


def _build_table_row_data(r: PropertyRow, idx: int, first_seen: dict[str, str] | None = None) -> dict:
    """Build a dict for a single table row for the Jinja2 template."""
    b = r.score_breakdown
    breakdown_title = f"予算{b['budget']:+d} 面積{b['area']:+d} 耐震{b['earthquake']:+d} 駅距{b['station']:+d} 立地{b['location']:+d} 間取{b['layout']:+d} ペト{b['pet']:+d} 管理{b['maintenance']:+d} リノ{b['renovation']:+d} 仲介{b['brokerage']:+d} 民泊{b['minpaku_penalty']:+d}"
    breakdown_html = " ".join([
        _score_cell(b["budget"], "予算"), _score_cell(b["area"], "面積"),
        _score_cell(b["earthquake"], "耐震"), _score_cell(b["station"], "駅距"),
        _score_cell(b["location"], "立地"), _score_cell(b["layout"], "間取"),
        _score_cell(b["pet"], "ペト"), _score_cell(b["maintenance"], "管理"),
        _score_cell(b["renovation"], "リノ"), _score_cell(b["brokerage"], "仲介"),
        _score_cell(b["minpaku_penalty"], "民泊"),
    ])
    # Pet badge for template
    pet_badge = ""
    pet_badge_class = ""
    if r.pet_score >= 15:
        pet_badge = "ペット可"
        pet_badge_class = "pet-ok"
    elif r.pet_score >= 10:
        pet_badge = "ペット相談可"
        pet_badge_class = "pet-maybe"

    # First-seen display
    first_seen_display = _format_first_seen(r.url, first_seen or {})
    is_new = first_seen_display == "NEW"

    return {
        "idx": idx,
        "name": r.name,
        "url": r.url,
        "source": r.source,
        "pet_badge": pet_badge,
        "pet_badge_class": pet_badge_class,
        "price_man": r.price_man,
        "price_formatted": format_price_man(r.price_man),
        "area_display": f"{(r.area_sqm or 0):.2f}",
        "area_formatted": format_area(r.area_sqm),
        "location": r.location,
        "station_text": r.station_text,
        "built_year": r.built_year or 0,
        "built_display": f"{r.built_year}年" if r.built_year else r.built_text,
        "layout": r.layout,
        "walk_min": r.walk_min if r.walk_min is not None else 999,
        "maint_display": _format_maintenance_disp(r),
        "breakdown_html": breakdown_html,
        "breakdown_title": breakdown_title,
        "total_score": r.total_score,
        "tier_label": r.tier_label,
        "tier_class": r.tier_class,
        "tier_color": r.tier_color,
        "first_seen": first_seen_display,
        "is_new": is_new,
    }


def _build_focus_card_data(r: PropertyRow, rank: int) -> dict:
    """Build a dict for a focus card for the Jinja2 template."""
    b = r.score_breakdown
    chips = [
        {"label": "予算", "value": b["budget"]},
        {"label": "面積", "value": b["area"]},
        {"label": "耐震", "value": b["earthquake"]},
        {"label": "駅", "value": b["station"]},
        {"label": "立地", "value": b["location"]},
        {"label": "間取り", "value": b["layout"]},
        {"label": "ペット", "value": b["pet"]},
        {"label": "管理費修繕", "value": b["maintenance"]},
        {"label": "リノベ", "value": b["renovation"]},
        {"label": "仲介", "value": b["brokerage"]},
        {"label": "民泊規約", "value": b["minpaku_penalty"]},
    ]
    return {
        "rank": rank,
        "name": r.name,
        "url": r.url,
        "price_formatted": format_price_man(r.price_man),
        "area_formatted": format_area(r.area_sqm),
        "location": r.location,
        "total_score": r.total_score,
        "tier_label": r.tier_label,
        "tier_color": r.tier_color,
        "chips": chips,
        "detail_comment": r.detail_comment,
        "station_text": r.station_text,
        "built_text": r.built_text,
        "layout": r.layout,
        "minpaku_status": r.minpaku_status,
    }


# Navigation pages for property report
_NAV_PAGES = [
    {"href": "index.html", "label": "Hub"},
    {"href": "minpaku-osaka.html", "label": "民泊・大阪"},
    {"href": "minpaku-fukuoka.html", "label": "民泊・福岡"},
    {"href": "minpaku-tokyo.html", "label": "民泊・東京"},
    {"href": "ittomono.html", "label": "一棟もの"},
    {"href": "market.html", "label": "賃貸Market"},
]


def load_patrol_summary() -> dict:
    """Load patrol_summary.json if it exists. Returns empty dict on failure."""
    summary_file = Path(__file__).parent / "data" / "patrol_summary.json"
    if not summary_file.exists():
        return {}
    try:
        return json.loads(summary_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_report_html(config: ReportConfig, rows: list[PropertyRow], meta: dict[str, str], raw_count: int, duplicate_count: int) -> str:
    """Build property search report HTML using the shared Jinja2 template."""
    rows_sorted = sorted(rows, key=lambda r: (-r.total_score, r.price_man, (r.walk_min or 999), r.name))
    kodate_count = sum(1 for r in rows_sorted if "戸建" in r.source)
    type_counts = {"kodate": kodate_count, "kubun": len(rows_sorted) - kodate_count}

    avg_price = round(sum(r.price_man for r in rows_sorted) / len(rows_sorted), 1) if rows_sorted else 0
    avg_area = round(sum((r.area_sqm or 0) for r in rows_sorted) / len(rows_sorted), 2) if rows_sorted else 0
    top_prop = rows_sorted[0] if rows_sorted else None
    search_date = meta.get("search_date") or dt.date.today().isoformat()
    revenue_rows = [r for r in rows_sorted if r.revenue]
    avg_net_yield = round(sum(r.revenue["net_yield"] for r in revenue_rows) / len(revenue_rows), 2) if revenue_rows else 0
    avg_ccr = round(sum(r.revenue["ccr"] for r in revenue_rows) / len(revenue_rows), 1) if revenue_rows else 0
    profitable_count = sum(1 for r in revenue_rows if r.revenue["after_tax_monthly_cf"] > 0)
    hero_stats = {
        "count": len(rows_sorted),
        "avg_price": int(round(avg_price)) if avg_price else 0,
        "avg_net_yield": avg_net_yield,
        "avg_ccr": avg_ccr,
        "top_count": sum(1 for r in rows_sorted if r.total_score >= 80),
        "pet_ok_count": sum(1 for r in rows_sorted if r.pet_score >= 10),
        "profitable_count": profitable_count,
    }

    sources_str = meta.get("sources_loaded", "SUUMO")
    city_badge = f"データソース: {sources_str}"

    # Build config dict for template (only serializable fields)
    config_dict = {
        "city_key": config.city_key,
        "city_label": config.city_label,
        "accent": config.accent,
        "accent_rgb": config.accent_rgb,
        "hero_conditions": config.hero_conditions,
        "data_path": str(config.data_path),
        "extra_data_paths": [str(p) for p in config.extra_data_paths],
    }

    # Load patrol summary for freshness banner
    patrol_summary = load_patrol_summary()

    # Render with lib.renderer
    env = create_env(extra_dirs=[_THIS_DIR / "lib" / "templates"])
    template = env.get_template("pages/property_report.html")
    return template.render(
        config=config_dict,
        rows_sorted=rows_sorted,
        type_counts=type_counts,
        meta=meta,
        raw_count=raw_count,
        duplicate_count=duplicate_count,
        avg_price=avg_price,
        avg_area=avg_area,
        hero_stats=hero_stats,
        top_prop=top_prop,
        search_date=search_date,
        city_badge=city_badge,
        search_condition_bullets=config.search_condition_bullets,
        investor_notes=config.investor_notes,
        deepdive_links=config.deepdive_links,
        sources_str=sources_str,
        nav_pages=_NAV_PAGES,
        current_page=f"minpaku-{config.city_key}.html",
        patrol_summary=patrol_summary,
    )


def load_property_registry() -> dict:
    """Load property registry with overrides and exclusions.

    Returns dict keyed by normalized URL (trailing slash) with:
      - status: ACTIVE/SOLD/EXCLUDED/ERROR_TIMEOUT
      - overrides: dict of field overrides (price, name, exclude, etc.)
      - exclude_reason: why excluded
      - linked_inquiry: inquiry ID if in pipeline
    """
    status_file = Path(__file__).parent / "data" / "property_status.json"
    if not status_file.exists():
        return {}
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        return {
            url.rstrip("/") + "/": info
            for url, info in data.get("properties", {}).items()
        }
    except Exception:
        return {}


def load_sold_urls() -> set[str]:
    """Load sold/excluded property URLs from status file (backward-compatible wrapper)."""
    registry = load_property_registry()
    return {
        url
        for url, data in registry.items()
        if data.get("status") in ("SOLD", "EXCLUDED", "ERROR_TIMEOUT")
    }


def generate_report(config: ReportConfig) -> Path:
    meta = extract_search_meta(config.data_path)
    base_rows = parse_data_file(config.data_path)
    raw_count = len(base_rows)
    # Detect primary source from data file
    first_source = base_rows[0].source if base_rows else "SUUMO"
    sources_loaded = [first_source]
    for extra_path in config.extra_data_paths:
        if extra_path.exists():
            extra_rows = parse_data_file(extra_path)
            base_rows.extend(extra_rows)
            raw_count += len(extra_rows)
            source_name = extra_path.stem.split("_")[0]
            if source_name not in sources_loaded:
                sources_loaded.append(source_name)
    if config.include_osaka_r:
        base_rows.extend(parse_osaka_r_rows(OSAKA_R_ROWS))
        raw_count += 4
        if "大阪R不動産" not in sources_loaded:
            sources_loaded.append("大阪R不動産")
    deduped, duplicate_count = dedupe_properties(base_rows)

    # Filter out sold properties
    sold_urls = load_sold_urls()
    before_filter = len(deduped)
    deduped = [r for r in deduped if r.url.rstrip("/") + "/" not in sold_urls]
    sold_count = before_filter - len(deduped)

    # Filter out owner-change / tenant-occupied / investment-only properties
    _OC_KEYWORDS = [
        "オーナーチェンジ", "賃貸中", "利回り", "投資顧問", "投資物件",
        "家賃", "月額賃料", "年間収入", "年間賃料",
        "表面利回", "想定利回", "収益", "入居者付", "入居中",
        "賃借人", "テナント付", "現行賃料", "満室",
    ]
    before_oc = len(deduped)

    def _is_oc(r: PropertyRow) -> bool:
        # Check ALL text fields for OC keywords (raw_line has the full original row)
        text = f"{r.name} {r.station_text} {r.minpaku_status} {r.location} {r.raw_line}"
        return any(kw in text for kw in _OC_KEYWORDS)

    deduped = [r for r in deduped if not _is_oc(r)]
    oc_count = before_oc - len(deduped)

    # Filter out ペット不可 properties
    before_pet = len(deduped)
    deduped = [r for r in deduped if not is_pet_ng(r)]
    pet_ng_count = before_pet - len(deduped)

    # Filter out 管理費修繕積立金 > 30,000円/月
    before_maint = len(deduped)
    deduped = [r for r in deduped if r.maintenance_fee == 0 or r.maintenance_fee <= 30000]
    maint_high_count = before_maint - len(deduped)
    if maint_high_count > 0:
        print(f"  Removed {maint_high_count} high-maintenance-fee (> 30,000円) properties")

    # Filter out 民泊禁止 properties
    before_minpaku = len(deduped)

    def _is_minpaku_ng(r: PropertyRow) -> bool:
        text = f"{r.minpaku_status} {r.name} {r.raw_line}"
        return "民泊禁止" in text or "民泊不可" in text or "住宅宿泊事業不可" in text

    deduped = [r for r in deduped if not _is_minpaku_ng(r)]
    minpaku_ng_count = before_minpaku - len(deduped)

    # Filter out サブリース properties
    before_sublease = len(deduped)
    deduped = [r for r in deduped if not is_sublease(r)]
    sublease_count = before_sublease - len(deduped)

    # 20㎡台フィルタ: 面積30㎡未満は投資対象外
    before_small = len(deduped)
    deduped = [r for r in deduped if r.area_sqm is None or r.area_sqm >= 30]
    small_area_count = before_small - len(deduped)

    for row in deduped:
        score_row(row, config)
        enrich_revenue(row, config)

    # 厳選フィルタ: ティアベース表示制御
    # 緑(80+) = 全数表示、黄(65-79) = 緑が少ない場合のみ補充、オレンジ/赤 = 非表示
    TIER_GREEN = 80   # 強く推奨: 常に表示
    TIER_YELLOW = 65  # 推奨: 緑が少ない場合に補充
    MAX_YELLOW_FILL = 20  # 緑+黄の合計上限
    before_quality = len(deduped)
    # オレンジ(50-64)・赤(<50)を除外
    deduped = [r for r in deduped if r.total_score >= TIER_YELLOW]
    quality_filtered = before_quality - len(deduped)
    deduped_sorted = sorted(deduped, key=lambda r: -r.total_score)

    green = [r for r in deduped_sorted if r.total_score >= TIER_GREEN]
    yellow = [r for r in deduped_sorted if TIER_YELLOW <= r.total_score < TIER_GREEN]

    if len(green) >= MAX_YELLOW_FILL:
        # 緑だけで十分 → 黄は表示しない
        deduped = green
        top_n_trimmed = len(yellow)
    else:
        # 緑を全数 + 黄で上限まで補充
        yellow_slots = MAX_YELLOW_FILL - len(green)
        deduped = green + yellow[:yellow_slots]
        top_n_trimmed = max(0, len(yellow) - yellow_slots)

    meta["sources_loaded"] = ", ".join(sources_loaded)
    meta["sold_removed"] = str(sold_count)
    meta["oc_removed"] = str(oc_count)
    meta["pet_ng_removed"] = str(pet_ng_count)
    meta["maint_high_removed"] = str(maint_high_count)
    meta["minpaku_ng_removed"] = str(minpaku_ng_count)
    meta["sublease_removed"] = str(sublease_count)
    meta["small_area_removed"] = str(small_area_count)
    meta["quality_filtered"] = str(quality_filtered)
    meta["top_n_trimmed"] = str(top_n_trimmed)
    html_text = build_report_html(config, deduped, meta, raw_count=raw_count, duplicate_count=duplicate_count)
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    config.output_path.write_text(html_text, encoding="utf-8")
    if sold_count > 0:
        print(f"  Removed {sold_count} sold properties")
    if oc_count > 0:
        print(f"  Removed {oc_count} owner-change/tenant-occupied properties")
    if pet_ng_count > 0:
        print(f"  Removed {pet_ng_count} pet-NG properties")
    if minpaku_ng_count > 0:
        print(f"  Removed {minpaku_ng_count} minpaku-NG properties")
    if sublease_count > 0:
        print(f"  Removed {sublease_count} sublease properties")
    if small_area_count > 0:
        print(f"  Removed {small_area_count} small-area (< 30㎡) properties")
    if quality_filtered > 0:
        print(f"  Removed {quality_filtered} low-score (< {TIER_YELLOW}) properties")
    if top_n_trimmed > 0:
        print(f"  Tier filter: {len(green)}件 green + {len(deduped) - len(green)}件 yellow (cut {top_n_trimmed} lower-ranked)")
    print(f"  Final: {len(deduped)}件 厳選済み")

    # 融資×収益の投資優先度ランキングを都市ごとに永続化（横断ダッシュボード用）
    from investment_priority import build_priority_records, save_city_priority
    priority_records = build_priority_records(deduped, config)
    save_city_priority(config.city_key, priority_records)

    # Auto QA
    _run_qa(config.output_path, deduped, config.city_label)

    return config.output_path


def _run_qa(output_path: Path, rows: list[PropertyRow], city_label: str) -> None:
    """レポート生成後の自動QAチェック"""
    warnings: list[str] = []
    errors: list[str] = []
    total = len(rows)

    # 1. 件数チェック
    if total == 0:
        errors.append("物件が0件です")

    # 2. 管理費データカバレッジ (30%未満はFAIL)
    maint_count = sum(1 for r in rows if r.maintenance_fee > 0)
    maint_breakdown_count = sum(1 for r in rows if r.maintenance_fee > 0 and ("管理費" in r.maintenance_fee_text or "修繕" in r.maintenance_fee_text))
    maint_pct = (maint_count / total * 100) if total > 0 else 0
    if maint_pct < 30:
        errors.append(f"管理費データ: {maint_count}/{total}件 ({maint_pct:.0f}%) — 30%未満。enrichment要確認")
    elif maint_pct < 50:
        warnings.append(f"管理費データ: {maint_count}/{total}件 ({maint_pct:.0f}%) — 半数未満 (内訳あり{maint_breakdown_count}件)")
    else:
        # Still report coverage for monitoring
        pass  # Will be included in the OK line below

    # 3. URL欠損
    no_url = sum(1 for r in rows if not r.url or r.url.strip() == "")
    if no_url > 0:
        errors.append(f"URL欠損: {no_url}件")

    # 4. スコア範囲
    score_min = min((r.total_score for r in rows), default=0)
    score_max = max((r.total_score for r in rows), default=0)
    if score_max > 150 or score_min < -50:
        warnings.append(f"スコア範囲が異常: {score_min}〜{score_max}")

    # 5. 出力ファイルサイズ
    if output_path.exists():
        size_kb = output_path.stat().st_size / 1024
        if size_kb < 5:
            errors.append(f"出力ファイルが小さすぎ: {size_kb:.1f}KB")

    # 6. 重複チェック（同じURLが残っていないか）
    urls = [r.url for r in rows if r.url]
    dup_urls = len(urls) - len(set(urls))
    if dup_urls > 0:
        warnings.append(f"URL重複: {dup_urls}件")

    # 結果出力
    prefix = f"  QA [{city_label}]"
    if errors:
        for e in errors:
            print(f"{prefix} ❌ {e}")
    if warnings:
        for w in warnings:
            print(f"{prefix} ⚠ {w}")
    if not errors and not warnings:
        print(f"{prefix} ✅ {total}件 OK (管理費{maint_pct:.0f}%, 内訳あり{maint_breakdown_count}件)")
    elif not errors:
        print(f"{prefix} ✅ {total}件 (警告{len(warnings)}件, 管理費{maint_pct:.0f}%)")
