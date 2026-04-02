#!/usr/bin/env python3
"""
Property Inquiry Pipeline — Lifecycle automation.

Status flow:
  discovered → flagged → inquired → in_discussion → viewing → viewed → decided | passed

Commands:
  --auto-flag [SCORE]   Flag high-score properties from daily patrol data
  --list [STATUS]       List inquiries (optionally filtered by status)
  --inquire ID          Mark as inquired (問い合わせ送信済み)
  --extract ID          Extract structured data from email reply (reads stdin or --file)
  --viewing ID DATE     Schedule viewing + create action item
  --viewed ID [NOTES]   Record viewing result
  --decide ID go|pass   Record decision
  --sync                Sync viewing/status from inbox-zero agent_memory
  --dashboard           Generate pipeline dashboard HTML
  --naiken              Generate naiken analysis for viewing properties
  --lifecycle           Run full lifecycle management (sweep stale + price tracking + sync)
  --stats               Show pipeline statistics
  --recalc [ID...]      Recalculate CF/CCR for specified IDs (or 'all' for all active)
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

from revenue_calc import InvestmentParams, analyze as revenue_analyze

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
INQUIRIES_PATH = DATA / "inquiries.yaml"
OUTPUT = BASE / "output"

# Make the report pipeline importable
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# Make the shared lib importable (Projects root)
_PROJECTS_ROOT = str(BASE.parent)
if _PROJECTS_ROOT not in sys.path:
    sys.path.insert(0, _PROJECTS_ROOT)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
GNAV_PAGES = [
    {"href": "index.html", "label": "Hub"},
    {"href": "market.html", "label": "Market"},
    {"href": "naiken-analysis.html", "label": "内覧分析"},
    {"href": "inquiry-messages.html", "label": "問い合わせ"},
    {"href": "inquiry-pipeline.html", "label": "Pipeline"},
]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FLAG_THRESHOLD = 55
FLAG_TOP_N = 30  # Max new flagged per cycle

STATUSES = [
    "discovered", "flagged", "inquired",
    "in_discussion", "viewing", "viewed",
    "decided", "passed",
]

STATUS_LABELS = {
    "discovered": "発見",
    "flagged": "候補",
    "inquired": "問い合わせ済",
    "in_discussion": "やり取り中",
    "viewing": "内見予定",
    "viewed": "内見済",
    "decided": "決定",
    "passed": "見送り",
}

STATUS_COLORS = {
    "discovered": "#71717a",
    "flagged": "#3b9eff",
    "inquired": "#f59e0b",
    "in_discussion": "#f97316",
    "viewing": "#a78bfa",
    "viewed": "#6366f1",
    "decided": "#22c55e",
    "passed": "#ef4444",
}

CITY_LABELS = {"osaka": "大阪", "fukuoka": "福岡", "tokyo": "東京"}

# Ad-copy markers that indicate a name is not a real building name
_AD_MARKERS = ["利回り", "！", "オーナーチェンジ", "人気の", "駅利用", "アクセス",
               "徒歩圏", "リフォーム完了", "分譲マンション", "♪", "【", "▶", "★",
               "☆", "◆", "「", "エリア、"]
_BLDG_SUFFIXES = ["マンション", "コーポ", "ハイツ", "パレス", "レジデンス", "ビル",
                  "タワー", "パーク", "コート", "メゾン", "プラザ", "ハウス", "ドーム",
                  "シャトー", "テラス", "ガーデン", "グラン", "ロイヤル", "アーバン",
                  "サニー", "ライオンズ", "アンピール", "ピュアドーム"]


def _clean_property_name(name: str, source: str = "", city_key: str = "") -> str:
    """Remove ad-copy from property names. Returns cleaned name or area-based fallback."""
    if not name:
        return name
    has_ad = any(m in name for m in _AD_MARKERS)
    has_bldg = any(s in name for s in _BLDG_SUFFIXES)
    if has_ad and not has_bldg:
        # Ad-copy without building suffix → not a real name
        return name  # Will be caught by fallback below
    if len(name) > 40 and has_ad:
        # Long name with ad markers → likely ad-copy even if it contains a suffix
        import re
        for s in _BLDG_SUFFIXES:
            m = re.search(rf"([ァ-ヶーa-zA-Z\d]{{2,}}(?:{s})[^\s,。、♪！]*)", name)
            if m:
                return m.group(1)[:40]
    return name


def _clean_station(station: str) -> str:
    """駅名を簡略表示: 路線名プレフィックスと「駅」サフィックスを除去。
    例: "福岡市七隈線渡辺通駅 徒歩8分" → "渡辺通 徒歩8分"
        "JR博多駅 徒歩5分" → "博多 徒歩5分"
    """
    if not station:
        return station
    # Remove railway line prefixes (e.g. "福岡市七隈線", "JR鹿児島本線", "西鉄天神大牟田線")
    import re as _re
    cleaned = _re.sub(r"[^\s　]+線", "", station).strip()
    if not cleaned:
        cleaned = station  # fallback if entire string was a line name
    # Remove trailing "駅" from station name token (preserve walk-time part)
    # e.g. "渡辺通駅 徒歩8分" → "渡辺通 徒歩8分"
    cleaned = _re.sub(r"([^\s　]+)駅(\s|　|$)", r"\1\2", cleaned)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------


def load_inquiries() -> list[dict]:
    if not INQUIRIES_PATH.exists():
        return []
    with open(INQUIRIES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("inquiries", [])


def _sync_to_registry(inquiries: list[dict]) -> None:
    """Write-through: sync pipeline decisions to property registry (property_status.json)."""
    status_file = BASE / "data" / "property_status.json"
    try:
        registry = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {"properties": {}}
        for inq in inquiries:
            url = inq.get("url", "")
            if not url:
                continue
            url_key = url.rstrip("/") + "/"
            entry = registry["properties"].get(url_key, {})

            # Sync field overrides
            overrides = entry.get("overrides", {})
            if inq.get("price"):
                overrides["price"] = inq["price"]
            if inq.get("name"):
                overrides["name"] = inq["name"]
            entry["overrides"] = overrides
            entry["linked_inquiry"] = inq.get("id")

            # Sync exclusion status
            if inq.get("status") == "passed":
                entry["status"] = "EXCLUDED"
                entry["exclude_reason"] = inq.get("decision", "passed")

            registry["properties"][url_key] = entry

        registry["last_sync"] = datetime.now().isoformat()
        status_file.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[registry sync] warning: {e}", file=sys.stderr)


def save_inquiries(inquiries: list[dict]) -> None:
    INQUIRIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INQUIRIES_PATH, "w", encoding="utf-8") as f:
        f.write("# Property Inquiry Pipeline — State Tracking\n")
        f.write(f"# Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("# Status: discovered → flagged → inquired → in_discussion → viewing → viewed → decided | passed\n\n")
        yaml.dump(
            {"inquiries": inquiries},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    _sync_to_registry(inquiries)


def _next_id(inquiries: list[dict]) -> str:
    max_num = 0
    for inq in inquiries:
        try:
            num = int(inq["id"].split("-")[1])
            max_num = max(max_num, num)
        except (IndexError, ValueError):
            pass
    return f"inq-{max_num + 1:03d}"


# ---------------------------------------------------------------------------
# Sync from agent memory (inbox-zero → inquiries.yaml)
# ---------------------------------------------------------------------------


def _name_match(inq_name: str, mem_name: str) -> bool:
    """Fuzzy name match between inquiries.yaml and agent_memory."""
    if not inq_name or not mem_name:
        return False
    # Exact match
    if inq_name == mem_name:
        return True
    # One contains the other (handles partial names)
    if mem_name in inq_name or inq_name in mem_name:
        return True
    # Normalize: remove spaces,　, unicode issues
    norm = lambda s: s.replace(" ", "").replace("\u3000", "").replace("\xa0", "")
    return norm(inq_name) == norm(mem_name)


def _extract_viewing_date(text: str) -> str | None:
    """Extract date from freeform text like '3/21(金) 10:00' → '2026-03-21'."""
    import re
    # Pattern: M/D or YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = date.today().year
        return f"{year}-{month:02d}-{day:02d}"
    return None


def _extract_viewing_time(text: str) -> str | None:
    """Extract time from freeform text like '3/21(金) 10:00' → '10:00'."""
    import re
    m = re.search(r"(\d{1,2}:\d{2})", text)
    return m.group(1) if m else None


def sync_from_agent_memory() -> int:
    """Sync viewing/discussion status from inbox-zero agent_memory to inquiries.yaml.

    Reads agent_memory.yaml, matches properties by name to inquiries.yaml entries,
    and updates status + agent + hard-filter results accordingly.
    Only upgrades status (never downgrades).

    Returns count of updates made.
    """
    agent_memory = _load_agent_memory()
    if not agent_memory:
        print("[sync] No agent memory found")
        return 0

    inquiries = load_inquiries()
    existing_names = {inq.get("name", "") for inq in inquiries}
    updates = 0

    for email_addr, mem in agent_memory.items():
        agent_name = mem.get("name", "")
        confirmed = mem.get("confirmed", {})
        properties = mem.get("properties", [])

        for prop in properties:
            if not isinstance(prop, dict):
                continue

            prop_name = prop.get("name", "")
            prop_status = prop.get("status", "")
            viewing_options = prop.get("viewing_options", "")

            # Find matching inquiry by name
            matched = False
            for inq in inquiries:
                if not _name_match(inq.get("name", ""), prop_name):
                    continue
                matched = True

                # Determine target status from agent_memory property status text
                target_status = None
                status_text = prop_status.lower() if prop_status else ""
                if "内覧確定" in prop_status or "内見確定" in prop_status:
                    target_status = "viewing"
                elif "内覧希望" in prop_status or "内見希望" in prop_status:
                    target_status = "viewing"
                elif "やり取り" in prop_status or "確認中" in prop_status or "絞り込み" in prop_status:
                    target_status = "in_discussion"
                elif "問い合わせ" in prop_status:
                    target_status = "inquired"

                if not target_status:
                    continue

                # Only upgrade status (never downgrade)
                current_idx = STATUSES.index(inq.get("status", "flagged")) if inq.get("status", "flagged") in STATUSES else 0
                target_idx = STATUSES.index(target_status)
                if target_idx <= current_idx:
                    continue

                inq["status"] = target_status
                inq["agent"] = agent_name
                inq["updated"] = str(date.today())

                # Extract viewing date/time if available
                date_src = viewing_options or prop_status
                if date_src and target_status == "viewing":
                    vd = _extract_viewing_date(date_src)
                    if vd:
                        inq["viewing_date"] = vd
                    vt = _extract_viewing_time(date_src)
                    if vt:
                        inq["viewing_time"] = vt

                # Update hard filter results from confirmed conditions
                if confirmed.get("pet_ok") is not None:
                    if confirmed["pet_ok"] is True:
                        inq["pet"] = "ok"
                    elif confirmed["pet_ok"] is False:
                        inq["pet"] = "ng"
                if confirmed.get("short_term_ok") is not None and inq.get("short_term") is None:
                    val = confirmed["short_term_ok"]
                    if val is True:
                        inq["short_term"] = "ok"
                    elif val is False:
                        inq["short_term"] = "ng"
                    else:
                        inq["short_term"] = str(val)

                updates += 1
                print(f"[sync] {inq['id']} {inq['name']} → {STATUS_LABELS.get(target_status, target_status)} (agent: {agent_name})")
                break

    if updates:
        save_inquiries(inquiries)
        print(f"[sync] {updates} inquiries updated from agent memory")
    else:
        print("[sync] No updates needed (all up to date)")

    return updates


# ---------------------------------------------------------------------------
# Auto-flag: scan raw data for high-score properties
# ---------------------------------------------------------------------------


def auto_flag(min_score: int = FLAG_THRESHOLD) -> list[dict]:
    """Read all city data, score, flag high-scorers → inquiries.yaml."""
    from generate_inquiry_messages import load_city_properties

    inquiries = load_inquiries()
    existing_urls = {inq["url"] for inq in inquiries}

    new_flagged = []
    for city_key in ("osaka", "fukuoka", "tokyo"):
        try:
            rows = load_city_properties(city_key)
        except Exception as e:
            print(f"  [{city_key}] skip ({e})")
            continue

        for row in rows:
            if row.url in existing_urls:
                continue
            if row.total_score < min_score:
                continue

            # Sublease exclusion: サブリース・家賃保証は不可
            _SUBLEASE_KEYWORDS = ["サブリース", "家賃保証", "一括借上", "借上げ", "マスターリース"]
            text = f"{row.name} {row.station_text} {row.raw_line}"
            if any(kw in text for kw in _SUBLEASE_KEYWORDS):
                continue

            # CF gate: only flag properties with positive cash flow
            if row.price_man and row.area_sqm:
                rent_override = None
                if rent_override:
                    rent_mid = rent_override
                else:
                    rent_per_sqm = {"fukuoka": (1800, 2200), "osaka": (2000, 2500), "tokyo": (2500, 3200)}
                    lo, hi = rent_per_sqm.get(city_key, (2000, 2500))
                    yr_val = row.built_year or 0
                    if yr_val and yr_val >= 2010:
                        lo, hi = int(lo * 1.1), int(hi * 1.1)
                    rent_lo = int(row.area_sqm * lo / 10000)
                    rent_hi = int(row.area_sqm * hi / 10000)
                    rent_mid = (rent_lo + rent_hi) / 2
                if rent_mid > 0:
                    yield_mid = round(rent_mid * 12 / row.price_man * 100, 2)
                    mgmt_fee = row.maintenance_fee or 0
                    age = (2026 - row.built_year) if row.built_year else 0
                    loan_yrs = min(35, max(15, 60 - age)) if age > 0 else 35
                    dr = 0.20
                    params = InvestmentParams(
                        building_ratio=0.50,
                        down_payment_ratio=dr,
                        loan_years=loan_yrs,
                    )
                    rev = revenue_analyze(
                        price_man=row.price_man,
                        yield_pct=yield_mid,
                        structure="RC造",
                        built_year=row.built_year,
                        maintenance_fee_monthly=mgmt_fee,
                        params=params,
                    )
                    # Skip if CF negative or CCR below 3%
                    if rev.verdict != "データ不足":
                        cf_net = rev.monthly_cf
                        if mgmt_fee:
                            cf_net -= mgmt_fee / 10000
                        if cf_net <= 0 or rev.ccr_pct < 3.0:
                            continue

            # Clean ad-copy names
            clean_name = _clean_property_name(row.name, row.source, city_key)

            entry = {
                "id": _next_id(inquiries + new_flagged),
                "name": clean_name,
                "url": row.url,
                "source": row.source,
                "city": city_key,
                "score": row.total_score,
                "status": "flagged",
                "price": row.price_man,
                "area": row.area_sqm,
                "layout": row.layout,
                "station": row.station_text,
                "year_built": row.built_year,
                "pet": row.pet_status or "unknown",
                "short_term": None,
                "management_fee": row.maintenance_fee,
                "agent": None,
                "thread_id": None,
                "viewing_date": None,
                "decision": None,
                "notes": "",
                "created": str(date.today()),
                "updated": str(date.today()),
            }
            new_flagged.append(entry)
            existing_urls.add(row.url)

    if new_flagged:
        inquiries.extend(new_flagged)
        save_inquiries(inquiries)

    print(f"[pipeline] {len(new_flagged)} properties flagged (score >= {min_score})")
    for inq in new_flagged[:5]:
        p = f"{inq['price']:,}" if isinstance(inq.get("price"), (int, float)) else "?"
        print(f"  {inq['id']}  {inq['score']}pt  {p}万  {inq['name']}")
    if len(new_flagged) > 5:
        print(f"  ... and {len(new_flagged) - 5} more")
    return new_flagged


# ---------------------------------------------------------------------------
# Lifecycle management: sweep stale + price tracking
# ---------------------------------------------------------------------------


def sweep_stale() -> dict:
    """Sweep stale flagged inquiries: delisted detection, age-out, still-listed check."""
    import re
    inquiries = load_inquiries()
    today = date.today()
    delisted = 0
    aged_out = 0
    unconfirmed = 0

    # Load property_status.json for delisted detection
    status_json_path = DATA / "property_status.json"
    sold_urls: set[str] = set()
    if status_json_path.exists():
        try:
            with open(status_json_path, encoding="utf-8") as f:
                ps = json.load(f)
            for url, info in ps.get("properties", {}).items():
                if isinstance(info, dict) and info.get("status") == "SOLD":
                    sold_urls.add(url)
        except Exception:
            pass

    # Build set of URLs present in any raw file (for still-listed check)
    raw_urls: set[str] = set()
    for raw_file in DATA.glob("*_raw.txt"):
        try:
            with open(raw_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("|")
                    if parts:
                        url = parts[-1].strip()
                        if url.startswith("http"):
                            raw_urls.add(url)
        except Exception:
            pass

    no_reply = 0
    low_score = 0
    changed = False
    sublease_count = 0

    _SUBLEASE_KEYWORDS = ["サブリース", "家賃保証", "一括借上", "借上げ", "マスターリース"]

    for inq in inquiries:
        status = inq.get("status", "")
        url = inq.get("url", "")
        name = inq.get("name", "")

        # Sublease exclusion: auto-pass any sublease properties in pipeline
        text = f"{name} {inq.get('notes', '')}"
        if any(kw in text for kw in _SUBLEASE_KEYWORDS):
            if status in ("flagged", "inquired", "in_discussion"):
                inq["status"] = "passed"
                existing_notes = inq.get("notes") or ""
                inq["notes"] = (existing_notes + "\nサブリース・家賃保証（自動パス）").strip()
                inq["updated"] = str(today)
                sublease_count += 1
                changed = True
                print(f"[sweep] {inq['id']} {name} → サブリースパス")
                continue

        # --- Applies to flagged AND inquired ---

        # a) Delisted detection: URL marked SOLD in property_status.json
        if status in ("flagged", "inquired") and url and url in sold_urls:
            inq["status"] = "passed"
            existing_notes = inq.get("notes") or ""
            inq["notes"] = (existing_notes + "\n掲載終了（自動検出）").strip()
            inq["updated"] = str(today)
            delisted += 1
            changed = True
            print(f"[sweep] {inq['id']} {inq['name']} → 掲載終了パス")
            continue

        # Skip [future:YYYY-MM] tagged items — 将来のアクション予定がある物件はsweep対象外
        notes = inq.get("notes", "") or ""
        if "[future:" in notes:
            continue

        # --- inquired: no reply detection (14 days) ---
        if status == "inquired":
            inquired_str = inq.get("inquired_date", inq.get("updated", ""))
            if inquired_str:
                try:
                    inquired_dt = date.fromisoformat(str(inquired_str))
                    days_waiting = (today - inquired_dt).days
                    if days_waiting > 14:
                        inq["status"] = "passed"
                        existing_notes = inq.get("notes") or ""
                        inq["notes"] = (existing_notes + f"\n未返信{days_waiting}日（自動パス）").strip()
                        inq["updated"] = str(today)
                        no_reply += 1
                        changed = True
                        print(f"[sweep] {inq['id']} {inq['name']} → 未返信パス ({days_waiting}日)")
                        continue
                except (ValueError, TypeError):
                    pass

        # --- in_discussion: stale detection (14 days no movement) ---
        if status == "in_discussion":
            updated_str = inq.get("updated", "")
            if updated_str:
                try:
                    updated_dt = date.fromisoformat(str(updated_str))
                    days_stale = (today - updated_dt).days
                    if days_stale > 14:
                        inq["status"] = "passed"
                        existing_notes = inq.get("notes") or ""
                        inq["notes"] = (existing_notes + f"\nやり取り停滞{days_stale}日（自動パス）").strip()
                        inq["updated"] = str(today)
                        no_reply += 1
                        changed = True
                        print(f"[sweep] {inq['id']} {inq['name']} → やり取り停滞パス ({days_stale}日)")
                        continue
                except (ValueError, TypeError):
                    pass

        # --- flagged only ---
        if status != "flagged":
            continue

        # b) Age-out: flagged > 30 days with no agent
        created_str = inq.get("created", "")
        if created_str and not inq.get("agent"):
            try:
                created_date = date.fromisoformat(str(created_str))
                if (today - created_date).days > 30:
                    inq["status"] = "passed"
                    existing_notes = inq.get("notes") or ""
                    inq["notes"] = (existing_notes + "\n30日間アクション無し（自動パス）").strip()
                    inq["updated"] = str(today)
                    aged_out += 1
                    changed = True
                    print(f"[sweep] {inq['id']} {inq['name']} → 期限パス (created: {created_str})")
                    continue
            except (ValueError, TypeError):
                pass

        # c) Low-score pruning: flagged with score < 70 and no agent
        score = inq.get("score", 0)
        if isinstance(score, (int, float)) and score < 70 and not inq.get("agent"):
            inq["status"] = "passed"
            existing_notes = inq.get("notes") or ""
            inq["notes"] = (existing_notes + f"\nスコア{score}（基準70未満・自動パス）").strip()
            inq["updated"] = str(today)
            low_score += 1
            changed = True
            print(f"[sweep] {inq['id']} {inq['name']} → 低スコアパス ({score}pt)")
            continue

        # d) Still-listed check: URL not found in any raw file
        if url and raw_urls and url not in raw_urls:
            existing_notes = inq.get("notes") or ""
            if "⚠️ 掲載未確認" not in existing_notes:
                inq["notes"] = (existing_notes + "\n⚠️ 掲載未確認").strip()
            inq["updated"] = str(today)
            unconfirmed += 1
            changed = True

    if changed:
        save_inquiries(inquiries)

    total = delisted + aged_out + no_reply + low_score
    print(f"[lifecycle] sweep: {delisted}件 掲載終了, {aged_out}件 期限切れ, {no_reply}件 未返信, {low_score}件 低スコア, {sublease_count}件 サブリース, {unconfirmed}件 掲載未確認")
    return {"delisted": delisted, "aged_out": aged_out, "no_reply": no_reply, "low_score": low_score, "sublease": sublease_count, "unconfirmed": unconfirmed}


def track_price_changes() -> list[dict]:
    """Parse raw files and detect price changes vs inquiries.yaml."""
    import re

    def _parse_price_man(price_text: str) -> int:
        """Parse price string to 万円 int. Handles '4190万円', '1億9760万円'."""
        if not price_text:
            return 0
        price_text = price_text.strip()
        # Handle 億 + 万 pattern: e.g. "1億9760万円"
        m = re.match(r"(\d+)億(\d+)万", price_text)
        if m:
            return int(m.group(1)) * 10000 + int(m.group(2))
        # Handle 億 only: e.g. "1億円"
        m = re.match(r"(\d+)億", price_text)
        if m:
            return int(m.group(1)) * 10000
        # Handle 万 only: e.g. "4190万円"
        m = re.match(r"(\d+(?:\.\d+)?)万", price_text)
        if m:
            return int(float(m.group(1)))
        # Plain number
        m = re.match(r"(\d+)", price_text)
        if m:
            return int(m.group(1))
        return 0

    # Build {url: price_text} from all raw files
    url_price_map: dict[str, str] = {}
    for raw_file in DATA.glob("*_raw.txt"):
        is_ittomono = "ittomono" in raw_file.name
        try:
            with open(raw_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) < 3:
                        continue
                    url = parts[-1].strip()
                    if not url.startswith("http"):
                        continue
                    # ittomono has score prefix at index 0, price at index 3
                    price_idx = 3 if is_ittomono else 2
                    if len(parts) > price_idx:
                        url_price_map[url] = parts[price_idx].strip()
        except Exception:
            pass

    inquiries = load_inquiries()
    today = date.today()
    changes: list[dict] = []
    modified = False

    for inq in inquiries:
        url = inq.get("url", "")
        if not url or url not in url_price_map:
            continue

        raw_price_text = url_price_map[url]
        new_price = _parse_price_man(raw_price_text)
        old_price = inq.get("price")

        if not isinstance(old_price, (int, float)) or old_price <= 0:
            continue
        if new_price <= 0:
            continue
        if new_price == int(old_price):
            continue

        # Price changed
        old_price_int = int(old_price)
        pct = (new_price - old_price_int) / old_price_int * 100

        note_part = f"価格変動: {old_price_int}万→{new_price}万 ({today})"
        if pct <= -10:
            note_part = "🔥値下げ " + note_part

        existing_notes = inq.get("notes") or ""
        inq["notes"] = (existing_notes + "\n" + note_part).strip()
        inq["price"] = new_price
        inq["updated"] = str(today)
        modified = True

        changes.append({
            "id": inq["id"],
            "name": inq.get("name", ""),
            "old_price": old_price_int,
            "new_price": new_price,
            "pct": round(pct, 1),
        })
        print(f"[lifecycle] 価格変動: {inq['id']} {inq.get('name', '')} {old_price_int}万→{new_price}万 ({pct:+.1f}%)")

    if modified:
        save_inquiries(inquiries)

    drop_count = sum(1 for c in changes if c["pct"] <= -10)
    print(f"[lifecycle] 価格変動: {len(changes)}件 (値下げ{drop_count}件)")
    return changes


def lifecycle() -> dict:
    """Run full lifecycle management: sweep stale + price tracking + sync."""
    print("=== Pipeline Lifecycle ===")
    sweep_result = sweep_stale()
    price_changes = track_price_changes()
    sync_count = sync_from_agent_memory()

    result = {
        "sweep": sweep_result,
        "price_changes": len(price_changes),
        "sync_updates": sync_count,
    }

    if sweep_result["delisted"] + sweep_result["aged_out"] + len(price_changes) + sync_count > 0:
        save_inquiries(load_inquiries())  # Already saved by individual functions
        print(f"[lifecycle] 完了: sweep={sweep_result}, 価格変動={len(price_changes)}件, sync={sync_count}件")
    else:
        print("[lifecycle] 変更なし")

    return result


# ---------------------------------------------------------------------------
# Extract structured data from email reply (Claude API)
# ---------------------------------------------------------------------------


def extract_from_email(inquiry_id: str, email_body: str) -> dict:
    """Use Claude to extract property data from agent's reply email."""
    try:
        import anthropic
    except ImportError:
        print("[pipeline] anthropic not installed")
        return {}

    client = anthropic.Anthropic()
    prompt = f"""以下の不動産業者からのメール本文から、物件情報を構造化データとして抽出してください。

メール本文:
---
{email_body[:3000]}
---

以下のJSON形式で返答。不明な項目はnullに:
{{
  "pet_allowed": true/false/null,
  "short_term_allowed": true/false/null,
  "management_fee": null,
  "repair_reserve": null,
  "floor": null,
  "direction": null,
  "agent_name": null,
  "agent_phone": null,
  "viewing_available": true/false/null,
  "viewing_date_suggested": null,
  "additional_info": null,
  "hard_filter_result": "pass"/"fail"/"pending"
}}

hard_filter_result判定:
- "pass": ペット可 AND 短期賃貸可 が確認済み
- "fail": ペット不可 OR 短期賃貸不可 が明記
- "pending": どちらか未確認

JSONのみ返答。"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        print("[pipeline] Failed to parse extraction result")
        return {}

    extracted = json.loads(text[start:end])

    # Update inquiry record
    inquiries = load_inquiries()
    for inq in inquiries:
        if inq["id"] != inquiry_id:
            continue

        # Map extracted fields
        if extracted.get("pet_allowed") is not None:
            inq["pet"] = "ok" if extracted["pet_allowed"] else "ng"
        if extracted.get("short_term_allowed") is not None:
            inq["short_term"] = "ok" if extracted["short_term_allowed"] else "ng"
        if extracted.get("management_fee"):
            inq["management_fee"] = extracted["management_fee"]
        if extracted.get("agent_name"):
            inq["agent"] = extracted["agent_name"]

        # Status transition based on hard filter
        hf = extracted.get("hard_filter_result")
        if hf == "fail":
            inq["status"] = "passed"
            inq["decision"] = "pass"
            inq["notes"] = f"ハードフィルター不合格: {extracted.get('additional_info', '')}"
        elif hf == "pass" and inq["status"] in ("inquired", "flagged"):
            inq["status"] = "in_discussion"
        elif inq["status"] == "inquired":
            inq["status"] = "in_discussion"

        inq["updated"] = str(date.today())
        break

    save_inquiries(inquiries)
    return extracted


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def update_status(inquiry_id: str, new_status: str, **kwargs) -> None:
    inquiries = load_inquiries()
    found = False
    for inq in inquiries:
        if inq["id"] != inquiry_id:
            continue
        inq["status"] = new_status
        inq["updated"] = str(date.today())
        for key, val in kwargs.items():
            inq[key] = val
        found = True
        break

    if not found:
        print(f"[pipeline] {inquiry_id} not found")
        return

    save_inquiries(inquiries)
    print(f"[pipeline] {inquiry_id} → {STATUS_LABELS.get(new_status, new_status)}")


def schedule_viewing(inquiry_id: str, viewing_date: str) -> None:
    """Schedule a viewing and auto-create action item."""
    update_status(inquiry_id, "viewing", viewing_date=viewing_date)
    _create_action_item(inquiry_id, viewing_date)


def _create_action_item(inquiry_id: str, viewing_date: str) -> None:
    """Create action item in kaizen-agent for the viewing."""
    inquiries = load_inquiries()
    inq = next((i for i in inquiries if i["id"] == inquiry_id), None)
    if not inq:
        return

    venv = BASE.parent / "stock-analyzer" / ".venv" / "bin" / "python3"
    tracker = BASE.parent / "kaizen-agent" / "src" / "action_tracker.py"

    if not venv.exists() or not tracker.exists():
        print("[pipeline] action_tracker not available, skipping")
        return

    action_id = f"naiken-{inquiry_id.replace('inq-', '')}"
    title = f"内見: {inq['name']} ({CITY_LABELS.get(inq.get('city', ''), inq.get('city', ''))})"
    price = f"{inq.get('price', '?'):,}" if isinstance(inq.get("price"), (int, float)) else "?"

    cmd = [
        str(venv), str(tracker), "--add",
        f"id={action_id}",
        f"title={title}",
        "project=property-analyzer",
        "priority=high",
        f"deadline={viewing_date}",
        f"impact=内見予定。{price}万円 / {inq.get('area', '?')}㎡ / {inq.get('layout', '?')}",
        f"context=URL: {inq['url']}",
        "domain=personal",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"[pipeline] Action item {action_id} created")
        else:
            print(f"[pipeline] Action item failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"[pipeline] Action item creation failed: {e}")


# ---------------------------------------------------------------------------
# Dashboard generation
# ---------------------------------------------------------------------------


def _render_card_analysis(inq: dict) -> str:
    """Render inline investment analysis for a pipeline card (collapsible)."""
    price_val = inq.get("price", 0)
    area_val = inq.get("area", 0)
    yr = inq.get("year_built", 0)
    mgmt = inq.get("management_fee", 0)
    city = inq.get("city", "")

    if not price_val or not area_val:
        return ""

    # Estimate rent
    rent_override = inq.get("rent_estimate")
    if rent_override:
        rent_lo = int(rent_override)
        rent_hi = int(rent_override) + 1
    else:
        rent_per_sqm = {"fukuoka": (1800, 2200), "osaka": (2000, 2500), "tokyo": (2500, 3200)}
        lo, hi = rent_per_sqm.get(city, (2000, 2500))
        if yr and yr >= 2010:
            lo, hi = int(lo * 1.1), int(hi * 1.1)
        rent_lo = int(area_val * lo / 10000) if area_val else 0
        rent_hi = int(area_val * hi / 10000) if area_val else 0

    if not rent_lo:
        return ""

    rent_mid = (rent_lo + rent_hi) / 2
    yield_mid = round(rent_mid * 12 / price_val * 100, 2) if price_val else 0
    yield_lo = round(rent_lo * 12 / price_val * 100, 1) if price_val else 0
    yield_hi = round(rent_hi * 12 / price_val * 100, 1) if price_val else 0

    if yield_mid <= 0:
        return ""

    # Run revenue_calc
    inq_loan_amount = inq.get("loan_amount")
    inq_loan_years = inq.get("loan_years")
    if inq_loan_amount and price_val:
        dr = (price_val - inq_loan_amount) / price_val
    else:
        dr = 0.20
    params = InvestmentParams(
        building_ratio=0.50,
        down_payment_ratio=dr,
        loan_years=int(inq_loan_years) if inq_loan_years else 0,
    )
    rev = revenue_analyze(
        price_man=price_val,
        yield_pct=yield_mid,
        structure="RC造",
        built_year=yr if yr else None,
        maintenance_fee_monthly=mgmt if mgmt else 0,
        params=params,
    )
    if rev.verdict == "データ不足":
        return ""

    mcf = rev.monthly_cf
    cf_color = "#22c55e" if mcf > 3 else "#facc15" if mcf > 0 else "#f87171"
    cf_sign = "+" if mcf >= 0 else ""

    payback = f"{rev.payback_years:.1f}年" if rev.payback_years != float("inf") else "∞"
    tax_line = ""
    if rev.tax_benefit > 0:
        tax_line = f'<div style="display:flex;justify-content:space-between"><span>節税効果</span><span style="color:var(--green)">+{rev.tax_benefit:,.0f}万/年</span></div>'

    vclass_map = {"高CF物件": "#22c55e", "安定CF": "#34d399", "薄利": "#facc15", "CF赤字": "#f87171"}
    v_color = vclass_map.get(rev.verdict, "#71717a")

    # Waterfall breakdown lines
    vacancy_pct = int(params.vacancy_rate * 100)
    mgmt_fee_monthly = inq.get("management_fee", 0) or 0
    mgmt_detail = inq.get("management_fee_detail", "")
    mgmt_detail_str = f"（{mgmt_detail}）" if mgmt_detail else ""

    wf_mgmt = ""
    if mgmt_fee_monthly > 0:
        mgmt_annual_man = mgmt_fee_monthly * 12 / 10000
        wf_mgmt = f'<div style="display:flex;justify-content:space-between;color:#a1a1aa"><span>　管理費・修繕</span><span>-{mgmt_annual_man:.1f}万/年{mgmt_detail_str}</span></div>'
    residual_line = ""
    if mgmt_fee_monthly > 0 and rev.opex > 0:
        mgmt_annual_man = mgmt_fee_monthly * 12 / 10000
        residual = rev.opex - mgmt_annual_man
        if residual > 0:
            residual_line = f'<div style="display:flex;justify-content:space-between;color:#a1a1aa"><span>　その他経費</span><span>-{residual:.1f}万/年</span></div>'
    elif rev.opex > 0:
        wf_mgmt = f'<div style="display:flex;justify-content:space-between;color:#a1a1aa"><span>　経費（{int(params.opex_rate*100)}%）</span><span>-{rev.opex:,.0f}万/年</span></div>'

    return f'''<details class="card-analysis" onclick="event.stopPropagation()">
  <summary style="font-size:11px;color:#71717a;cursor:pointer;padding:4px 0">▸ 投資分析</summary>
  <div style="font-size:11px;padding:6px 0;border-top:1px solid #27272a;margin-top:4px;display:flex;flex-direction:column;gap:3px">
    <div style="display:flex;justify-content:space-between"><span>想定賃料</span><span>{rent_lo}〜{rent_hi}万/月（年{rev.gross_income:,.0f}万）</span></div>
    <div style="display:flex;justify-content:space-between;color:#a1a1aa"><span>　空室控除（{vacancy_pct}%）</span><span>-{rev.vacancy_loss:,.0f}万/年</span></div>
    {wf_mgmt}
    {residual_line}
    <div style="display:flex;justify-content:space-between;border-top:1px solid #333;padding-top:2px"><span>NOI（営業利益）</span><span>{rev.noi:,.0f}万/年</span></div>
    <div style="display:flex;justify-content:space-between"><span>ローン返済</span><span>-{rev.annual_debt_service:,.0f}万/年（月{rev.annual_debt_service / 12:.1f}万 × {rev.loan_years}年）</span></div>
    <div style="display:flex;justify-content:space-between;font-weight:600;border-top:1px solid #333;padding-top:2px"><span>月間CF</span><span style="color:{cf_color}">{cf_sign}{mcf:.1f}万/月</span></div>
    {tax_line}
    <div style="display:flex;justify-content:space-between"><span>表面利回り</span><span>{yield_lo}〜{yield_hi}%</span></div>
    <div style="display:flex;justify-content:space-between"><span>CCR（自己資本利回り）</span><span>{rev.ccr_pct:.1f}%</span></div>
    <div style="display:flex;justify-content:space-between"><span>回収</span><span>{payback}</span></div>
    <div style="display:flex;justify-content:space-between"><span>判定</span><span style="color:{v_color};font-weight:600">{rev.verdict}</span></div>
    <div style="border-top:1px solid #333;padding-top:3px;margin-top:2px">
      <div style="display:flex;justify-content:space-between"><span>頭金</span><span>{rev.down_payment:,.0f}万（{params.down_payment_ratio*100:.0f}%）</span></div>
      <div style="display:flex;justify-content:space-between;color:#a1a1aa"><span>　諸費用（{params.acquisition_cost_rate*100:.0f}%）</span><span>{rev.acquisition_cost:,.0f}万</span></div>
      <div style="display:flex;justify-content:space-between;font-weight:600"><span>初期必要資金</span><span>{rev.total_equity:,.0f}万</span></div>
    </div>
    <div style="color:#52525b;font-size:10px;margin-top:2px">金利{params.loan_rate_annual*100:.2f}% / 空室{vacancy_pct}%</div>
  </div>
</details>'''


def _render_card(inq: dict) -> str:
    """Render a single inquiry card."""
    status = inq.get("status", "unknown")
    color = STATUS_COLORS.get(status, "#71717a")
    label = STATUS_LABELS.get(status, status)
    pet_icon = {"ok": "✅", "ng": "❌", "可": "✅", "相談可": "🔶"}.get(
        str(inq.get("pet", "")), "⏳"
    )
    st_icon = {"ok": "✅", "ng": "❌"}.get(str(inq.get("short_term", "")), "⏳")
    price = f"{inq['price']:,}万" if isinstance(inq.get("price"), (int, float)) else "?"
    area_val = inq.get("area")
    area = f"{area_val}㎡" if area_val else "?"
    viewing_line = ""
    if inq.get("viewing_date"):
        viewing_line = f'<div style="color:#a78bfa;font-size:12px;margin-top:6px">内見: {inq["viewing_date"]}</div>'
    notes_line = ""
    if inq.get("notes"):
        notes_line = f'<div style="color:#a1a1aa;font-size:11px;margin-top:4px;font-style:italic">{inq["notes"]}</div>'
    dimmed = ' style="opacity:0.4"' if status == "passed" else ""

    # Waiting badge for inquired properties
    waiting_badge = ""
    if status == "inquired":
        inquired_str = inq.get("inquired_date", inq.get("updated", ""))
        if inquired_str:
            try:
                days_w = (date.today() - date.fromisoformat(str(inquired_str))).days
                if days_w >= 7:
                    waiting_badge = f'<span style="background:#f97316;color:#fff;padding:1px 6px;border-radius:8px;font-size:10px;font-weight:600">未返信 {days_w}日</span>'
                else:
                    waiting_badge = f'<span style="background:var(--blue);color:#fff;padding:1px 6px;border-radius:8px;font-size:10px">送信 {days_w}日前</span>'
            except (ValueError, TypeError):
                pass

    # Stale badge for in_discussion
    stale_badge = ""
    if status == "in_discussion":
        updated_str = inq.get("updated", "")
        if updated_str:
            try:
                days_stale = (date.today() - date.fromisoformat(str(updated_str))).days
                if days_stale >= 7:
                    stale_badge = f'<span style="background:#71717a;color:#fff;padding:1px 6px;border-radius:8px;font-size:10px">動きなし {days_stale}日</span>'
            except (ValueError, TypeError):
                pass

    # Investment analysis (collapsible)
    analysis_html = _render_card_analysis(inq)

    return f'''<div class="inq-card"{dimmed}>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <a href="{inq.get('url', '#')}" target="_blank" rel="noopener" class="card-name" style="text-decoration:none;color:inherit">{inq.get('name', '?')} ↗</a>
    <div style="display:flex;gap:6px;align-items:center">
      {waiting_badge}{stale_badge}
      <span class="status-pill" style="background:{color}">{label}</span>
      <span class="card-score">{inq.get('score', '?')}pt</span>
    </div>
  </div>
  <div class="card-detail">{price} / {area} / 築{2026 - int(inq['year_built']) if inq.get('year_built') else '?'}年（融資{min(35, max(15, 60 - (2026 - int(inq['year_built'])))) if inq.get('year_built') else '?'}年） / {_clean_station(inq.get('station', '?'))}</div>
  <div class="card-filters">
    <span>ペット {pet_icon}</span>
    <span>短期賃貸 {st_icon}</span>
    {f'<span>担当: {inq["agent"]}</span>' if inq.get('agent') else ''}
  </div>
  {viewing_line}{notes_line}
  <div class="card-meta">{inq.get('source', '')} / {inq.get('id', '')}</div>
  {analysis_html}
</div>'''


def _load_agent_memory() -> dict:
    """inbox-zero/data/agent_memory.yaml を読み込み。

    Local path first (works on dev machine), then GitHub API fallback (GHA).
    """
    # 1) Local path (sibling directory)
    mem_path = BASE.parent / "inbox-zero" / "data" / "agent_memory.yaml"
    if mem_path.exists():
        with open(mem_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("agents", {})

    # 2) GitHub API fallback (for GHA — inbox-zero is a separate private repo)
    token = os.environ.get("GH_PAT", "")
    if not token:
        print("[pipeline] agent_memory: local path not found and GH_PAT not set — skipping")
        return {}
    api_url = "https://api.github.com/repos/ymatz28-beep/inbox-zero/contents/data/agent_memory.yaml"
    req = Request(api_url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read())
        content = base64.b64decode(payload["content"]).decode("utf-8")
        data = yaml.safe_load(content) or {}
        print("[pipeline] agent_memory: fetched from GitHub API")
        return data.get("agents", {})
    except Exception as e:
        print(f"[pipeline] agent_memory: GitHub API fetch failed — {e}")
        return {}


def _build_viewing_schedule(inquiries: list[dict], agent_memory: dict) -> str:
    """内覧スケジュールセクションのHTML生成。upcoming + 進行中案件を一覧化。"""
    # agent_memory を名前でも引けるように逆引きmap作成
    agent_by_name: dict[str, dict] = {}
    for email, mem in agent_memory.items():
        name = mem.get("name", "")
        agent_by_name[name] = {**mem, "email": email}

    # 進行中（viewing, in_discussion, inquired）を抽出
    active = [
        i for i in inquiries
        if i.get("status") in ("viewing", "in_discussion", "inquired")
    ]
    if not active:
        return ""

    # viewing が先、次に in_discussion、最後に inquired
    status_order = {"viewing": 0, "in_discussion": 1, "inquired": 2}
    active.sort(key=lambda x: (status_order.get(x.get("status", ""), 9), x.get("viewing_date") or "9999"))

    cards = []
    for inq in active:
        status = inq.get("status", "")
        color = STATUS_COLORS.get(status, "#71717a")
        label = STATUS_LABELS.get(status, status)
        city = CITY_LABELS.get(inq.get("city", ""), "")

        # Agent info from agent_memory
        agent_name = inq.get("agent", "")
        agent_info = agent_by_name.get(agent_name, {})
        agent_company = agent_info.get("company", "")
        agent_phone = ""
        agent_email = agent_info.get("email", "")

        # 担当者連絡先行
        agent_title = agent_info.get("title", "")
        agent_line = ""
        if agent_name:
            parts = [f"<strong>{agent_name}</strong>"]
            if agent_title:
                parts.append(f"<span class='agent-title'>{agent_title}</span>")
            if agent_company:
                parts.append(f"（{agent_company}）")
            agent_line = f'<div class="sched-agent">👤 {"".join(parts)}</div>'
            contact_parts = []
            if agent_email:
                contact_parts.append(agent_email)
            if agent_phone:
                contact_parts.append(agent_phone)
            if contact_parts:
                agent_line += f'<div class="sched-contact">{" / ".join(contact_parts)}</div>'

        # 内覧日時
        date_line = ""
        if inq.get("viewing_date"):
            vd = inq["viewing_date"]
            vt = inq.get("viewing_time", "")
            loc = inq.get("viewing_location", "")
            time_str = f" {vt}" if vt else ""
            date_line = f'<div class="sched-date">📅 {vd}{time_str}</div>'
            if loc:
                date_line += f'<div class="sched-loc">📍 {loc}</div>'
        elif status == "in_discussion":
            date_line = '<div class="sched-date" style="color:#f59e0b">⏳ 日程調整中</div>'
        elif status == "inquired":
            date_line = '<div class="sched-date" style="color:#71717a">📨 返信待ち</div>'

        # ハードフィルター状態
        pet_icon = {"ok": "✅", "ng": "❌", "可": "✅", "相談可": "🔶"}.get(
            str(inq.get("pet", "")), "⏳"
        )
        st_val = inq.get("short_term")
        if st_val is True or st_val == "ok":
            st_icon = "✅"
        elif st_val is False or st_val == "ng":
            st_icon = "❌"
        elif st_val and st_val != "null":
            st_icon = "🔶"
        else:
            st_icon = "⏳"

        notes = inq.get("notes", "")
        notes_line = f'<div class="sched-notes">{notes}</div>' if notes else ""

        cards.append(f'''<div class="sched-card" style="border-left:3px solid {color}">
  <div class="sched-header">
    <a href="{inq.get('url', '#')}" target="_blank" rel="noopener" class="sched-name" style="text-decoration:none;color:inherit">{inq.get("name", "?")} ↗</a>
    <div style="display:flex;gap:6px;align-items:center">
      <span class="status-pill" style="background:{color}">{label}</span>
      <span class="sched-city">{city}</span>
    </div>
  </div>
  {date_line}
  {agent_line}
  <div class="sched-filters">ペット {pet_icon}　短期賃貸 {st_icon}</div>
  {notes_line}
</div>''')

    count_viewing = sum(1 for i in active if i.get("status") == "viewing")
    count_discussion = sum(1 for i in active if i.get("status") == "in_discussion")
    count_inquired = sum(1 for i in active if i.get("status") == "inquired")

    return f'''
<div class="schedule-section">
  <div class="schedule-header">
    <h2>内覧スケジュール / 進行中</h2>
    <div class="schedule-counts">
      {f'<span style="color:#a78bfa">内見 {count_viewing}</span>' if count_viewing else ''}
      {f'<span style="color:#f97316">やり取り中 {count_discussion}</span>' if count_discussion else ''}
      {f'<span style="color:#f59e0b">問い合わせ済 {count_inquired}</span>' if count_inquired else ''}
    </div>
  </div>
  <div class="schedule-cards">
    {"".join(cards)}
  </div>
</div>'''


def _naiken_invest_analysis(p: dict, all_props: list[dict]) -> str:
    """物件別の投資分析セクション — 収益シミュレーション waterfall 付き。"""
    price = p.get("price", 0)
    area = p.get("area", 0)
    mgmt = p.get("management_fee", 0)
    yr = p.get("year_built", 0)
    city = p.get("city", "")

    # 想定賃料: rent_estimateがあればそれを優先、なければ都市別㎡単価ベース
    rent_override = p.get("rent_estimate")
    if rent_override:
        rent_lo = int(rent_override)
        rent_hi = int(rent_override) + 1
    else:
        rent_per_sqm = {"fukuoka": (1800, 2200), "osaka": (2000, 2500), "tokyo": (2500, 3200)}
        lo, hi = rent_per_sqm.get(city, (2000, 2500))
        if yr and yr >= 2010:
            lo, hi = int(lo * 1.1), int(hi * 1.1)  # 築浅プレミアム
        rent_lo = int(area * lo / 10000) if area else 0
        rent_hi = int(area * hi / 10000) if area else 0

    # 表面利回り (midpoint for simulation)
    yield_lo = round(rent_lo * 12 / price * 100, 1) if price else 0
    yield_hi = round(rent_hi * 12 / price * 100, 1) if price else 0
    yield_cls = "ok" if yield_hi >= 4.0 else ("" if yield_hi >= 3.0 else "warn")
    rent_mid = (rent_lo + rent_hi) / 2
    yield_mid = round(rent_mid * 12 / price * 100, 2) if price else 0

    # ㎡単価の相対評価
    sqm_prices = [pp["price"] / pp["area"] for pp in all_props if pp.get("price") and pp.get("area")]
    my_sqm = price / area if price and area else 0
    sqm_rank = "割安" if my_sqm <= min(sqm_prices) * 1.05 else ("高め" if my_sqm >= max(sqm_prices) * 0.95 else "中間")
    sqm_cls = "ok" if sqm_rank == "割安" else ("warn" if sqm_rank == "高め" else "")

    # 築年数リスク
    age = datetime.now().year - yr if yr else 0
    age_label = "低い" if age < 15 else ("中程度" if age < 30 else "高い（要修繕確認）")
    age_cls = "ok" if age < 15 else ("" if age < 30 else "warn")

    # KPI grid (quick overview)
    grid_html = f"""<div class="section-title">投資分析</div>
