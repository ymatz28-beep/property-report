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
  --stats               Show pipeline statistics
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

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

# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------


def load_inquiries() -> list[dict]:
    if not INQUIRIES_PATH.exists():
        return []
    with open(INQUIRIES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("inquiries", [])


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

            entry = {
                "id": _next_id(inquiries + new_flagged),
                "name": row.name,
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

    return f'''<a href="{inq.get('url', '#')}" target="_blank" rel="noopener" class="inq-card"{dimmed}>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span class="card-name">{inq.get('name', '?')}</span>
    <div style="display:flex;gap:6px;align-items:center">
      <span class="status-pill" style="background:{color}">{label}</span>
      <span class="card-score">{inq.get('score', '?')}pt</span>
    </div>
  </div>
  <div class="card-detail">{price} / {area} / {inq.get('layout', '?')} / {inq.get('station', '?')}</div>
  <div class="card-filters">
    <span>ペット {pet_icon}</span>
    <span>短期賃貸 {st_icon}</span>
    {f'<span>担当: {inq["agent"]}</span>' if inq.get('agent') else ''}
  </div>
  {viewing_line}{notes_line}
  <div class="card-meta">{inq.get('source', '')} / {inq.get('id', '')}</div>
</a>'''


def _load_agent_memory() -> dict:
    """inbox-zero/data/agent_memory.yaml を読み込み。"""
    mem_path = BASE.parent / "inbox-zero" / "data" / "agent_memory.yaml"
    if not mem_path.exists():
        return {}
    with open(mem_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("agents", {})


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
    <span class="sched-name">{inq.get("name", "?")}</span>
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


def generate_dashboard() -> Path:
    from generate_search_report_common import (
        global_nav_css,
        global_nav_html,
        site_header_css,
        site_header_html,
    )

    inquiries = load_inquiries()
    agent_memory = _load_agent_memory()

    # Stats
    total = len(inquiries)
    by_status: dict[str, int] = {}
    by_city: dict[str, int] = {}
    for inq in inquiries:
        s = inq.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        c = inq.get("city", "other")
        by_city[c] = by_city.get(c, 0) + 1

    # Status priority for sorting within each city (active first)
    status_priority = {
        "viewing": 0, "in_discussion": 1, "inquired": 2,
        "flagged": 3, "viewed": 4, "decided": 5, "passed": 6,
    }

    # City configs matching existing report design
    city_configs = [
        ("osaka", "大阪", "#3b9eff", "59,158,255"),
        ("fukuoka", "福岡", "#34d399", "52,211,153"),
        ("tokyo", "東京", "#a78bfa", "167,139,250"),
    ]

    # Build section nav
    nav_items = []
    for city_key, city_label, accent, _ in city_configs:
        cnt = by_city.get(city_key, 0)
        if cnt:
            nav_items.append(
                f'<a href="#city-{city_key}" class="nav-tab" '
                f'onclick="showCity(\'{city_key}\')" data-city="{city_key}">'
                f'{city_label} <span class="tab-count">{cnt}</span></a>'
            )

    section_nav = (
        '<div class="section-nav"><div class="section-nav-inner">'
        + '<a href="#" class="nav-tab active" onclick="showCity(\'all\')" data-city="all">'
        + f'All <span class="tab-count">{total}</span></a>'
        + "".join(nav_items)
        + "</div></div>"
    )

    # Build city sections
    city_sections = []
    for city_key, city_label, accent, accent_rgb in city_configs:
        city_items = [i for i in inquiries if i.get("city") == city_key]
        if not city_items:
            continue

        # Sort: active statuses first, then by score descending
        city_items.sort(
            key=lambda x: (status_priority.get(x.get("status", ""), 9), -(x.get("score") or 0))
        )

        # City-level stats
        city_active = sum(
            1 for i in city_items if i.get("status") in ("viewing", "in_discussion", "inquired")
        )
        city_flagged = sum(1 for i in city_items if i.get("status") == "flagged")

        cards_html = "\n".join(_render_card(inq) for inq in city_items)

        city_sections.append(f'''
<div class="city-section" id="city-{city_key}" data-city="{city_key}">
  <div class="city-header" style="border-left:3px solid {accent}">
    <h2>{city_label}</h2>
    <div class="city-stats">
      <span>{len(city_items)}件</span>
      {f'<span style="color:#f97316">進行中 {city_active}</span>' if city_active else ''}
      {f'<span style="color:{accent}">候補 {city_flagged}</span>' if city_flagged else ''}
    </div>
  </div>
  <div class="city-cards">{cards_html}</div>
</div>''')

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Property Pipeline — iUMA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#050507;color:#f5f5f7;font-family:'Inter','Noto Sans JP',sans-serif;min-height:100vh}}
{site_header_css()}
{global_nav_css()}
.container{{max-width:800px;margin:0 auto;padding:0 16px 80px}}

/* Hero */
.hero{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:32px 32px 28px;margin:20px 0}}
.hero h1{{font-size:clamp(20px,2.5vw,26px);font-weight:700}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}}
.stat{{background:rgba(255,255,255,.06);border-radius:10px;padding:10px 16px;text-align:center;min-width:72px}}
.stat-val{{font-size:22px;font-weight:700;font-family:'JetBrains Mono',monospace}}
.stat-label{{font-size:10px;color:#71717a;margin-top:2px}}

/* Section nav — matches stock portfolio .nav-bar pattern */
.section-nav{{position:sticky;top:92px;z-index:80;background:rgba(10,12,18,.94);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.06);margin:0 -16px;padding:0 16px}}
.section-nav-inner{{display:flex;gap:0;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch;scrollbar-width:none}}
.section-nav-inner::-webkit-scrollbar{{display:none}}
.nav-tab{{display:inline-flex;align-items:center;gap:4px;padding:10px 16px;font-size:12px;font-weight:600;color:rgba(255,255,255,.45);text-decoration:none;border-bottom:2px solid transparent;transition:color .2s,border-color .2s;cursor:pointer}}
.nav-tab:hover{{color:rgba(255,255,255,.8)}}
.nav-tab.active{{color:#fff;border-bottom-color:#3b9eff}}
.tab-count{{font-size:10px;color:rgba(255,255,255,.3);font-family:'JetBrains Mono',monospace}}
.nav-tab.active .tab-count{{color:rgba(255,255,255,.6)}}

/* City sections */
.city-section{{margin-top:28px}}
.city-section.hidden{{display:none}}
.city-header{{padding-left:12px;margin-bottom:14px;display:flex;align-items:baseline;gap:12px}}
.city-header h2{{font-size:18px;font-weight:700}}
.city-stats{{display:flex;gap:10px;font-size:11px;color:#71717a}}

/* Cards */
.inq-card{{display:block;text-decoration:none;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:16px;margin-bottom:8px;transition:background .15s,border-color .15s}}
.inq-card:hover{{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.14)}}
.card-name{{color:#f5f5f7;font-size:14px;font-weight:600}}
.card-score{{background:rgba(255,255,255,.08);padding:2px 8px;border-radius:8px;font-size:11px;font-family:'JetBrains Mono',monospace;color:#a1a1aa}}
.status-pill{{padding:2px 8px;border-radius:8px;font-size:10px;font-weight:600;color:#fff}}
.card-detail{{color:#a1a1aa;font-size:12px;margin-top:6px}}
.card-filters{{display:flex;gap:12px;margin-top:8px;font-size:11px;color:#71717a}}
.card-meta{{color:#52525b;font-size:10px;margin-top:6px}}

/* Schedule section */
.schedule-section{{margin:24px 0;padding:0}}
.schedule-header{{display:flex;align-items:baseline;gap:12px;margin-bottom:14px}}
.schedule-header h2{{font-size:18px;font-weight:700}}
.schedule-counts{{display:flex;gap:10px;font-size:11px}}
.schedule-cards{{display:flex;flex-direction:column;gap:8px}}
.sched-card{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:16px;transition:background .15s}}
.sched-card:hover{{background:rgba(255,255,255,.08)}}
.sched-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.sched-name{{font-size:15px;font-weight:600;color:#f5f5f7}}
.sched-city{{font-size:11px;color:#71717a;font-family:'JetBrains Mono',monospace}}
.sched-date{{font-size:13px;color:#a78bfa;margin-bottom:4px}}
.sched-loc{{font-size:12px;color:#71717a;margin-bottom:4px}}
.sched-agent{{font-size:12px;color:#d4d4d8;margin-bottom:2px}}
.agent-title{{font-size:10px;color:#71717a;margin-left:4px}}
.sched-contact{{font-size:11px;color:#71717a;margin-bottom:4px;font-family:'JetBrains Mono',monospace}}
.sched-filters{{font-size:11px;color:#71717a;margin-top:6px}}
.sched-notes{{font-size:11px;color:#a1a1aa;font-style:italic;margin-top:4px}}

/* Empty state */
.empty{{text-align:center;padding:60px 20px;color:#52525b}}
.empty h2{{font-size:18px;color:#71717a;margin-bottom:8px}}

@media(max-width:640px){{
  .hero{{padding:24px 20px 20px}}
  .stats{{gap:8px}}
  .stat{{min-width:60px;padding:8px 12px}}
  .stat-val{{font-size:18px}}
  .nav-tab{{padding:10px 12px;font-size:11px}}
  .city-header h2{{font-size:16px}}
}}
</style>
</head>
<body>
{site_header_html()}
{global_nav_html("inquiry-pipeline.html")}

<div class="container">
  <div class="hero">
    <h1>Property Pipeline</h1>
    <div class="stats">
      <div class="stat"><div class="stat-val">{total}</div><div class="stat-label">Total</div></div>
      <div class="stat"><div class="stat-val" style="color:#f97316">{by_status.get('in_discussion', 0) + by_status.get('inquired', 0)}</div><div class="stat-label">進行中</div></div>
      <div class="stat"><div class="stat-val" style="color:#a78bfa">{by_status.get('viewing', 0)}</div><div class="stat-label">内見</div></div>
      <div class="stat"><div class="stat-val" style="color:#22c55e">{by_status.get('decided', 0)}</div><div class="stat-label">決定</div></div>
      <div class="stat"><div class="stat-val" style="color:#ef4444">{by_status.get('passed', 0)}</div><div class="stat-label">見送り</div></div>
    </div>
  </div>

  {_build_viewing_schedule(inquiries, agent_memory)}

  {section_nav}

  {''.join(city_sections) if city_sections else '<div class="empty"><h2>No inquiries yet</h2><p>Run --auto-flag to detect high-score properties</p></div>'}
</div>

<script>
function showCity(city) {{
  document.querySelectorAll('.city-section').forEach(s => {{
    s.classList.toggle('hidden', city !== 'all' && s.dataset.city !== city);
  }});
  document.querySelectorAll('.nav-tab').forEach(t => {{
    t.classList.toggle('active', t.dataset.city === city);
  }});
}}
</script>
</body>
</html>'''

    out_path = OUTPUT / "inquiry-pipeline.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[pipeline] Dashboard → {out_path}")
    return out_path


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

    elif cmd == "--stats":
        print_stats()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
