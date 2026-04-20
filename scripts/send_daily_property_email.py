#!/usr/bin/env python3
"""Daily property patrol email — delivers today's new-listings + source health.

Reads property-analyzer/data/patrol_summary.json and emails a stacked-card
summary (per DESIGN.md §Email). Runs daily at 10:00 JST via launchd
(com.yuma.property-daily-email).

Run: python send_daily_property_email.py [--dry-run]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.digest.delivery_gmail import send_gmail_html  # noqa: E402

PATROL_SUMMARY = ROOT / "property-analyzer" / "data" / "patrol_summary.json"
DASHBOARD_URL = "https://ymatz28-beep.github.io/property-report/"
MAX_NEW_ITEMS_SHOWN = 10

C_BG = "#f5f5f7"
C_CARD = "#ffffff"
C_TEXT = "var(--bg-secondary)"
C_MUTED = "#6b7280"
C_ERROR = "var(--accent-red)"
C_WARN = "var(--accent-amber)"
C_SUCCESS = "var(--accent-green)"
C_INFO = "#6366f1"
FONT = "-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif"
JP_CSS = "overflow-wrap:anywhere;line-break:strict;"


def esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def card(inner_html: str) -> str:
    return (
        f'<div style="background:{C_CARD};border-radius:10px;padding:16px;'
        f'margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.06);">'
        f"{inner_html}</div>"
    )


def _item_row(label_html: str, value_html: str, accent: str = C_MUTED) -> str:
    return (
        f'<div style="padding:8px 0;border-top:1px solid #eee;'
        f"display:flex;justify-content:space-between;gap:12px;"
        f'font-size:13px;color:{C_TEXT};{JP_CSS}">'
        f'<div style="flex:1;">{label_html}</div>'
        f'<div style="color:{accent};white-space:nowrap;">{value_html}</div>'
        f"</div>"
    )


def render_email(summary: dict) -> str:
    date_str = esc(summary.get("date", "?"))
    total = summary.get("total", 0)
    prev = summary.get("prev_total", 0)
    new = summary.get("new_count", 0)
    removed = summary.get("removed_count", 0)
    elapsed = summary.get("elapsed_min", 0)
    ok = summary.get("ok_count", 0)
    step_total = summary.get("step_count", 0)
    failed_sources = summary.get("failed_sources", []) or []
    failed_steps = summary.get("failed_steps", []) or []
    new_items = summary.get("new_items", []) or []

    delta_str = ""
    if new or removed:
        delta_str = (
            f' <span style="color:{C_SUCCESS};">+{new}</span>'
            f' <span style="color:{C_WARN};">-{removed}</span>'
        )
    hero = card(
        f'<div style="font-weight:700;font-size:18px;color:{C_TEXT};'
        f'margin-bottom:4px;">🏠 今日の物件パトロール</div>'
        f'<div style="font-size:13px;color:{C_MUTED};{JP_CSS}">'
        f"{date_str} / 追跡 <strong>{total}</strong> 件{delta_str} / "
        f"所要 {elapsed}分 / 取得 {ok}/{step_total} ソース"
        f"</div>"
    )

    new_card = ""
    if new_items:
        rows: list[str] = []
        for it in new_items[:MAX_NEW_ITEMS_SHOWN]:
            title = esc((it.get("title") or it.get("name") or "?")[:140])
            src = esc(it.get("source") or it.get("site") or "?")
            url = it.get("url") or ""
            area = esc(it.get("area") or it.get("region") or "")
            price = esc(str(it.get("price") or it.get("price_text") or ""))
            tags = " / ".join(x for x in [area, price] if x)
            link = (
                f'<a href="{esc(url)}" style="color:{C_INFO};'
                f'text-decoration:none;font-weight:600;">{title}</a>'
                if url
                else f'<span style="font-weight:600;">{title}</span>'
            )
            rows.append(
                f'<div style="padding:10px 0;border-top:1px solid #eee;{JP_CSS}">'
                f'<div style="font-size:13px;color:{C_TEXT};margin-bottom:2px;">'
                f"{link}</div>"
                f'<div style="font-size:11px;color:{C_MUTED};">'
                f"{src}{' · ' + tags if tags else ''}</div>"
                f"</div>"
            )
        shown = min(MAX_NEW_ITEMS_SHOWN, len(new_items))
        new_card = card(
            f'<div style="font-weight:700;font-size:15px;color:{C_SUCCESS};'
            f'margin-bottom:4px;">🆕 新着 {len(new_items)}件'
            + (
                f" — 上位{shown}表示" if len(new_items) > shown else ""
            )
            + "</div>"
            + "".join(rows)
        )

    err_card = ""
    if failed_sources or failed_steps:
        src_rows: list[str] = []
        for s in failed_sources[:8]:
            src_rows.append(_item_row(esc(str(s)), "source", C_ERROR))
        for s in failed_steps[:8]:
            src_rows.append(_item_row(esc(str(s)), "step", C_ERROR))
        total_fail = len(failed_sources) + len(failed_steps)
        err_card = card(
            f'<div style="font-weight:700;font-size:15px;color:{C_ERROR};'
            f'margin-bottom:4px;">🔴 失敗 {total_fail}件</div>'
            + "".join(src_rows)
        )

    health = card(
        f'<div style="font-weight:700;font-size:15px;color:{C_TEXT};'
        f'margin-bottom:4px;">ソース健全性</div>'
        f'<div style="font-size:13px;color:{C_MUTED};{JP_CSS}">'
        f'<span style="color:{C_SUCCESS if ok == step_total else C_WARN};">'
        f"{ok}/{step_total} OK</span>"
        f"{' · ' + str(total) + '件追跡' if total else ''}"
        f"</div>"
    )

    cta = (
        f'<div style="text-align:center;margin-top:8px;">'
        f'<a href="{DASHBOARD_URL}" '
        f'style="display:inline-block;background:{C_INFO};color:#fff;'
        f"text-decoration:none;padding:12px 24px;border-radius:8px;"
        f"font-weight:600;font-size:14px;min-height:44px;line-height:20px;"
        f'">property-report で詳細を見る →</a></div>'
    )

    return (
        f'<html><body style="margin:0;padding:0;background:{C_BG};">'
        f'<div style="max-width:600px;margin:0 auto;padding:16px;'
        f'font-family:{FONT};color:{C_TEXT};">'
        f"{hero}{new_card}{err_card}{health}{cta}"
        f"</div></body></html>"
    )


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not PATROL_SUMMARY.exists():
        print(f"[property-daily] missing {PATROL_SUMMARY} — skip")
        return 0
    summary = json.loads(PATROL_SUMMARY.read_text(encoding="utf-8"))
    new = summary.get("new_count", 0)
    removed = summary.get("removed_count", 0)
    failed = len(summary.get("failed_sources", []) or []) + len(
        summary.get("failed_steps", []) or []
    )
    date_str = summary.get("date", "?")
    badge = f"+{new}/-{removed}" if (new or removed) else "異常なし"
    if failed:
        badge = f"🔴失敗{failed} / {badge}"
    subject = f"🏠 物件パトロール {date_str} ({badge}) | Property Daily"
    html = render_email(summary)
    if dry:
        preview = Path("/tmp/property_daily_preview.html")
        preview.write_text(html, encoding="utf-8")
        print(f"[property-daily] DRY — wrote preview: {preview}")
        print(f"[property-daily] subject: {subject}")
        return 0
    ok = send_gmail_html(subject, html)
    print(f"[property-daily] sent={ok} new={new} removed={removed} failed={failed}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