<div class="invest-grid">
<div class="invest-card"><div class="label">想定賃料（{CITY_LABELS.get(city, '')} {p.get('layout', '')} {area}㎡）</div><div class="num">{rent_lo}〜{rent_hi}万円/月</div></div>
<div class="invest-card"><div class="label">表面利回り</div><div class="num {yield_cls}">{yield_lo}〜{yield_hi}%</div></div>
<div class="invest-card"><div class="label">㎡単価 vs 他物件</div><div class="num {sqm_cls}">{sqm_rank}</div></div>
<div class="invest-card"><div class="label">築年数リスク</div><div class="num {age_cls}">{age_label}</div></div>
</div>"""

    # Revenue waterfall simulation
    if not price or yield_mid <= 0:
        return grid_html

    # 区分マンション: RC構造を仮定、建物比率50%（区分は土地持分小さい）
    # loan_amount / loan_years が inquiry に設定されていれば頭金比率・期間を導出
    inq_loan_amount = p.get("loan_amount")  # 万円
    inq_loan_years = p.get("loan_years")    # 年
    if inq_loan_amount and price:
        computed_ratio = (price - inq_loan_amount) / price
    else:
        computed_ratio = 0.20  # default 20%
    params = InvestmentParams(
        building_ratio=0.50,
        down_payment_ratio=computed_ratio,
        loan_years=int(inq_loan_years) if inq_loan_years else 0,
    )
    rev = revenue_analyze(
        price_man=price,
        yield_pct=yield_mid,
        structure="RC造",
        built_year=yr if yr else None,
        params=params,
    )

    if rev.verdict == "データ不足":
        return grid_html

    def _f(v: float) -> str:
        if abs(v) >= 10000:
            return f"{v/10000:.2f}億"
        return f"{v:,.0f}万"

    p_rv = rev.params
    vclass = {
        "高CF物件": "rv-high", "安定CF": "rv-stable",
        "薄利": "rv-thin", "CF赤字": "rv-red",
    }.get(rev.verdict, "rv-thin")

    payback = f"{rev.payback_years:.1f}年" if rev.payback_years != float("inf") else "∞"

    mcf = rev.monthly_cf
    cf_color = "#22c55e" if mcf > 30 else "#34d399" if mcf > 15 else "#facc15" if mcf > 0 else "#f87171"
    cf_sign = "+" if rev.annual_cf >= 0 else ""

    building_price = rev.price_man * p_rv.building_ratio

    # Management fee annotation
    mgmt_note = ""
    if mgmt:
        mgmt_man = mgmt / 10000
        cf_after_mgmt = rev.monthly_cf - mgmt_man
        cf_after_color = "#34d399" if cf_after_mgmt > 0 else "#f87171"
        cf_after_sign = "+" if cf_after_mgmt >= 0 else ""
        mgmt_note = f"""<div class="rv-row rv-minus"><span class="rv-desc">管理費・修繕積立金</span><span class="rv-note">{mgmt:,}円/月</span><span class="rv-amount">-{mgmt_man:.1f}万/月</span></div>
        <div class="rv-row rv-highlight"><span class="rv-desc">管理費込み月間CF</span><span class="rv-note"></span><span class="rv-amount" style="color:{cf_after_color}">{cf_after_sign}{cf_after_mgmt:.1f}万/月</span></div>"""

    waterfall_html = f'''<div class="revenue-block">
      <div class="rv-header">
        <span class="rv-title">収益シミュレーション</span>
        <span class="rv-verdict {vclass}">{rev.verdict}</span>
      </div>
      <div class="rv-assumptions">前提: 頭金{p_rv.down_payment_ratio*100:.0f}% / 金利{p_rv.loan_rate_annual*100:.2f}% / {rev.loan_years}年ローン / 空室率{p_rv.vacancy_rate*100:.0f}% / 経費率{p_rv.opex_rate*100:.0f}% / 建物比率{p_rv.building_ratio*100:.0f}%<br>想定賃料: {rent_lo}〜{rent_hi}万/月（中央値{rent_mid:.0f}万 → 利回り{yield_mid:.1f}%で試算）</div>

      <div class="rv-section">
        <div class="rv-section-title">収入 → キャッシュフロー</div>
        <div class="rv-row"><span class="rv-desc">年間賃料収入</span><span class="rv-note">= 想定{rent_mid:.0f}万/月 × 12</span><span class="rv-amount">{_f(rev.gross_income)}</span></div>
        <div class="rv-row rv-minus"><span class="rv-desc">空室損（{p_rv.vacancy_rate*100:.0f}%）</span><span class="rv-note"></span><span class="rv-amount">-{_f(rev.vacancy_loss)}</span></div>
        <div class="rv-row rv-minus"><span class="rv-desc">運営経費（税・保険・修繕等）</span><span class="rv-note">{p_rv.opex_rate*100:.0f}%</span><span class="rv-amount">-{_f(rev.opex)}</span></div>
        <div class="rv-row rv-subtotal"><span class="rv-desc">営業利益（NOI）</span><span class="rv-note"></span><span class="rv-amount">{_f(rev.noi)}</span></div>
        <div class="rv-row rv-minus"><span class="rv-desc">ローン返済</span><span class="rv-note">借入{_f(rev.loan_amount)} / {rev.loan_years}年</span><span class="rv-amount">-{_f(rev.annual_debt_service)}</span></div>
        <div class="rv-row rv-total"><span class="rv-desc">年間キャッシュフロー</span><span class="rv-note"></span><span class="rv-amount" style="color:{cf_color}">{cf_sign}{_f(rev.annual_cf)}</span></div>
        <div class="rv-row rv-highlight"><span class="rv-desc">月間キャッシュフロー</span><span class="rv-note"></span><span class="rv-amount" style="color:{cf_color}">{cf_sign}{rev.monthly_cf:,.1f}万/月</span></div>
        {mgmt_note}
      </div>

      <div class="rv-section">
        <div class="rv-section-title">減価償却 → 節税効果</div>
        <div class="rv-row"><span class="rv-desc">建物価格</span><span class="rv-note">= 取得価格 × 建物比率{p_rv.building_ratio*100:.0f}%</span><span class="rv-amount">{_f(building_price)}</span></div>
        <div class="rv-row"><span class="rv-desc">残存耐用年数</span><span class="rv-note">法定{rev.useful_life}年 − 築{2026 - yr if yr else "?"}年</span><span class="rv-amount">{rev.remaining_life}年</span></div>
        <div class="rv-row rv-subtotal"><span class="rv-desc">年間償却額</span><span class="rv-note">= {_f(building_price)} ÷ {rev.remaining_life}年</span><span class="rv-amount">{_f(rev.depreciation_annual)}</span></div>
        {"<div class='rv-row rv-highlight'><span class='rv-desc'>節税効果（損益通算）</span><span class='rv-note'>帳簿上の赤字 → 他の所得と相殺</span><span class='rv-amount' style=\"color:var(--green)\">+" + f"{rev.tax_benefit:,.0f}" + "万/年</span></div>" if rev.tax_benefit > 0 else "<div class='rv-row'><span class='rv-desc'>税負担</span><span class='rv-note'>課税所得" + f"{rev.taxable_income:,.0f}" + "万 × 税率" + f"{p_rv.tax_rate*100:.0f}" + "%</span><span class='rv-amount'>-" + f"{rev.taxable_income * p_rv.tax_rate:,.0f}" + "万</span></div>"}
      </div>

      <div class="rv-bottom">
        <div class="rv-bottom-item"><span class="rv-bottom-label">税引後CF</span><span class="rv-bottom-val">{"+" if rev.after_tax_cf >= 0 else ""}{_f(rev.after_tax_cf)}/年</span></div>
        <div class="rv-bottom-item"><span class="rv-bottom-label">実質利回り</span><span class="rv-bottom-val">{rev.net_yield_pct:.1f}%</span></div>
        <div class="rv-bottom-item"><span class="rv-bottom-label">自己資金回収</span><span class="rv-bottom-val">{payback}</span></div>
      </div>
    </div>'''

    return grid_html + waterfall_html


def _naiken_merits_risks(p: dict, all_props: list[dict]) -> str:
    """物件別メリット/リスク（属性ベース自動判定）。"""
    merits, risks, checks = [], [], []
    price = p.get("price", 0)
    area = p.get("area", 0)
    yr = p.get("year_built", 0)
    mgmt = p.get("management_fee", 0)
    age = datetime.now().year - yr if yr else 0

    # ㎡単価
    sqm = price / area if price and area else 0
    all_sqm = sorted(pp["price"] / pp["area"] for pp in all_props if pp.get("price") and pp.get("area"))
    if sqm and sqm <= all_sqm[0] * 1.05:
        merits.append(f"㎡単価最安（{sqm:.1f}万）")
    elif sqm and sqm >= all_sqm[-1] * 0.95:
        risks.append(f"㎡単価最高（{sqm:.1f}万）")

    # 面積
    all_areas = sorted(pp.get("area", 0) for pp in all_props)
    if area >= all_areas[-1]:
        merits.append(f"面積最大（{area}㎡）")
    elif area <= all_areas[0]:
        risks.append(f"面積最小（{area}㎡）")

    # ペット
    if p.get("pet") == "ok":
        merits.append("ペット可確定")
    elif p.get("pet") == "ng":
        risks.append("ペット不可")
    else:
        checks.append("ペット可否の確認")

    # 耐震（1981年6月以降 = 新耐震基準）
    if yr and yr < 1981:
        risks.append(f"旧耐震（{yr}年）")
        checks.append("耐震診断の有無")
    elif yr and yr == 1981:
        # 1981年は月で判定（月不明なら保守的に旧耐震）
        built_month = p.get("built_month")
        if built_month and built_month >= 6:
            merits.append(f"新耐震（{yr}年{built_month}月）")
        else:
            risks.append(f"旧耐震（{yr}年・新耐震基準適用か要確認）")
            checks.append("耐震診断の有無")
    elif yr and yr > 1981:
        merits.append(f"新耐震（{yr}年）")

    # 築年数
    if age > 30:
        risks.append(f"築{age}年（大規模修繕リスク）")
        checks.append("大規模修繕の履歴と次回予定")
    elif age < 10:
        merits.append(f"築{age}年（築浅）")

    # 管理費
    all_mgmt = sorted(pp.get("management_fee", 0) for pp in all_props if pp.get("management_fee"))
    if mgmt and all_mgmt and mgmt >= all_mgmt[-1]:
        risks.append(f"管理費最高（{mgmt:,}円）")
    elif mgmt and all_mgmt and mgmt <= all_mgmt[0]:
        merits.append(f"管理費最安（{mgmt:,}円）")

    # 短期賃貸
    st = p.get("short_term")
    if st and "OK" in str(st).upper():
        merits.append("短期賃貸可")
    elif not st:
        checks.append("短期賃貸（マンスリー）可否の確認")

    m = " / ".join(merits) if merits else "—"
    r = " / ".join(risks) if risks else "—"
    c = " / ".join(checks) if checks else "—"
    return f"""<div class="section-title">メリット / リスク</div>
