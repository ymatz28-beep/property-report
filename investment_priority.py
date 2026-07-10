"""Cross-city investment priority ranking: financing favorability x profitability.

Routinizes the manual triage judgment (loan_years/structure for financing +
CCR/payback/verdict for profitability) that was previously done ad-hoc per
property during deep-dive discovery, so every patrol run surfaces the same
ranking automatically instead of relying on a human noticing a good candidate.

Called from generate_search_report_common.generate_report() (per city, right
after scoring) to persist ranked records, and read by
generate_investment_priority.py to build the cross-city dashboard.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("data")
PRIORITY_DIR = DATA_DIR / "investment_priority"

# 収支verdict（revenue_calc.pyが既に算出済み）別の加点。判定ロジック自体は再実装しない。
PROFIT_POINTS = {
    "高CF物件": 25,
    "安定CF": 15,
    "薄利": 5,
    "CF赤字": -20,
}

# 構造別の融資しやすさ加点。法定耐用年数（RC/SRC=47年, S=34年, 木造=22年）が長いほど
# 銀行の融資期間・LTVが伸びやすいことに基づく（loan_yearsの年数側は別途加点）。
STRUCTURE_POINTS = {
    "RC造": 10,
    "SRC造": 10,
    "S造": 5,
    "鉄骨造": 5,
    "木造": 0,
}


def compute_financing_score(loan_years: int | None, structure: str) -> int:
    """融資の組みやすさスコア。loan_yearsは澤畠さん(筑波銀行)ルールで既に算出済みの値を使う。"""
    score = 0
    if loan_years is not None:
        if loan_years >= 30:
            score += 15
        elif loan_years >= 25:
            score += 10
        elif loan_years >= 20:
            score += 5
        else:
            score -= 5
    for key, pts in STRUCTURE_POINTS.items():
        if key in (structure or ""):
            score += pts
            break
    return score


def build_priority_records(rows: list, config) -> list[dict]:
    """Build investment-priority records for properties with usable revenue data."""
    records = []
    for r in rows:
        if not r.revenue:
            continue
        loan_years = r.revenue.get("loan_years")
        verdict = r.revenue.get("verdict", "")
        financing_score = compute_financing_score(loan_years, r.structure)
        profit_score = PROFIT_POINTS.get(verdict, 0)
        records.append({
            "city_key": config.city_key,
            "city_label": config.city_label,
            "name": r.name,
            "url": r.url,
            "price_man": r.price_man,
            "location": r.location,
            "structure": r.structure or "不明",
            "loan_years": loan_years,
            "verdict": verdict,
            "ccr": r.revenue.get("ccr"),
            "payback_years": r.revenue.get("payback_years"),
            "monthly_cf": r.revenue.get("after_tax_monthly_cf"),
            "quality_score": r.total_score,
            "financing_score": financing_score,
            "profit_score": profit_score,
            "composite_score": financing_score + profit_score,
        })
    records.sort(key=lambda x: -x["composite_score"])
    return records


def save_city_priority(city_key: str, records: list[dict]) -> Path:
    PRIORITY_DIR.mkdir(parents=True, exist_ok=True)
    out = PRIORITY_DIR / f"{city_key}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_all_priority() -> list[dict]:
    """Load and merge per-city priority records, sorted by composite score."""
    all_records: list[dict] = []
    if not PRIORITY_DIR.exists():
        return all_records
    for f in sorted(PRIORITY_DIR.glob("*.json")):
        try:
            all_records.extend(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    all_records.sort(key=lambda x: -x["composite_score"])
    return all_records


def tier_for(score: int) -> tuple[str, str]:
    """Map composite score to (label, CSS color var name)."""
    if score >= 30:
        return "優良", "var(--green)"
    if score >= 10:
        return "有望", "var(--yellow)"
    return "参考", "var(--text-muted)"
