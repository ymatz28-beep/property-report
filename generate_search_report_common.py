from __future__ import annotations

import datetime as dt
import html
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


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
    raw_line: str = ""
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


def _normalize_name(name: str) -> str:
    """Normalize property name for dedup (handles katakana variants like シティ/シテイ)."""
    s = re.sub(r"[\s　]+", "", name)
    s = s.replace("テイ", "ティ").replace("ヴィ", "ビ")
    s = re.sub(r"[Ⅰ-Ⅻ]", lambda m: str("ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ".index(m.group()) + 1), s)
    return s


def dedupe_properties(rows: list[PropertyRow]) -> tuple[list[PropertyRow], int]:
    seen: set[tuple] = set()
    out: list[PropertyRow] = []
    dup_count = 0
    for row in rows:
        # Primary key: normalized name + area_sqm (same building, same unit)
        norm = _normalize_name(row.name)
        key_physical = (norm, row.area_sqm)
        # Fallback: original name + price
        key_name_price = (row.name, row.price_man)
        if key_physical in seen or key_name_price in seen:
            dup_count += 1
            continue
        seen.add(key_physical)
        seen.add(key_name_price)
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
    checks = [
        ("博多駅/祇園", 20, ["博多駅", "祇園"]),
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
        if any(kw in text for kw in kws):
            return label, score
    return "Other", -5


def pet_score_for_row(row: PropertyRow) -> int:
    """Pet scoring: 可=15, 相談可=10, SUUMO(filtered for pet)=10, unknown=0, 不可=-5"""
    text = f"{row.pet_status} {row.name} {row.minpaku_status}"
    # Check 不可 BEFORE 可 to avoid false positives
    if "ペット不可" in text or row.pet_status == "不可":
        return -5
    if "ペット可" in text or row.pet_status == "可":
        return 15
    if "ペット相談" in text or row.pet_status == "相談可":
        return 10
    if row.source == "SUUMO":
        # SUUMO data was pre-filtered for ペット相談可
        return 10
    return 0


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
    """Renovation scoring: unrenovated=5 (can DIY), renovated=0, unknown=3"""
    text = f"{row.name} {row.raw_line}".lower()
    renovated_keywords = [
        "リノベーション済", "リノベ済", "リフォーム済", "フルリノベ",
        "フルリフォーム", "新装", "内装済", "室内リフォーム",
        "リノベーション済み", "リフォーム済み",
    ]
    if any(kw.lower() in text for kw in renovated_keywords):
        return 0  # Already renovated - no DIY opportunity
    unrenovated_keywords = [
        "現況", "現状渡し", "そのまま", "古い",
    ]
    if any(kw in text for kw in unrenovated_keywords):
        return 5  # Clearly unrenovated - DIY opportunity
    return 3  # Unknown - likely unrenovated (most used condos)


def minpaku_penalty(row: PropertyRow) -> int:
    return -30 if "民泊禁止" in row.minpaku_status else 0


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
    if b.get("renovation", 0) >= 5:
        strengths.append("リノベ余地あり")
    if b.get("brokerage", 0) >= 3:
        strengths.append(f"仲介手数料{row.brokerage_text}")
    if b.get("renovation", 0) == 0:
        cautions.append("リノベ済み（DIY余地なし）")
    if b.get("pet", 0) <= 0:
        cautions.append("ペット条件要確認")
    if b.get("minpaku_penalty", 0) < 0:
        cautions.append("民泊規約で大幅減点")
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


def build_report_html(config: ReportConfig, rows: list[PropertyRow], meta: dict[str, str], raw_count: int, duplicate_count: int) -> str:
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

    radar_labels = ["予算", "面積", "耐震", "駅距離", "立地", "間取り", "ペット", "リノベ余地", "仲介手数料", "民泊規約"]
    radar_datasets = []
    for i, r in enumerate(top5):
        b = r.score_breakdown
        radar_datasets.append(
            {
                "label": f"{i+1}. {r.name[:18]}",
                "data": [
                    round(b["budget"] / 20 * 100),
                    round(b["area"] / 15 * 100),
                    round(b["earthquake"] / 15 * 100),
                    round(b["station"] / 15 * 100),
                    round(b["location"] / 15 * 100),
                    round(b["layout"] / 10 * 100),
                    max(0, round(b["pet"] / 15 * 100)),
                    round(b["renovation"] / 5 * 100),
                    round(b["brokerage"] / 5 * 100),
                    0 if b["minpaku_penalty"] < 0 else 100,
                ],
                "borderWidth": 2,
            }
        )

    table_rows_html = []
    for idx, r in enumerate(rows_sorted, start=1):
        score_badge = f'<span class="score-badge" style="--badge:{r.tier_color}">{r.total_score}</span>'
        link = f'<a href="{html.escape(r.url)}" target="_blank" rel="noopener noreferrer">{html.escape(r.name)}</a>'
        built_disp = f"{r.built_year}年" if r.built_year else html.escape(r.built_text)
        table_rows_html.append(
            f"""
            <tr class="{r.tier_class}" data-index="{idx}" data-name="{html.escape(r.name)}" data-location="{html.escape(r.location)}" data-layout="{html.escape(r.layout)}" data-tier="{html.escape(r.tier_label)}" data-price="{r.price_man}" data-area="{(r.area_sqm or 0):.2f}" data-score="{r.total_score}" data-year="{r.built_year or 0}" data-walk="{r.walk_min if r.walk_min is not None else 999}">
              <td>{idx}</td>
              <td class="name-col">{link}<div class="source-tag">{html.escape(r.source)}</div></td>
              <td>{format_price_man(r.price_man)}</td>
              <td>{format_area(r.area_sqm)}</td>
              <td>{html.escape(r.location)}</td>
              <td>{html.escape(r.station_text)}</td>
              <td>{built_disp}</td>
              <td>{html.escape(r.layout)}</td>
              <td>{score_badge}</td>
              <td><span class="tier-pill" style="--tier:{r.tier_color}">{html.escape(r.tier_label)}</span></td>
            </tr>
            """
        )

    focus_cards_html = []
    for i, r in enumerate(top5, start=1):
        b = r.score_breakdown
        chips = [
            ("予算", b["budget"]),
            ("面積", b["area"]),
            ("耐震", b["earthquake"]),
            ("駅", b["station"]),
            ("立地", b["location"]),
            ("間取り", b["layout"]),
            ("ペット", b["pet"]),
            ("リノベ", b["renovation"]),
            ("仲介", b["brokerage"]),
            ("民泊規約", b["minpaku_penalty"]),
        ]
        chip_html = "".join(
            f'<span class="chip {"chip-penalty" if v < 0 else ""}">{html.escape(k)} {v:+d}</span>' for k, v in chips
        )
        focus_cards_html.append(
            f"""
            <article class="focus-card">
              <div class="focus-head">
                <div class="focus-rank">#{i}</div>
                <div>
                  <h3><a href="{html.escape(r.url)}" target="_blank" rel="noopener noreferrer">{html.escape(r.name)}</a></h3>
                  <p>{format_price_man(r.price_man)} / {format_area(r.area_sqm)} / {html.escape(r.location)}</p>
                </div>
                <div class="focus-score" style="--accent:{r.tier_color}">{r.total_score}<span>{html.escape(r.tier_label)}</span></div>
              </div>
              <div class="chip-row">{chip_html}</div>
              <p class="focus-comment">{html.escape(r.detail_comment)}</p>
              <div class="focus-meta">
                <span>{html.escape(r.station_text)}</span>
                <span>{html.escape(r.built_text)}</span>
                <span>{html.escape(r.layout)}</span>
                {"<span>"+html.escape(r.minpaku_status)+"</span>" if r.minpaku_status else ""}
              </div>
            </article>
            """
        )

    sources_str = meta.get("sources_loaded", "SUUMO")
    city_badge = f"データソース: {sources_str}"
    html_doc = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(config.city_label)} 物件検索レポート</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg:#0b0f16;
      --bg2:#101826;
      --card:rgba(255,255,255,0.045);
      --line:rgba(255,255,255,0.12);
      --muted:#a9b3c6;
      --text:#edf3ff;
      --accent:{config.accent};
      --accent-rgb:{config.accent_rgb};
      --success:#22c55e;
      --warn:#f59e0b;
      --danger:#ef4444;
      --radius:18px;
      --shadow:0 18px 60px rgba(0,0,0,0.45);
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      color:var(--text);
      font-family:"Inter","Noto Sans JP",sans-serif;
      background:
        radial-gradient(circle at 15% -10%, rgba(var(--accent-rgb),0.16), transparent 40%),
        radial-gradient(circle at 88% 12%, rgba(110,120,255,0.10), transparent 45%),
        linear-gradient(180deg,#070b11,#0b0f16 28%, #0d1320 100%);
    }}
    .wrap {{ max-width:1280px; margin:0 auto; padding:24px 16px 44px; }}
    .hero {{
      position:relative;
      padding:28px;
      border-radius:24px;
      border:1px solid var(--line);
      background:linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
      box-shadow:var(--shadow);
      overflow:hidden;
      backdrop-filter: blur(12px);
    }}
    .hero::after {{
      content:"";
      position:absolute; inset:auto -10% -35% auto;
      width:360px; height:360px; border-radius:50%;
      background:radial-gradient(circle, rgba(var(--accent-rgb),0.22), transparent 70%);
      filter:blur(8px);
    }}
    .kicker {{ color:var(--muted); letter-spacing:.12em; text-transform:uppercase; font-weight:700; font-size:12px; }}
    h1 {{ margin:10px 0 10px; font-size:clamp(28px,4.2vw,46px); line-height:1.06; font-weight:900; font-family:"Noto Sans JP","Inter",sans-serif; }}
    .hero-sub {{ color:#d0d9eb; margin:0; max-width:860px; }}
    .badge-row {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
    .badge {{
      display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px;
      border:1px solid rgba(var(--accent-rgb),0.35);
      background:rgba(var(--accent-rgb),0.08);
      color:#e8fbff; font-size:12px; font-weight:600;
    }}
    .grid-4 {{
      margin-top:16px;
      display:grid;
      grid-template-columns:repeat(4, minmax(0,1fr));
      gap:14px;
    }}
    .card {{
      border:1px solid var(--line);
      background:var(--card);
      border-radius:var(--radius);
      padding:16px;
      backdrop-filter: blur(10px);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.03);
    }}
    .stat .label {{ color:var(--muted); font-size:12px; }}
    .stat .value {{ font-size:28px; font-weight:800; margin-top:6px; }}
    .stat .sub {{ color:#cdd6e8; font-size:12px; margin-top:4px; }}
    .section {{
      margin-top:16px;
      border:1px solid var(--line);
      background:var(--card);
      border-radius:var(--radius);
      padding:18px;
      backdrop-filter: blur(10px);
    }}
    .section h2 {{
      margin:0 0 12px; font-size:18px; font-weight:800; letter-spacing:.02em;
      display:flex; align-items:center; gap:10px;
    }}
    .section h2::before {{
      content:"";
      width:10px; height:10px; border-radius:50%;
      background:var(--accent);
      box-shadow:0 0 0 6px rgba(var(--accent-rgb),.12);
    }}
    .cond-list {{
      margin:0; padding-left:18px; color:#d8e0f0; line-height:1.75;
      columns:2; column-gap:24px;
    }}
    .table-shell {{ overflow:auto; border-radius:14px; border:1px solid rgba(255,255,255,.08); }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; min-width:1180px; }}
    thead th {{
      position:sticky; top:0; z-index:1;
      background:rgba(12,17,26,.92); color:#dbe7fa;
      font-size:12px; text-align:left; padding:12px 10px;
      border-bottom:1px solid rgba(255,255,255,.08);
      white-space:nowrap;
    }}
    thead th button {{
      all:unset; cursor:pointer; color:inherit; font-weight:700;
      display:inline-flex; gap:6px; align-items:center;
    }}
    tbody td {{
      padding:12px 10px; border-bottom:1px solid rgba(255,255,255,.05);
      font-size:13px; vertical-align:top;
    }}
    tbody tr:nth-child(even) td {{ background:rgba(255,255,255,.012); }}
    tbody tr:hover td {{ background:rgba(var(--accent-rgb),.06); }}
    .tier-strong td {{ box-shadow: inset 4px 0 0 rgba(34,197,94,.7); }}
    .tier-good td {{ box-shadow: inset 4px 0 0 rgba(250,204,21,.7); }}
    .tier-conditional td {{ box-shadow: inset 4px 0 0 rgba(251,146,60,.7); }}
    .tier-pass td {{ box-shadow: inset 4px 0 0 rgba(239,68,68,.7); }}
    a {{ color:#eaf7ff; text-decoration:none; }}
    a:hover {{ color:var(--accent); text-decoration:underline; }}
    .name-col a {{ font-weight:700; }}
    .source-tag {{
      margin-top:4px; font-size:11px; color:var(--muted);
      display:inline-block; padding:2px 8px; border-radius:999px;
      border:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.02);
    }}
    .score-badge {{
      display:inline-grid; place-items:center;
      min-width:38px; padding:5px 10px; border-radius:999px;
      border:1px solid color-mix(in oklab, var(--badge) 50%, white 10%);
      background:color-mix(in oklab, var(--badge) 16%, transparent);
      color:#fff; font-weight:800;
    }}
    .tier-pill {{
      display:inline-flex; align-items:center; padding:4px 10px; border-radius:999px;
      border:1px solid color-mix(in oklab, var(--tier) 45%, white 8%);
      background:color-mix(in oklab, var(--tier) 14%, transparent);
      font-weight:700; font-size:12px;
    }}
    .focus-grid {{
      display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:14px;
    }}
    .focus-card {{
      border-radius:18px; border:1px solid var(--line);
      background:linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
      padding:14px; box-shadow:var(--shadow);
    }}
    .focus-head {{ display:grid; grid-template-columns:auto 1fr auto; gap:12px; align-items:start; }}
    .focus-rank {{
      width:36px; height:36px; border-radius:12px; display:grid; place-items:center;
      background:rgba(var(--accent-rgb),.12); border:1px solid rgba(var(--accent-rgb),.35); font-weight:800;
    }}
    .focus-head h3 {{ margin:0; font-size:17px; line-height:1.3; }}
    .focus-head p {{ margin:4px 0 0; color:var(--muted); font-size:12px; }}
    .focus-score {{
      min-width:68px; text-align:center; font-weight:900; font-size:24px;
      color:#fff; border-radius:14px; padding:8px 10px;
      border:1px solid color-mix(in oklab, var(--accent) 40%, white 8%);
      background:color-mix(in oklab, var(--accent) 14%, transparent);
    }}
    .focus-score span {{ display:block; margin-top:4px; font-size:10px; color:#dfe8f7; font-weight:700; }}
    .chip-row {{ margin-top:10px; display:flex; flex-wrap:wrap; gap:8px; }}
    .chip {{
      display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:700;
      padding:5px 8px; border-radius:999px; border:1px solid rgba(255,255,255,.09);
      background:rgba(255,255,255,.03); color:#e6eefc;
    }}
    .chip-penalty {{ border-color:rgba(239,68,68,.25); background:rgba(239,68,68,.10); color:#ffdada; }}
    .focus-comment {{ margin:10px 0 0; color:#dbe4f4; line-height:1.65; font-size:13px; }}
    .focus-meta {{ margin-top:10px; display:flex; flex-wrap:wrap; gap:8px; color:var(--muted); font-size:12px; }}
    .focus-meta span {{ padding:4px 8px; border-radius:999px; border:1px solid rgba(255,255,255,.06); background:rgba(255,255,255,.02); }}
    .chart-grid {{ display:grid; grid-template-columns:1.2fr 1fr; gap:14px; }}
    .chart-col {{ display:grid; gap:14px; }}
    .chart-card canvas {{ width:100%; max-height:360px; }}
    .notes {{ margin:0; padding-left:18px; line-height:1.8; color:#d9e2f3; }}
    .footer {{ margin-top:16px; color:var(--muted); font-size:12px; text-align:center; }}
    .footer a {{ color:#cfeeff; }}
    @media (max-width: 960px) {{
      .grid-4 {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
      .chart-grid, .focus-grid {{ grid-template-columns:1fr; }}
      .cond-list {{ columns:1; }}
      .hero {{ padding:18px; }}
    }}
    @media (max-width: 560px) {{
      .grid-4 {{ grid-template-columns:1fr; }}
      .focus-head {{ grid-template-columns:auto 1fr; }}
      .focus-score {{ grid-column:1/-1; justify-self:start; min-width:auto; width:fit-content; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      * {{ scroll-behavior:auto !important; animation:none !important; transition:none !important; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="kicker">PROPERTY SEARCH REPORT / {html.escape(config.city_label.upper())}</div>
      <h1>{html.escape(config.city_label)} 民泊向け中古マンション候補レポート</h1>
      <p class="hero-sub">検索データを実行時に解析し、重複排除・立地評価・民泊適性スコアリングを実施。テーブルはクリックソート対応、上位候補はスコア内訳まで確認できます。</p>
      <div class="badge-row">
        <span class="badge">検索日 {html.escape(search_date)}</span>
        <span class="badge">原データ {raw_count}件</span>
        <span class="badge">重複除外 {duplicate_count}件</span>
        <span class="badge">売却済除外 {meta.get("sold_removed", "0")}件</span>
        <span class="badge">OC除外 {meta.get("oc_removed", "0")}件</span>
        <span class="badge">有効件数 {len(rows_sorted)}件</span>
        <span class="badge">{html.escape(city_badge)}</span>
      </div>
      <div class="badge-row">
        {''.join(f'<span class="badge">{html.escape(b)}</span>' for b in config.hero_conditions)}
      </div>
    </section>

    <section class="grid-4">
      <div class="card stat"><div class="label">総候補数</div><div class="value">{len(rows_sorted)}</div><div class="sub">重複排除後</div></div>
      <div class="card stat"><div class="label">平均価格</div><div class="value">{avg_price:,.1f}万円</div><div class="sub">全候補平均</div></div>
      <div class="card stat"><div class="label">平均面積</div><div class="value">{avg_area:.2f}㎡</div><div class="sub">全候補平均</div></div>
      <div class="card stat"><div class="label">最高スコア</div><div class="value">{top_prop.total_score if top_prop else '-'}</div><div class="sub">{html.escape(top_prop.name if top_prop else '')}</div></div>
    </section>

    <section class="section">
      <h2>Search Conditions</h2>
      <ul class="cond-list">
        <li>データ元条件: {html.escape(meta.get("conditions", "5000万以下 / 40-70㎡ / ペット相談可"))}</li>
        <li>重複排除キー: 物件名 + 価格（先勝ち）</li>
        <li>駅アクセスに「バス」を含む場合、徒歩分数評価は0点</li>
        <li>築年1981年7月以降を新耐震として評価</li>
        <li>民泊禁止は -30 点ペナルティ</li>
        {''.join(f"<li>{html.escape(item)}</li>" for item in config.search_condition_bullets)}
      </ul>
    </section>

    <section class="section">
      <h2>Property Table</h2>
      <div class="table-shell">
        <table id="propertyTable">
          <thead>
            <tr>
              <th><button data-sort="index" data-type="number">#</button></th>
              <th><button data-sort="name" data-type="string">物件名</button></th>
              <th><button data-sort="price" data-type="number">価格</button></th>
              <th><button data-sort="area" data-type="number">面積</button></th>
              <th><button data-sort="location" data-type="string">所在地</button></th>
              <th><button data-sort="walk" data-type="number">最寄駅</button></th>
              <th><button data-sort="year" data-type="number">築年</button></th>
              <th><button data-sort="layout" data-type="string">間取り</button></th>
              <th><button data-sort="score" data-type="number">スコア</button></th>
              <th><button data-sort="tier" data-type="string">評価</button></th>
            </tr>
          </thead>
          <tbody>
            {''.join(table_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Top 5 Focus Cards</h2>
      <div class="focus-grid">
        {''.join(focus_cards_html)}
      </div>
    </section>

    <section class="section">
      <h2>Charts</h2>
      <div class="chart-grid">
        <div class="card chart-card"><canvas id="radarChart"></canvas></div>
        <div class="chart-col">
          <div class="card chart-card"><canvas id="bucketChart"></canvas></div>
          <div class="card chart-card"><canvas id="priceChart"></canvas></div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Investor Notes</h2>
      <ul class="notes">
        {''.join(f'<li>{html.escape(n)}</li>' for n in config.investor_notes)}
      </ul>
    </section>

    <div class="footer">
      <div>Sources: {html.escape(sources_str)} ({html.escape(str(config.data_path))}{' + ' + ', '.join(str(p) for p in config.extra_data_paths) if config.extra_data_paths else ''})</div>
      <div>Generated on {html.escape(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}</div>
    </div>
  </div>

  <script>
    const chartAccent = 'rgba({config.accent_rgb}, 1)';
    const chartAccentFill = 'rgba({config.accent_rgb}, 0.18)';
    const radarLabels = {safe_json(radar_labels)};
    const radarDatasets = {safe_json(radar_datasets)}.map((d, i) => {{
      const hueShift = [0, 18, 35, 52, 70][i] || 0;
      const alpha = 0.14 + i * 0.03;
      return {{
        ...d,
        borderColor: i === 0 ? chartAccent : `hsla(${{(195 + hueShift)%360}}, 90%, 68%, .95)`,
        backgroundColor: i === 0 ? chartAccentFill : `hsla(${{(195 + hueShift)%360}}, 90%, 68%, ${{alpha}})`,
        pointRadius: 2,
        pointHoverRadius: 4,
      }};
    }});
    const bucketLabels = {safe_json(list(bucket_counts.keys()))};
    const bucketValues = {safe_json(list(bucket_counts.values()))};
    const priceLabels = {safe_json(price_bin_labels)};
    const priceValues = {safe_json(price_bin_values)};

    const commonGrid = {{
      color: 'rgba(255,255,255,0.08)',
      drawBorder: false,
    }};
    const commonTicks = {{ color: 'rgba(220,230,245,0.8)', font: {{ family: 'Inter, Noto Sans JP, sans-serif' }} }};

    new Chart(document.getElementById('radarChart'), {{
      type: 'radar',
      data: {{ labels: radarLabels, datasets: radarDatasets }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ labels: {{ color: '#e8efff' }} }},
          title: {{ display: true, text: 'Top5 スコア内訳比較（0-100正規化）', color: '#e8efff' }}
        }},
        scales: {{
          r: {{
            suggestedMin: 0,
            suggestedMax: 100,
            angleLines: {{ color: 'rgba(255,255,255,0.08)' }},
            grid: {{ color: 'rgba(255,255,255,0.08)' }},
            pointLabels: {{ color: 'rgba(230,240,255,0.88)', font: {{ size: 11 }} }},
            ticks: {{ backdropColor: 'transparent', color: 'rgba(220,230,245,0.55)', stepSize: 20 }}
          }}
        }}
      }}
    }});

    new Chart(document.getElementById('bucketChart'), {{
      type: 'bar',
      data: {{
        labels: bucketLabels,
        datasets: [{{
          label: '件数',
          data: bucketValues,
          borderRadius: 8,
          borderSkipped: false,
          backgroundColor: bucketValues.map((_, i) => `rgba({config.accent_rgb}, ${{0.35 + (i % 5) * 0.1}})`),
          borderColor: bucketValues.map((_, i) => `rgba({config.accent_rgb}, ${{0.7 + (i % 3) * 0.1}})`),
          borderWidth: 1
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          title: {{ display: true, text: 'エリア分布（立地バケット別件数）', color: '#e8efff' }}
        }},
        scales: {{
          x: {{ ticks: commonTicks, grid: {{ display: false }} }},
          y: {{ ticks: commonTicks, grid: commonGrid, beginAtZero: true }}
        }}
      }}
    }});

    new Chart(document.getElementById('priceChart'), {{
      type: 'bar',
      data: {{
        labels: priceLabels,
        datasets: [{{
          label: '件数',
          data: priceValues,
          borderRadius: 8,
          borderSkipped: false,
          backgroundColor: priceValues.map((_, i) => `rgba(255,255,255, ${{0.14 + (i % 4) * 0.05}})`),
          borderColor: priceValues.map(() => chartAccent),
          borderWidth: 1
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          title: {{ display: true, text: '価格分布（500万円刻み）', color: '#e8efff' }}
        }},
        scales: {{
          x: {{ ticks: commonTicks, grid: {{ display: false }} }},
          y: {{ ticks: commonTicks, grid: commonGrid, beginAtZero: true }}
        }}
      }}
    }});

    (() => {{
      const table = document.getElementById('propertyTable');
      const tbody = table.querySelector('tbody');
      const headers = table.querySelectorAll('thead button[data-sort]');
      let sortState = {{ key: 'score', dir: 'desc' }};

      const valueFor = (row, key, type) => {{
        if (key === 'name') {{
          return (row.dataset.name || '').toLowerCase();
        }}
        const v = row.dataset[key];
        return type === 'number' ? Number(v) : (v || '');
      }};

      const applySort = (key, type) => {{
        if (sortState.key === key) {{
          sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
        }} else {{
          sortState = {{ key, dir: key === 'score' ? 'desc' : 'asc' }};
        }}
        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort((a, b) => {{
          const av = valueFor(a, key, type);
          const bv = valueFor(b, key, type);
          let cmp = 0;
          if (type === 'number') cmp = av - bv;
          else cmp = String(av).localeCompare(String(bv), 'ja');
          if (cmp === 0) cmp = Number(a.dataset.index) - Number(b.dataset.index);
          return sortState.dir === 'asc' ? cmp : -cmp;
        }});
        rows.forEach(r => tbody.appendChild(r));
        headers.forEach(h => h.textContent = h.textContent.replace(/[↑↓]$/, ''));
        const active = Array.from(headers).find(h => h.dataset.sort === key);
        if (active) active.textContent = active.textContent + (sortState.dir === 'asc' ? '↑' : '↓');
      }};

      headers.forEach(h => {{
        h.addEventListener('click', () => applySort(h.dataset.sort, h.dataset.type || 'string'));
      }});
    }})();
  </script>
</body>
</html>
"""
    return html_doc


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
        "家賃", "月額賃料", "年間収入", "年間賃料", "月額",
        "表面利回", "想定利回", "収益",
    ]
    before_oc = len(deduped)

    def _is_oc(r: PropertyRow) -> bool:
        text = f"{r.name} {r.station_text} {r.minpaku_status}"
        return any(kw in text for kw in _OC_KEYWORDS)

    deduped = [r for r in deduped if not _is_oc(r)]
    oc_count = before_oc - len(deduped)

    for row in deduped:
        score_row(row, config)
    meta["sources_loaded"] = ", ".join(sources_loaded)
    meta["sold_removed"] = str(sold_count)
    meta["oc_removed"] = str(oc_count)
    html_text = build_report_html(config, deduped, meta, raw_count=raw_count, duplicate_count=duplicate_count)
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    config.output_path.write_text(html_text, encoding="utf-8")
    if sold_count > 0:
        print(f"  Removed {sold_count} sold properties")
    if oc_count > 0:
        print(f"  Removed {oc_count} owner-change/tenant-occupied properties")
    return config.output_path