<table><tr><th style="color:var(--green)">メリット</th><td>{m}</td></tr>
<tr><th style="color:var(--red)">リスク</th><td>{r}</td></tr>
<tr><th style="color:var(--yellow)">要確認</th><td>{c}</td></tr></table>"""


def _naiken_checklist(p: dict) -> str:
    """物件別の内覧チェックリスト（属性ベース）。"""
    items = [
        "<strong>ペット飼育条件の詳細（サイズ・頭数制限）</strong>",
        "<strong>短期賃貸（マンスリー）活用の可否</strong>",
        "管理規約で民泊条項の確認",
    ]
    yr = p.get("year_built", 0)
    age = datetime.now().year - yr if yr else 0
    if yr and yr <= 1985:
        items.append("耐震診断の実施有無")
    items.append("大規模修繕の履歴と次回予定")
    items.append("修繕積立金の残高と値上げ予定")
    if age > 20:
        items.append(f"築{age}年 — 水回り・設備の状態（リフォーム要否）")
    items.extend([
        "日当たり・眺望・騒音",
        "管理組合の運営状況（滞納・借入）",
    ])
    li = "\n".join(f"<li>{it}</li>" for it in items)
    return f'<div class="section-title">内覧チェックリスト</div>\n<ul class="checklist">{li}</ul>'


def _naiken_questions(p: dict, agent_name: str) -> str:
    """物件別の質問リスト（担当者向け）。"""
    qs = [
        "管理規約で「住宅宿泊事業（民泊）」に関する規定はありますか？",
        "不在時のマンスリー賃貸（1ヶ月以上の定期賃貸借）は管理規約上可能ですか？",
        "大規模修繕の直近実施時期と次回予定は？",
        "修繕積立金の値上げ予定はありますか？",
    ]
    yr = p.get("year_built", 0)
    if yr and yr <= 1985:
        qs.append(f"{yr}年築は新耐震基準適用ですか？ 耐震診断は実施済みですか？")
    qs.append("管理組合の財務状況（借入金・滞納）は？")
    label = f"（{agent_name}さんに確認）" if agent_name else ""
    items = "\n".join(f'<div class="question"><strong>Q{i+1}.</strong> {q}</div>' for i, q in enumerate(qs))
    return f'<div class="section-title">質問リスト{label}</div>\n{items}'


def generate_naiken_analysis() -> Path | None:
    """Auto-generate naiken-analysis.html from viewing properties.

    Full analysis: schedule, comparison, per-property investment analysis,
    merits/risks, checklists, questions, and common verification items.
    Archives previous version before overwriting.
    """
    from lib.renderer import render

    out = OUTPUT / "naiken-analysis.html"

    # Archive previous version before overwriting
    if out.exists():
        archive_dir = OUTPUT / "archive"
        archive_dir.mkdir(exist_ok=True)
        prev_content = out.read_text(encoding="utf-8")
        # Use modification date for archive filename
        mtime = out.stat().st_mtime
        archive_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        archive_path = archive_dir / f"naiken-{archive_date}.html"
        if not archive_path.exists():
            archive_path.write_text(prev_content, encoding="utf-8")

    inquiries = load_inquiries()
    viewing = [i for i in inquiries if i.get("status") in ("viewing", "viewed")]
    if not viewing:
        html = render("pages/naiken.html", {
            "title_city": "",
            "viewing_count": 0,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "property_sections": [],
            "common_html": "",
            "archive_sections": [],
            "gnav_pages": GNAV_PAGES,
            "gnav_current": "内覧分析",
        }, extra_dirs=[BASE / "lib" / "templates"], scope="public")
        out.write_text(html, encoding="utf-8")
        return out

    # Group by viewing_date
    by_date: dict[str, list[dict]] = {}
    for v in viewing:
        d = v.get("viewing_date", "未定")
        by_date.setdefault(d, []).append(v)

    # Agent contacts from agent_memory
    agent_memory = _load_agent_memory()
    agent_contacts: dict[str, dict] = {}
    for email, ag in agent_memory.items():
        name = ag.get("name", "")
        if name:
            agent_contacts[name] = {
                "company": ag.get("company", ""),
                "phone": ag.get("phone", ""),
                "email": email,
            }

    # Build sections — separate current (most recent date) vs archive (older dates)
    sorted_dates = sorted(by_date.keys(), reverse=True)  # newest first
    latest_date = sorted_dates[0] if sorted_dates else None
    archive_dates = sorted_dates[1:] if len(sorted_dates) > 1 else []

    property_sections = []
    archive_sections = []

    def _build_date_sections(vdate: str, props: list[dict], target: list[str]) -> None:
        """Build HTML sections for a given viewing date and append to target list."""
        cities = set(CITY_LABELS.get(p.get("city", ""), p.get("city", "")) for p in props)
        city_str = "・".join(sorted(cities))

        # Agent info
        agents = set(p.get("agent", "") for p in props if p.get("agent"))
        agent_info_html = ""
        for ag_name in agents:
            info = agent_contacts.get(ag_name, {})
            company = info.get("company", "")
            phone = info.get("phone", "")
            parts = [f"<strong>{ag_name}</strong>"]
            if company:
                parts.append(f"（{company}）")
            if phone:
                parts.append(f"<br>TEL: <span style='font-family:JetBrains Mono,monospace'>{phone}</span>")
            agent_info_html += "担当: " + "".join(parts) + "<br>"

        viewing_time = next((str(p["viewing_time"]) for p in props if p.get("viewing_time")), "")

        # Schedule banner
        schedule = f"""<div class="schedule-banner">
