#!/usr/bin/env python3
"""
一棟もの 収支シミュレーター (revenue_calc.py)

IttomonoRow の数値フィールドから CF・CCR・節税効果・税引後キャッシュフロー等を
純粋な算術計算で導出する。外部API・ネットワーク呼び出しなし。

Usage:
    from revenue_calc import analyze, InvestmentParams
    result = analyze(price_man=15000, yield_pct=7.5, structure="RC造", built_year=2005)
    print(result.monthly_cf)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Investment Parameters (configurable at call site)
# ============================================================

@dataclass
class InvestmentParams:
    """Loan and expense parameters — override defaults as needed."""

    # Financing
    down_payment_ratio: float = 0.20   # 頭金比率 (20%)
    loan_rate_annual: float = 0.0285   # ローン金利 年率 (2.85%)
    loan_years: int = 30               # ローン期間 (30年)

    # Operations
    vacancy_rate: float = 0.07         # 空室率 (7%)
    opex_rate: float = 0.20            # 経費率 (管理・修繕・保険・固定資産税, 20%)

    # Depreciation
    building_ratio: float = 0.60       # 建物比率 (取得価格の60% = 建物, 残40% = 土地)

    # Tax
    tax_rate: float = 0.30             # 所得税+住民税合算 (30%)


# Module-level defaults — used when params=None
DEFAULT_PARAMS = InvestmentParams()

# Useful life by structure (法定耐用年数)
USEFUL_LIFE: dict[str, int] = {
    "RC":  47,  # RC造 / SRC造
    "SRC": 47,
    "S":   34,  # S造 / 鉄骨造
    "木":  22,  # 木造
}

CURRENT_YEAR = 2026


# ============================================================
# Output dataclass
# ============================================================

@dataclass
class RevenueAnalysis:
    """Full revenue / cash-flow breakdown for a single property."""

    # Inputs (echo back for reference)
    price_man: int
    yield_pct: float
    structure: str
    built_year: Optional[int]
    units_count: int
    area_sqm: Optional[float]
    params: InvestmentParams = field(repr=False, default_factory=InvestmentParams)

    # --- Income ---
    gross_income: float = 0.0          # 年間賃料収入 (万円)
    vacancy_loss: float = 0.0          # 空室損 (万円)
    effective_income: float = 0.0      # 実効収入 (万円)
    opex: float = 0.0                  # 運営経費 (万円)
    noi: float = 0.0                   # NOI (万円)
    net_yield_pct: float = 0.0         # 実質利回り (%)

    # --- Financing ---
    down_payment: float = 0.0          # 頭金 (万円)
    loan_amount: float = 0.0           # 借入額 (万円)
    annual_debt_service: float = 0.0   # 年間ローン返済 (万円)

    # --- Cash Flow ---
    annual_cf: float = 0.0             # 年間CF (万円) = NOI - ADS
    monthly_cf: float = 0.0            # 月間CF (万円)
    ccr_pct: float = 0.0               # CCR / Cash-on-Cash Return (%)
    payback_years: float = 0.0         # 投資回収年数 (年)

    # --- Tax / Depreciation ---
    useful_life: int = 0               # 法定耐用年数 (年)
    remaining_life: int = 0            # 残存耐用年数 (年)
    depreciation_annual: float = 0.0   # 年間減価償却費 (万円)
    taxable_income: float = 0.0        # 課税所得 (万円)
    tax_benefit: float = 0.0           # 節税効果 (万円, 課税所得<0 の場合)
    after_tax_cf: float = 0.0          # 税引後CF (万円)

    # --- Verdict ---
    verdict: str = ""                  # 高CF物件 / 安定CF / 薄利 / CF赤字


# ============================================================
# Core Calculation
# ============================================================

def _resolve_useful_life(structure: str) -> int:
    """Map structure string to legal useful life (年)."""
    s = structure.upper()
    if "SRC" in s:
        return USEFUL_LIFE["SRC"]
    if "RC" in s or "鉄筋コンクリート" in s:
        return USEFUL_LIFE["RC"]
    if "S造" in s or "S " in s or "鉄骨" in s:
        return USEFUL_LIFE["S"]
    if "木造" in s or "木 " in s:
        return USEFUL_LIFE["木"]
    # Unknown structure → conservative estimate (RC)
    return USEFUL_LIFE["RC"]


def _pmt(rate_annual: float, nper: int, pv: float) -> float:
    """PMT formula: annual payment on a fixed-rate fully-amortizing loan.

    Args:
        rate_annual: Annual interest rate (e.g. 0.018 for 1.8%)
        nper: Loan term in years
        pv: Principal (positive = outstanding balance)

    Returns:
        Annual debt service (positive value = cash outflow)
    """
    if rate_annual == 0:
        return pv / nper
    r = rate_annual / 12          # monthly rate
    n = nper * 12                  # total months
    monthly = pv * r * (1 + r) ** n / ((1 + r) ** n - 1)
    return monthly * 12            # convert to annual


def analyze(
    price_man: int,
    yield_pct: float,
    structure: str,
    built_year: Optional[int],
    units_count: int = 0,
    area_sqm: Optional[float] = None,
    params: Optional[InvestmentParams] = None,
) -> RevenueAnalysis:
    """Calculate revenue and cash-flow metrics for a 一棟もの property.

    Args:
        price_man: Purchase price in 万円 (e.g. 15000 = 1.5億)
        yield_pct: Gross yield percentage (e.g. 7.5 for 7.5%)
        structure: Building structure string (e.g. "RC造", "S造", "木造")
        built_year: Year of construction (e.g. 2005), or None if unknown
        units_count: Number of rental units (0 if unknown)
        area_sqm: Total floor area in m² (optional, for reference)
        params: InvestmentParams override. Uses DEFAULT_PARAMS if None.

    Returns:
        RevenueAnalysis dataclass with all computed metrics.
    """
    p = params or DEFAULT_PARAMS

    result = RevenueAnalysis(
        price_man=price_man,
        yield_pct=yield_pct,
        structure=structure,
        built_year=built_year,
        units_count=units_count,
        area_sqm=area_sqm,
        params=p,
    )

    # Guard: nothing meaningful to compute without price or yield
    if price_man <= 0 or yield_pct <= 0:
        result.verdict = "データ不足"
        return result

    # ---- Income ----
    gross_income = price_man * yield_pct / 100
    vacancy_loss = gross_income * p.vacancy_rate
    effective_income = gross_income - vacancy_loss
    opex = effective_income * p.opex_rate
    noi = effective_income - opex
    net_yield_pct = noi / price_man * 100

    result.gross_income = round(gross_income, 2)
    result.vacancy_loss = round(vacancy_loss, 2)
    result.effective_income = round(effective_income, 2)
    result.opex = round(opex, 2)
    result.noi = round(noi, 2)
    result.net_yield_pct = round(net_yield_pct, 2)

    # ---- Financing ----
    down_payment = price_man * p.down_payment_ratio
    loan_amount = price_man * (1 - p.down_payment_ratio)
    annual_debt_service = _pmt(p.loan_rate_annual, p.loan_years, loan_amount)

    result.down_payment = round(down_payment, 2)
    result.loan_amount = round(loan_amount, 2)
    result.annual_debt_service = round(annual_debt_service, 2)

    # ---- Cash Flow ----
    annual_cf = noi - annual_debt_service
    monthly_cf = annual_cf / 12
    ccr_pct = (annual_cf / down_payment * 100) if down_payment > 0 else 0.0
    payback_years = (down_payment / annual_cf) if annual_cf > 0 else float("inf")

    result.annual_cf = round(annual_cf, 2)
    result.monthly_cf = round(monthly_cf, 2)
    result.ccr_pct = round(ccr_pct, 2)
    result.payback_years = round(payback_years, 1) if payback_years != float("inf") else float("inf")

    # ---- Depreciation ----
    useful_life = _resolve_useful_life(structure)
    age = (CURRENT_YEAR - built_year) if built_year else 0
    remaining_life = max(1, useful_life - age)
    depreciation_annual = (price_man * p.building_ratio) / remaining_life

    result.useful_life = useful_life
    result.remaining_life = remaining_life
    result.depreciation_annual = round(depreciation_annual, 2)

    # ---- Tax / After-Tax CF ----
    # Simplified model: interest portion of ADS is deductible.
    # We approximate annual interest as loan_amount × rate (year-1 approximation).
    # For a more precise model, integrate declining interest over the amortization schedule.
    # Here we use a single-year approximation (conservative for early years).
    annual_interest_approx = loan_amount * p.loan_rate_annual
    taxable_income = noi - annual_interest_approx - depreciation_annual

    if taxable_income < 0:
        # Red ink — generates loss pass-through against other income
        tax_benefit = abs(taxable_income) * p.tax_rate
        income_tax_due = 0.0
    else:
        tax_benefit = 0.0
        income_tax_due = taxable_income * p.tax_rate

    after_tax_cf = annual_cf - income_tax_due + tax_benefit

    result.taxable_income = round(taxable_income, 2)
    result.tax_benefit = round(tax_benefit, 2)
    result.after_tax_cf = round(after_tax_cf, 2)

    # ---- Verdict ----
    if monthly_cf > 30:
        result.verdict = "高CF物件"
    elif monthly_cf > 15:
        result.verdict = "安定CF"
    elif monthly_cf > 0:
        result.verdict = "薄利"
    else:
        result.verdict = "CF赤字"

    return result


# ============================================================
# Pretty-print helper
# ============================================================

def _fmt(value: float, unit: str = "万円", decimals: int = 1) -> str:
    """Format a float for display."""
    if value == float("inf"):
        return "∞"
    return f"{value:,.{decimals}f} {unit}"


def print_analysis(r: RevenueAnalysis) -> None:
    """Print a human-readable breakdown of the RevenueAnalysis."""
    p = r.params
    sep = "─" * 52

    print(sep)
    print(f"  物件概要")
    print(sep)
    price_oku = r.price_man / 10000
    print(f"  購入価格     : {r.price_man:,} 万円 ({price_oku:.2f}億)")
    print(f"  表面利回り   : {r.yield_pct}%")
    print(f"  構造         : {r.structure or '不明'}")
    built = str(r.built_year) + "年" if r.built_year else "不明"
    print(f"  築年         : {built}  (残存耐用年数 {r.remaining_life}年 / 法定{r.useful_life}年)")
    print(f"  総戸数       : {r.units_count}戸" if r.units_count else "  総戸数       : 不明")
    if r.area_sqm:
        print(f"  敷地面積     : {r.area_sqm}㎡")

    print()
    print(f"  【ローン条件】 頭金{p.down_payment_ratio*100:.0f}% / {p.loan_rate_annual*100:.1f}% / {p.loan_years}年")
    print(sep)
    print(f"  頭金         : {_fmt(r.down_payment)}")
    print(f"  借入額       : {_fmt(r.loan_amount)}")
    print(f"  年間返済     : {_fmt(r.annual_debt_service)}")

    print()
    print(f"  【収入・支出】 空室率{p.vacancy_rate*100:.0f}% / 経費率{p.opex_rate*100:.0f}%")
    print(sep)
    print(f"  年間賃料収入 : {_fmt(r.gross_income)}")
    print(f"  空室損       : {_fmt(-r.vacancy_loss)}")
    print(f"  実効収入     : {_fmt(r.effective_income)}")
    print(f"  運営経費     : {_fmt(-r.opex)}")
    print(f"  NOI          : {_fmt(r.noi)}")
    print(f"  実質利回り   : {r.net_yield_pct}%")

    print()
    print(f"  【キャッシュフロー】")
    print(sep)
    print(f"  年間CF       : {_fmt(r.annual_cf)}")
    print(f"  月間CF       : {_fmt(r.monthly_cf)}")
    cf_sign = "+" if r.monthly_cf >= 0 else ""
    print(f"               ({cf_sign}{r.monthly_cf:.1f}万円/月)")
    print(f"  CCR          : {r.ccr_pct:.2f}%")
    print(f"  投資回収年数 : {r.payback_years:.1f}年" if r.payback_years != float("inf") else "  投資回収年数 : ∞ (CF赤字)")

    print()
    print(f"  【減価償却・節税】 建物比率{p.building_ratio*100:.0f}% / 税率{p.tax_rate*100:.0f}%")
    print(sep)
    print(f"  年間償却費   : {_fmt(r.depreciation_annual)}")
    print(f"  課税所得     : {_fmt(r.taxable_income)}")
    if r.tax_benefit > 0:
        print(f"  節税効果     : +{_fmt(r.tax_benefit)}  ← 損失計上による還付相当")
    else:
        income_tax = r.taxable_income * p.tax_rate
        print(f"  税負担       : {_fmt(income_tax)}")
    print(f"  税引後年間CF : {_fmt(r.after_tax_cf)}")
    print(f"  税引後月間CF : {_fmt(r.after_tax_cf / 12)}")

    print()
    print(sep)
    verdict_display = {
        "高CF物件": "★★★ 高CF物件",
        "安定CF":   "★★  安定CF",
        "薄利":     "★   薄利",
        "CF赤字":   "✗   CF赤字",
        "データ不足": "?   データ不足",
    }
    print(f"  総合判定     : {verdict_display.get(r.verdict, r.verdict)}")
    print(sep)


# ============================================================
# Demo
# ============================================================

if __name__ == "__main__":
    print("=" * 52)
    print("  一棟もの 収支シミュレーター — サンプル試算")
    print("=" * 52)

    # --- Case 1: RC造, 大阪, 1.5億, 利回り7.5%, 築20年, 15戸 ---
    print("\n[Case 1] 大阪 RC造 1.5億 / 利回り7.5% / 2004年築 / 15戸")
    r1 = analyze(
        price_man=15000,
        yield_pct=7.5,
        structure="RC造",
        built_year=2004,
        units_count=15,
        area_sqm=650.0,
    )
    print_analysis(r1)

    # --- Case 2: 木造アパート, 福岡, 8000万, 利回り9%, 築30年, 8戸 ---
    print("\n[Case 2] 福岡 木造 8000万 / 利回り9% / 1996年築 / 8戸")
    r2 = analyze(
        price_man=8000,
        yield_pct=9.0,
        structure="木造",
        built_year=1996,
        units_count=8,
    )
    print_analysis(r2)

    # --- Case 3: S造, 東京, 2億, 利回り5%, 築10年, 20戸 (CF check) ---
    print("\n[Case 3] 東京 S造 2億 / 利回り5% / 2014年築 / 20戸")
    r3 = analyze(
        price_man=20000,
        yield_pct=5.0,
        structure="S造",
        built_year=2014,
        units_count=20,
    )
    print_analysis(r3)

    # --- Case 4: Custom params — lower down payment, higher vacancy ---
    print("\n[Case 4] 大阪 RC造 1.8億 / 利回り6.5% / カスタムパラメータ (頭金10%, 空室10%)")
    custom = InvestmentParams(
        down_payment_ratio=0.10,
        vacancy_rate=0.10,
        loan_rate_annual=0.02,
        loan_years=35,
    )
    r4 = analyze(
        price_man=18000,
        yield_pct=6.5,
        structure="SRC造",
        built_year=2001,
        units_count=18,
        params=custom,
    )
    print_analysis(r4)
