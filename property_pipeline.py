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


def generate_dashboard() -> Path:
    from generate_search_report_common import (
        global_nav_css,
        global_nav_html,
        site_header_css,
        site_header_html,
    )

    inquiries = load_inquiries()

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
            key=lambda x: (status_priority.get(x.get("status", ""), 9), -x.get("score", 0))
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