<h2>{vdate} 内覧スケジュール — {city_str} {len(props)}件</h2>
<div class="detail">"""
        if viewing_time:
            schedule += f"<strong>{viewing_time}</strong> 集合<br>"
        for idx, p in enumerate(props, 1):
            schedule += f"{'→ ' if idx > 1 else ''}{idx}. {p['name']}<br>"
        schedule += f"<br>{agent_info_html}</div></div>"
        target.append(schedule)

        # Per-property detailed analysis
        for idx, p in enumerate(props, 1):
            yr = p.get("year_built", "")
            age_str = f"築{datetime.now().year - yr}年" if isinstance(yr, int) and yr else ""
            sqm_price = round(p["price"] / p["area"], 1) if p.get("price") and p.get("area") else ""
            pet_raw = str(p.get("pet", ""))
            if pet_raw == "ok":
                pet_label = "可 ✅"
                pet_cls = "ok"
            elif pet_raw == "ng":
                continue  # ペット不可は掲載しない
            else:
                pet_label = "⚠️ 未確認"
                pet_cls = "warn"
            agent_name = p.get("agent", "")

            # Tags
            tags = [f'<span class="tag tag-blue">{p.get("price", "?")}万円</span>']
            if pet_raw == "ok":
                tags.append('<span class="tag tag-green">ペット可</span>')
            else:
                tags.append('<span class="tag tag-yellow">⚠️ ペット未確認</span>')
            if isinstance(yr, int) and yr < 1981:
                tags.append(f'<span class="tag tag-red">旧耐震({yr})</span>')
            elif isinstance(yr, int) and yr == 1981:
                built_month = p.get("built_month")
                if built_month and built_month >= 6:
                    tags.append(f'<span class="tag tag-green">新耐震({yr})</span>')
                else:
                    tags.append(f'<span class="tag tag-yellow">旧耐震({yr})</span>')
            elif isinstance(yr, int) and yr > 1981:
                tags.append(f'<span class="tag tag-green">新耐震({yr})</span>')
            if p.get("area", 0) >= 60:
                tags.append(f'<span class="tag tag-green">{p["area"]}㎡（広い）</span>')
            tags.append(f'<span class="tag tag-muted">{p.get("source", "")}</span>')
            tags_html = "\n".join(tags)

            # Comparison annotation
            areas = [pp.get("area", 0) for pp in props]
            area_note = "（最大）" if p.get("area") == max(areas) else ("（最小）" if p.get("area") == min(areas) else "")
            sqm_prices_all = [pp["price"] / pp["area"] for pp in props if pp.get("price") and pp.get("area")]
            sqm_note = ""
            sqm_cls = ""
            if sqm_price:
                if sqm_price <= min(sqm_prices_all) * 1.05:
                    sqm_note = "（最安）"
                    sqm_cls = "ok"
                elif sqm_price >= max(sqm_prices_all) * 0.95:
                    sqm_note = "（最高）"

            section = f"""<div class="property">
