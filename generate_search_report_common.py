from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
from collections import Counter
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


def site_header_css() -> str:
    return """
/* ── Shared Gnav ── */
.site-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 52px;
  background: rgba(22,24,31,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  position: sticky; top: 0; z-index: 100;
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
  .nav-toggle-label { display: block; }
  .site-nav {
    display: none; flex-direction: column; gap: 0;
    position: absolute; top: 52px; left: 0; right: 0; z-index: 200;
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
    return """<header class="site-header">
  <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-label="Toggle navigation">
  <label for="nav-toggle" class="nav-toggle-label"><span></span></label>
  <nav class="site-nav">
    <a href="https://ymatz28-beep.github.io/report-dashboard/">Hub</a>
    <a href="https://ymatz28-beep.github.io/property-report/" aria-current="page">Property</a>
    <a href="https://ymatz28-beep.github.io/trip-planner/">Travel</a>
  </nav>
</header>"""


def global_nav_css() -> str:
    return """
.gnav{position:sticky;top:52px;z-index:90;background:rgba(10,12,18,.92);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.08);padding:0;font-family:'Inter','Noto Sans JP',sans-serif}
.gnav-inner{max-width:1280px;margin:0 auto;display:flex;align-items:center;gap:0;padding:0 16px;overflow-x:auto;white-space:nowrap}
.gnav a{display:inline-block;padding:8px 14px;font-size:11px;font-weight:600;color:rgba(255,255,255,.5);text-decoration:none;letter-spacing:.04em;transition:color .2s}
.gnav a:hover{color:#fff}
.gnav a.cur{color:#fff;border-bottom:2px solid #3b9eff}
@media(max-width:640px){.gnav a{padding:8px 10px;font-size:10px}}
"""


def global_nav_html(current: str = "") -> str:
    pages = [
        ("index.html", "Hub"),
        ("minpaku-osaka.html", "大阪"),
        ("minpaku-fukuoka.html", "福岡"),
        ("minpaku-tokyo.html", "東京"),
        ("naiken-analysis.html", "内覧分析"),
        ("inquiry-messages.html", "問い合わせ"),
    ]
    links = []
    for href, label in pages:
        cls = ' class="cur"' if href == current else ""
        links.append(f'<a href="{href}"{cls}>{label}</a>')
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
        return int(y.group(1)), int(m.group(1)) if m else 1
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
    m = re.search(r"徒歩\s*(\d+)\s*分", station_text)
    if m:
        return int(m.group(1))
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
        else:
            continue
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


def hydrate_parsed_fields(row: PropertyRow) -> None:
    row.price_man = parse_price_man(row.price_text)
    row.area_sqm = parse_area_sqm(row.area_text)
    row.built_year, row.built_month = parse_built(row.built_text)
    row.walk_min = parse_walk_minutes(row.station_text)
    row.maintenance_fee = parse_maintenance_fee(row.maintenance_fee_text)


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


def dedupe_properties(rows: list[PropertyRow]) -> tuple[list[PropertyRow], int]:
    seen: dict[tuple, int] = {}  # key -> index in out
    out: list[PropertyRow] = []
    dup_count = 0
    for row in rows:
        norm = _normalize_name(row.name)
        key_physical = (norm, row.area_sqm)
        key_name_price = (row.name, row.price_man)
        # Use sentinel-based lookup to avoid 0-index truthiness bug
        idx_phys = seen.get(key_physical)
        idx_name = seen.get(key_name_price)
        existing_idx = idx_phys if idx_phys is not None else idx_name
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
    if area_sqm is None:
        return 0
    if 50 <= area_sqm < 60:
        return 15
    if 40 <= area_sqm < 50:
        return 10
    if 60 <= area_sqm < 70:
        return 10
    if area_sqm > 70:
        return 5
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
        return -5
    if walk_min <= 20:
        return -15
    return -25  # 20分超は民泊・居住ともに非現実的


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
    return "Other", 5


def classify_location_fukuoka(text: str) -> tuple[str, int]:
    # Strip railway line names to avoid false matches (e.g. "天神大牟田線" → "天神")
    cleaned = re.sub(
        r"(西鉄天神大牟田線|地下鉄空港線|地下鉄箱崎線|地下鉄七隈線|ＪＲ鹿児島本線|ＪＲ篠栗線|JR鹿児島本線|JR篠栗線)",
        "", text,
    )
    checks = [
        ("博多駅/祇園", 20, ["博多駅", "祇園町"]),
        ("天神/中洲/春吉", 20, ["天神", "中洲", "春吉"]),
        ("薬院", 18, ["薬院"]),
        ("赤坂/大濠/大手門", 15, ["赤坂", "大濠", "大手門"]),
        ("渡辺通/住吉/上川端", 15, ["渡辺通", "住吉", "上川端"]),
        ("呉服町/古門戸", 12, ["呉服町", "古門戸"]),
        ("平尾/舞鶴", 10, ["平尾", "舞鶴"]),
        ("西新/唐人町/藤崎", 5, ["西新", "唐人町", "藤崎"]),
        ("大橋/高宮", 0, ["大橋", "高宮"]),
    ]
    for label, score, kws in checks:
        if any(kw in cleaned for kw in kws):
            return label, score
    return "Other", -5


def pet_score_for_row(row: PropertyRow) -> int:
    """Pet scoring: 可=15, 相談可=10, unknown=-15, 不可=-5 (but hard-filtered).

    Most Japanese condos default to no-pets, so unknown pet status is treated
    as a strong negative to prevent unconfirmed properties from ranking high.
    """
    text = f"{row.pet_status} {row.name} {row.minpaku_status}"
    # Check 不可 BEFORE 可 to avoid false positives
    if "ペット不可" in text or row.pet_status == "不可":
        return -5
    if "ペット可" in text or row.pet_status == "可":
        return 15
    if "ペット相談" in text or row.pet_status == "相談可":
        return 10
    return -15


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
    return 3  # Unknown - likely unrenovated (most used condos)


def minpaku_penalty(row: PropertyRow) -> int:
    # 民泊禁止はハードフィルタで除外済みなので、ここでは確認不能=0
    return 0


def grade_tier(total: int) -> tuple[str, str, str]:
    if total >= 80:
        return "強く推奨", "tier-strong", "#22c55e"
    if total >= 65:
        return "推奨", "tier-good", "#facc15"
    if total >= 50:
        return "条件付き", "tier-conditional", "#fb923c"
    return "見送り", "tier-pass", "#ef4444"


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
    return "Other", -5


def score_row(row: PropertyRow, config: ReportConfig) -> None:
    text_for_loc = f"{row.location} {row.station_text} {row.name}"
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
    {"href": "minpaku-osaka.html", "label": "大阪"},
    {"href": "minpaku-fukuoka.html", "label": "福岡"},
    {"href": "minpaku-tokyo.html", "label": "東京"},
    {"href": "naiken-analysis.html", "label": "内覧分析"},
    {"href": "inquiry-messages.html", "label": "問い合わせ"},
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
    top5 = rows_sorted[:5]

    avg_price = round(sum(r.price_man for r in rows_sorted) / len(rows_sorted), 1) if rows_sorted else 0
    avg_area = round(sum((r.area_sqm or 0) for r in rows_sorted) / len(rows_sorted), 2) if rows_sorted else 0
    top_prop = rows_sorted[0] if rows_sorted else None
    search_date = meta.get("search_date") or dt.date.today().isoformat()

    bucket_counts = Counter(r.bucket_label for r in rows_sorted)
    price_bins = Counter()
    for r in rows_sorted:
        bin_start = (r.price_man // 500) * 500
        price_bins[bin_start] += 1
    price_bin_labels = [f"{b}-{b+499}万円" for b in sorted(price_bins)]
    price_bin_values = [price_bins[b] for b in sorted(price_bins)]

    radar_labels = ["予算", "面積", "耐震", "駅距離", "立地", "間取り", "ペット", "管理費修繕", "リノベ余地", "仲介手数料", "民泊規約"]
    radar_datasets = []
    for i, r in enumerate(top5):
        b = r.score_breakdown
        radar_datasets.append({
            "label": f"{i+1}. {r.name[:18]}",
            "data": [
                round(b["budget"] / 20 * 100),
                round(b["area"] / 15 * 100),
                round(b["earthquake"] / 15 * 100),
                round(b["station"] / 15 * 100),
                round(b["location"] / 15 * 100),
                round(b["layout"] / 10 * 100),
                max(0, round(b["pet"] / 15 * 100)),
                max(0, round(b["maintenance"] / 10 * 100)),
                round(b["renovation"] / 5 * 100),
                round(b["brokerage"] / 5 * 100),
                0 if b["minpaku_penalty"] < 0 else 100,
            ],
            "borderWidth": 2,
        })

    # Build structured data for template
    first_seen = load_first_seen()
    # Backfill: register any URLs not yet tracked with today's date
    today_iso = dt.date.today().isoformat()
    backfilled = 0
    for r in rows_sorted:
        if r.url and r.url not in first_seen:
            first_seen[r.url] = today_iso
            backfilled += 1
    if backfilled:
        first_seen_file = Path(__file__).parent / "data" / "first_seen.json"
        first_seen_file.write_text(json.dumps(first_seen, ensure_ascii=False, indent=2), encoding="utf-8")
    table_rows = [_build_table_row_data(r, idx, first_seen) for idx, r in enumerate(rows_sorted, start=1)]
    focus_cards = [_build_focus_card_data(r, i) for i, r in enumerate(top5, start=1)]
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
    env = create_env()
    template = env.get_template("pages/property_report.html")
    return template.render(
        config=config_dict,
        rows_sorted=rows_sorted,
        top5=top5,
        meta=meta,
        raw_count=raw_count,
        duplicate_count=duplicate_count,
        avg_price=avg_price,
        avg_area=avg_area,
        top_prop=top_prop,
        search_date=search_date,
        radar_labels=radar_labels,
        radar_datasets=radar_datasets,
        bucket_labels=list(bucket_counts.keys()),
        bucket_values=list(bucket_counts.values()),
        price_bin_labels=price_bin_labels,
        price_bin_values=price_bin_values,
        city_badge=city_badge,
        table_rows=table_rows,
        focus_cards=focus_cards,
        search_condition_bullets=config.search_condition_bullets,
        investor_notes=config.investor_notes,
        sources_str=sources_str,
        nav_pages=_NAV_PAGES,
        current_page=f"minpaku-{config.city_key}.html",
        patrol_summary=patrol_summary,
    )


def load_sold_urls() -> set[str]:
    """Load sold property URLs from status file."""
    status_file = Path(__file__).parent / "data" / "property_status.json"
    if not status_file.exists():
        return set()
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        return {
            url.rstrip("/") + "/"
            for url, info in data.get("properties", {}).items()
            if info.get("status") == "SOLD"
        }
    except Exception:
        return set()


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

    def _is_pet_ng(r: PropertyRow) -> bool:
        text = f"{r.pet_status} {r.name} {r.raw_line}"
        if r.pet_status == "不可" or "ペット不可" in text or "ペット飼育不可" in text:
            return True
        return False

    deduped = [r for r in deduped if not _is_pet_ng(r)]
    pet_ng_count = before_pet - len(deduped)

    # Filter out 民泊禁止 properties
    before_minpaku = len(deduped)

    def _is_minpaku_ng(r: PropertyRow) -> bool:
        text = f"{r.minpaku_status} {r.name} {r.raw_line}"
        return "民泊禁止" in text or "民泊不可" in text or "住宅宿泊事業不可" in text

    deduped = [r for r in deduped if not _is_minpaku_ng(r)]
    minpaku_ng_count = before_minpaku - len(deduped)

    for row in deduped:
        score_row(row, config)

    # 厳選フィルタ: 最低スコア閾値 + 上位N件に制限
    MIN_SCORE = 30
    MAX_DISPLAY = 50
    before_quality = len(deduped)
    deduped = [r for r in deduped if r.total_score >= MIN_SCORE]
    quality_filtered = before_quality - len(deduped)
    deduped_sorted = sorted(deduped, key=lambda r: -r.total_score)
    if len(deduped_sorted) > MAX_DISPLAY:
        # ペット可物件を優先保護: 先にペット可を確保、残り枠を高スコア順で埋める
        def _is_pet_ok(r: PropertyRow) -> bool:
            return r.pet_status in ("可", "相談可") or r.pet_score >= 10
        pet_ok = [r for r in deduped_sorted if _is_pet_ok(r)]
        others = [r for r in deduped_sorted if not _is_pet_ok(r)]
        remaining_slots = max(0, MAX_DISPLAY - len(pet_ok))
        deduped = pet_ok + others[:remaining_slots]
        deduped = sorted(deduped, key=lambda r: -r.total_score)
        top_n_trimmed = len(deduped_sorted) - len(deduped)
    else:
        deduped = deduped_sorted
        top_n_trimmed = 0

    meta["sources_loaded"] = ", ".join(sources_loaded)
    meta["sold_removed"] = str(sold_count)
    meta["oc_removed"] = str(oc_count)
    meta["pet_ng_removed"] = str(pet_ng_count)
    meta["minpaku_ng_removed"] = str(minpaku_ng_count)
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
    if quality_filtered > 0:
        print(f"  Removed {quality_filtered} low-score (< {MIN_SCORE}) properties")
    if top_n_trimmed > 0:
        print(f"  Trimmed to top {MAX_DISPLAY} (cut {top_n_trimmed} lower-ranked)")
    print(f"  Final: {len(deduped)}件 厳選済み")

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