<h2>{idx}. {p['name']}</h2>
<p class="sub">{CITY_LABELS.get(p.get('city', ''), '')} / {p.get('layout', '')} / {p.get('area', '?')}㎡ / {yr}年 / {_clean_station(p.get('station', ''))}</p>
<div>{tags_html}</div>
<div class="section-title">物件概要</div>
<table>
<tr><th>価格</th><td class="val">{p.get('price', '?')}万円</td></tr>
<tr><th>面積</th><td>{p.get('area', '?')}㎡{area_note}</td></tr>
<tr><th>間取り</th><td>{p.get('layout', '?')}</td></tr>
<tr><th>築年</th><td>{yr}年{'（' + age_str + '）' if age_str else ''}</td></tr>
<tr><th>最寄駅</th><td>{_clean_station(p.get('station', '?'))}</td></tr>
<tr><th>管理費</th><td>{f'{p["management_fee"]:,}円/月' if p.get('management_fee') else '?'}</td></tr>
<tr><th>㎡単価</th><td class="mono {sqm_cls}">{f'{sqm_price}万円/㎡{sqm_note}' if sqm_price else '?'}</td></tr>
<tr><th>ペット</th><td class="{pet_cls}">{pet_label}</td></tr>
<tr><th>短期賃貸</th><td>{p.get('short_term') or '<span class="neutral">未確認</span>'}</td></tr>
<tr><th>ソース</th><td><a href="{p.get('url', '#')}" target="_blank">{p.get('source', '?')}</a></td></tr>
</table>
<details class="collapsible-section"><summary class="collapsible-trigger">収益分析 ▸</summary>
{_naiken_invest_analysis(p, props)}
</details>
{_naiken_merits_risks(p, props)}
{_naiken_checklist(p)}
{_naiken_questions(p, agent_name)}
</div>"""
            target.append(section)

    # Build current (latest date) sections
    if latest_date:
        _build_date_sections(latest_date, by_date[latest_date], property_sections)

    # Build archive sections (older dates)
    for adate in sorted(archive_dates, reverse=True):
        _build_date_sections(adate, by_date[adate], archive_sections)

    # Common verification items
    common = """<div class="property">
<h2>共通確認事項（全物件）</h2>
<div class="section-title">ハードフィルター（必須確認）</div>
<ul class="checklist">
<li><strong>ペット飼育（チワワ3kg）: 可否 + 具体的条件</strong></li>
<li><strong>短期賃貸: マンスリー（1ヶ月以上の定期賃貸借）活用の可否</strong></li>
</ul>
<div class="verdict verdict-caution">
<strong>判定基準:</strong><br>
・ペット不可 → 即辞退<br>
・マンスリー不可 → NG<br>
・「民泊禁止」のみ → マンスリー可否を別途確認（マンスリーOKなら問題なし）
</div>
<div class="section-title">投資判断チェック</div>
<ul class="checklist">
<li>法人（iUMAプロパティマネジメント）購入の可否・融資条件</li>
<li>特区民泊の申請可否（期限: 2026/5/29）</li>
<li>値引き余地の確認</li>
<li>引渡し時期の確認</li>
<li>仲介手数料の確認（両手か片手か）</li>
</ul>
<div class="section-title">2拠点生活の実用性</div>
<ul class="checklist">
<li>空港アクセス（空港→物件）の所要時間</li>
<li>スーパー・コンビニの近さ</li>
<li>チワワの散歩ルート（公園・緑道）</li>
<li>インターネット回線（光回線の導入状況）</li>
</ul>
</div>"""

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    latest_props = by_date[latest_date] if latest_date else list(by_date.values())[0]
    latest_cities = set(CITY_LABELS.get(p.get("city", ""), "") for p in latest_props)
    title_city = "・".join(sorted(c for c in latest_cities if c))

    html = render("pages/naiken.html", {
        "title_city": title_city,
        "viewing_count": len(viewing),
        "generated_at": now_str,
        "property_sections": property_sections,
        "common_html": common,
        "archive_sections": archive_sections,
        "gnav_pages": GNAV_PAGES,
        "gnav_current": "内覧分析",
    }, extra_dirs=[BASE / "lib" / "templates"], scope="public")

    out.write_text(html, encoding="utf-8")
    return out


def generate_dashboard() -> Path:
    all_inquiries = load_inquiries()
    agent_memory = _load_agent_memory()

    passed_items = [i for i in all_inquiries if i.get("status") == "passed"]

    # Stats
    by_status: dict[str, int] = {}
    for inq in all_inquiries:
        s = inq.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    # Stage tab definitions
    STAGE_TABS = [
        ("active",     "進行中", "#f59e0b", ("inquired", "in_discussion")),
        ("viewing",    "内見",   "#a78bfa", ("viewing",)),
        ("appraisal",  "査定中", "#6366f1", ("viewed",)),
        ("done",       "完了",   "#22c55e", ("decided",)),
        ("candidates", "候補",   "#71717a", ("flagged",)),
    ]

    # Group inquiries by stage
    stage_items: dict[str, list] = {key: [] for key, *_ in STAGE_TABS}
    for inq in all_inquiries:
        status = inq.get("status", "")
        for key, _label, _color, statuses in STAGE_TABS:
            if status in statuses:
                stage_items[key].append(inq)
                break

    # Sort each stage by score descending
    for key in stage_items:
        stage_items[key].sort(key=lambda x: -(x.get("score") or 0))

    # needs_action: active items not updated in 3+ days
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    active_statuses_set = {"inquired", "in_discussion"}
    needs_action_count = 0
    for inq in all_inquiries:
        if inq.get("status") not in active_statuses_set:
            continue
        updated_raw = inq.get("updated_at") or inq.get("created_at") or ""
        if not updated_raw:
            needs_action_count += 1
            continue
        try:
            updated_dt = datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
            if updated_dt.tzinfo is None:
                updated_dt = updated_dt.replace(tzinfo=timezone.utc)
            if (now - updated_dt).days >= 3:
                needs_action_count += 1
        except (ValueError, TypeError):
            needs_action_count += 1

    # Build stage tabs nav
    first_nonempty = next((key for key, *_ in STAGE_TABS if stage_items[key]), None)
    tab_html_parts = []
    for key, label, color, _ in STAGE_TABS:
        cnt = len(stage_items[key])
        is_active = key == first_nonempty
        active_cls = " active" if is_active else ""
        tab_html_parts.append(
            f'<a class="stage-tab{active_cls}" data-stage="{key}" '
            f'style="--tab-color:{color}" onclick="showStage(\'{key}\')">'
            f'{label} <span class="tab-count">{cnt}</span></a>'
        )
    section_nav = (
        '<div class="section-nav"><div class="section-nav-inner">'
        + "".join(tab_html_parts)
        + "</div></div>"
    )

    # Build stage sections
    stage_sections = []
    for idx, (key, label, color, _) in enumerate(STAGE_TABS):
        items = stage_items[key]
        is_active = key == first_nonempty
        hidden_cls = "" if is_active else " hidden"

        if key == "candidates":
            # Top 15 visible, rest in details
            top = items[:15]
            rest = items[15:]
            cards_html = "\n".join(_render_card(inq) for inq in top)
            if rest:
                rest_cards = "\n".join(_render_card(inq) for inq in rest)
                cards_html += f'''
  <details style="margin-top:12px">
    <summary style="color:#71717a;cursor:pointer;font-size:13px;padding:8px 0">
      他 {len(rest)}件（クリックで展開）
    </summary>
    <div class="stage-cards" style="margin-top:8px">{rest_cards}</div>
  </details>'''
        else:
            cards_html = "\n".join(_render_card(inq) for inq in items)

        stage_sections.append(f'''
<div class="stage-section{hidden_cls}" data-stage="{key}">
  <div class="stage-header" style="border-left:3px solid {color}">
    <h2>{label}</h2>
    <div class="stage-stats"><span>{len(items)}件</span></div>
  </div>
  <div class="stage-cards">{cards_html}</div>
</div>''')

    # Passed section (top 10 by recency)
    passed_sorted = sorted(
        passed_items,
        key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""),
        reverse=True,
    )
    top_passed = passed_sorted[:10]
    passed_cards_html = "\n".join(_render_card(inq) for inq in top_passed)
    passed_html = f'''
<details style="margin-top:32px">
  <summary style="color:#71717a;cursor:pointer;font-size:13px;padding:8px 0">
    見送り {len(passed_items)}件（クリックで展開）
  </summary>
  <div class="stage-cards" style="margin-top:8px">{passed_cards_html}</div>
</details>''' if passed_items else ""

    # --- Template rendering ---
    from lib.renderer import render

    stats = {
        "active":       by_status.get("inquired", 0) + by_status.get("in_discussion", 0),
        "viewing":      by_status.get("viewing", 0),
        "appraisal":    by_status.get("viewed", 0),
        "done":         by_status.get("decided", 0),
        "candidates":   by_status.get("flagged", 0),
        "passed":       by_status.get("passed", 0),
        "needs_action": needs_action_count,
    }

    # schedule: active + viewing + appraisal items
    schedule_statuses = {"inquired", "in_discussion", "viewing", "viewed"}
    schedule_items = [i for i in all_inquiries if i.get("status") in schedule_statuses]
    schedule_html = _build_viewing_schedule(schedule_items, agent_memory)

    html = render("pages/pipeline.html", {
        "stats": stats,
        "schedule_html": schedule_html,
        "section_nav": section_nav,
        "stage_sections": stage_sections,
        "passed_html": passed_html,
        "gnav_pages": GNAV_PAGES,
        "gnav_current": "Pipeline",
    }, extra_dirs=[BASE / "lib" / "templates"], scope="public")

    out = OUTPUT / "inquiry-pipeline.html"
    out.write_text(html, encoding="utf-8")
    print(f"[pipeline] Dashboard → {out}")
    return out


# ---------------------------------------------------------------------------
# CLI display
# ---------------------------------------------------------------------------


def print_list(status_filter: str | None = None) -> None:
    inquiries = load_inquiries()
    if status_filter:
        inquiries = [i for i in inquiries if i.get("status") == status_filter]

    if not inquiries:
        print("  No inquiries found")
        return

    for inq in inquiries:
        s = inq.get("status", "?")
        price = f"{inq['price']:,}" if isinstance(inq.get("price"), (int, float)) else "?"
        city = CITY_LABELS.get(inq.get("city", ""), "")
        print(
            f"  {inq['id']:8s}  [{STATUS_LABELS.get(s, s):6s}]  "
            f"{inq.get('score', '?'):3}pt  {price:>6s}万  {city} {inq.get('name', '?')}"
        )

    print(f"\n  Total: {len(inquiries)}")


def print_stats() -> None:
    inquiries = load_inquiries()
    total = len(inquiries)
    by_status: dict[str, int] = {}
    by_city: dict[str, int] = {}
    for inq in inquiries:
        s = inq.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        c = inq.get("city", "?")
        by_city[c] = by_city.get(c, 0) + 1

    print(f"\n  Property Pipeline ({date.today()})")
    print(f"  {'─' * 32}")
    for s in STATUSES:
        cnt = by_status.get(s, 0)
        if cnt:
            print(f"  {STATUS_LABELS.get(s, s):10s}: {cnt}")
    print(f"  {'─' * 32}")
    print(f"  {'Total':10s}: {total}")
    if by_city:
        print(f"\n  By city:")
        for c, cnt in sorted(by_city.items()):
            print(f"    {CITY_LABELS.get(c, c):6s}: {cnt}")


# ---------------------------------------------------------------------------
# Recalculate CF/CCR from rent_estimate
# ---------------------------------------------------------------------------

ACTIVE_STATUSES_RECALC = {"flagged", "inquired", "in_discussion", "viewing", "viewed", "decided"}


def recalc_properties(property_ids: list[str] | None = None) -> None:
    """Recalculate CF/CCR for specified properties using current rent_estimate."""
    inquiries = load_inquiries()

    recalc_all = property_ids is None or property_ids == ["all"]
    if recalc_all:
        targets = [i for i in inquiries if i.get("status") in ACTIVE_STATUSES_RECALC]
    else:
        targets = [i for i in inquiries if i.get("id") in property_ids]
        found_ids = {i["id"] for i in targets}
        missing = [pid for pid in property_ids if pid not in found_ids]
        if missing:
            print(f"  [warn] IDs not found: {', '.join(missing)}")

    if not targets:
        print("  No matching properties found.")
        return

    changed = 0
    for inq in targets:
        pid = inq.get("id", "?")
        name = inq.get("name", "?")
        price = inq.get("price")
        rent_estimate = inq.get("rent_estimate")

        if not price:
            print(f"  [{pid}] {name}: skip — no price")
            continue
        if not rent_estimate:
            print(f"  [{pid}] {name}: skip — no rent_estimate")
            continue

        price_man = int(price)
        rent_monthly = float(rent_estimate)  # 万円/月
        yield_pct = round(rent_monthly * 12 / price_man * 100, 2)

        yr = inq.get("year_built")
        mgmt = inq.get("management_fee", 0) or 0
        loan_amount = inq.get("loan_amount")
        loan_years = inq.get("loan_years")

        if loan_amount and price_man:
            dr = (price_man - int(loan_amount)) / price_man
        else:
            dr = 0.20

        params = InvestmentParams(
            building_ratio=0.50,
            down_payment_ratio=dr,
            loan_years=int(loan_years) if loan_years else 0,
        )

        rev = revenue_analyze(
            price_man=price_man,
            yield_pct=yield_pct,
            structure="RC造",
            built_year=int(yr) if yr else None,
            maintenance_fee_monthly=int(mgmt) if mgmt else 0,
            params=params,
        )

        mcf = rev.monthly_cf
        ccr = rev.ccr_pct
        after_tax_cf = rev.after_tax_cf
        sign = "+" if mcf >= 0 else ""
        print(f"  [{pid}] {name}: 利回り{yield_pct}% → 月CF {sign}{mcf:.1f}万, CCR {ccr:.1f}%, 税後年CF {after_tax_cf:.1f}万 ({rev.verdict})")

        # Inject recalc summary into notes
        recalc_note = (
            f"[recalc {date.today()}] rent_estimate={rent_monthly}万/月, yield={yield_pct}%, "
            f"月CF={sign}{mcf:.1f}万, CCR={ccr:.1f}%, 税後年CF={after_tax_cf:.1f}万 ({rev.verdict})"
        )
        existing_notes = inq.get("notes") or ""
        # Replace previous recalc note if present, otherwise append
        import re as _re
        cleaned = _re.sub(r"\[recalc [^\]]+\][^\n]*\n?", "", existing_notes).rstrip()
        inq["notes"] = (cleaned + "\n" + recalc_note).lstrip()
        inq["updated"] = str(date.today())
        changed += 1

    if changed:
        save_inquiries(inquiries)
        print(f"\n  {changed} propert{'y' if changed == 1 else 'ies'} updated → {INQUIRIES_PATH}")
    else:
        print("  No updates made.")


# ---------------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------------


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "--auto-flag":
        threshold = int(args[1]) if len(args) > 1 else FLAG_THRESHOLD
        auto_flag(threshold)

    elif cmd == "--list":
        status_filter = args[1] if len(args) > 1 else None
        print_list(status_filter)

    elif cmd == "--inquire":
        if len(args) < 2:
            print("Usage: --inquire ID")
            return
        update_status(args[1], "inquired", inquired_date=str(date.today()))

    elif cmd == "--extract":
        if len(args) < 2:
            print("Usage: --extract ID [--file PATH]  (or pipe email via stdin)")
            return
        if len(args) >= 4 and args[2] == "--file":
            email_body = Path(args[3]).read_text(encoding="utf-8")
        else:
            print("Paste email body (Ctrl+D to finish):")
            email_body = sys.stdin.read()
        result = extract_from_email(args[1], email_body)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "--viewing":
        if len(args) < 3:
            print("Usage: --viewing ID YYYY-MM-DD")
            return
        schedule_viewing(args[1], args[2])

    elif cmd == "--viewed":
        if len(args) < 2:
            print("Usage: --viewed ID [notes...]")
            return
        notes = " ".join(args[2:]) if len(args) > 2 else ""
        update_status(args[1], "viewed", notes=notes)

    elif cmd == "--decide":
        if len(args) < 3:
            print("Usage: --decide ID go|pass [reason...]")
            return
        decision = args[2]
        if decision not in ("go", "pass"):
            print("Decision must be 'go' or 'pass'")
            return
        new_status = "decided" if decision == "go" else "passed"
        reason = " ".join(args[3:]) if len(args) > 3 else ""
        update_status(args[1], new_status, decision=decision, notes=reason)

    elif cmd == "--sync":
        sync_from_agent_memory()

    elif cmd == "--dashboard":
        path = generate_dashboard()
        subprocess.run(["open", str(path)])

    elif cmd == "--naiken":
        path = generate_naiken_analysis()
        if path:
            subprocess.run(["open", str(path)])
        else:
            print("No viewing properties found.")

    elif cmd == "--lifecycle":
        lifecycle()

    elif cmd == "--stats":
        print_stats()

    elif cmd == "--recalc":
        ids = args[1:] if len(args) > 1 else None
        recalc_properties(ids)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
