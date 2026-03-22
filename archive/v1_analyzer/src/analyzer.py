"""収支分析・投資指標計算モジュール"""

import numpy as np
from dataclasses import dataclass, field


@dataclass
class CashFlowResult:
    """年間キャッシュフロー"""
    year: int
    gross_income: float
    operating_expenses: float
    noi: float  # Net Operating Income
    debt_service: float  # ローン返済額
    net_cash_flow: float  # 税引前CF
    cumulative_cf: float
    loan_balance: float
    property_value: float


@dataclass
class AnalysisResult:
    """分析結果"""
    # 基本指標
    gross_yield: float          # 表面利回り
    net_yield: float            # 実質利回り（NOI利回り）
    cap_rate: float             # キャップレート
    cash_on_cash: float         # CCR（自己資金利回り）
    roi: float                  # ROI
    irr: float | None           # IRR
    dscr: float                 # DSCR
    payback_years: int | None   # 回収期間

    # 年間収支
    annual_gross_income: float
    annual_operating_expenses: float
    annual_noi: float
    annual_debt_service: float
    annual_net_cf: float

    # 投資額
    total_investment: float     # 総投資額
    equity: float               # 自己資金
    loan_amount: float

    # 35年キャッシュフロー
    cashflows: list[CashFlowResult] = field(default_factory=list)

    # 損益分岐点
    breakeven_occupancy: float = 0.0  # 損益分岐稼働率


def calc_monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    """元利均等返済の月額返済額"""
    if annual_rate == 0:
        return principal / (years * 12)
    r = annual_rate / 12
    n = years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def calc_loan_balance(principal: float, annual_rate: float, years: int, elapsed_years: int) -> float:
    """ローン残高計算"""
    if annual_rate == 0:
        return principal * (1 - elapsed_years / years)
    r = annual_rate / 12
    n = years * 12
    p = elapsed_years * 12
    monthly = calc_monthly_payment(principal, annual_rate, years)
    return principal * (1 + r) ** p - monthly * ((1 + r) ** p - 1) / r


def get_rent_decline_rate(year: int, config: dict) -> float:
    """年次ごとの家賃下落率を取得"""
    decline = config.get("rent_decline", {})
    if year <= 10:
        return decline.get("year_1_10", 0.01)
    elif year <= 20:
        return decline.get("year_11_20", 0.005)
    else:
        return decline.get("year_21_35", 0.003)


def get_property_decline_rate(structure: str, config: dict) -> float:
    """構造別の物件価値下落率"""
    decline = config.get("property_decline", {})
    structure_map = {
        "木造": "wooden",
        "軽量鉄骨": "light_steel",
        "RC": "rc",
        "SRC": "src",
        "重量鉄骨": "rc",
    }
    key = structure_map.get(structure, "rc")
    return decline.get(key, 0.015)


def analyze_rental(property_data: dict, config: dict, loan_rate: float, loan_years: int, ltv: float) -> AnalysisResult:
    """賃貸収支分析"""
    price = property_data["price"] * 10000  # 万円→円
    rc = config["rental_costs"]
    pc = config["purchase_costs"]

    # 諸費用計算
    purchase_costs = (
        price * pc["registration_tax"]
        + price * pc["acquisition_tax"]
        + price * pc["stamp_duty"]
        + price * pc["agent_fee"]
        + pc["judicial_scrivener"]
        + pc["misc"]
    )

    # 融資
    loan_amount = price * ltv
    equity = price - loan_amount + purchase_costs
    total_investment = price + purchase_costs

    # 年間収入
    monthly_rent = property_data["current_rent_monthly"] * 10000
    annual_gross = monthly_rent * 12
    effective_income = annual_gross * (1 - rc["vacancy_rate"])

    # 年間支出
    property_tax = price * rc["assessed_value_ratio"] * rc["property_tax_rate"]
    annual_expenses = (
        effective_income * rc["management_fee_rate"]
        + effective_income * rc["maintenance_reserve"]
        + rc["insurance_annual"]
        + property_tax
    )

    # NOI
    noi = effective_income - annual_expenses

    # ローン返済
    monthly_payment = calc_monthly_payment(loan_amount, loan_rate, loan_years)
    annual_debt_service = monthly_payment * 12

    # 税引前CF
    net_cf = noi - annual_debt_service

    # 指標計算
    gross_yield = annual_gross / price * 100
    net_yield = noi / price * 100
    cap_rate = noi / price * 100
    cash_on_cash = net_cf / equity * 100 if equity > 0 else 0
    dscr = noi / annual_debt_service if annual_debt_service > 0 else float("inf")

    # 損益分岐稼働率
    fixed_costs = annual_expenses - effective_income * (rc["management_fee_rate"] + rc["maintenance_reserve"])
    variable_rate = rc["management_fee_rate"] + rc["maintenance_reserve"]
    if annual_gross > 0:
        breakeven_occ = (annual_debt_service + fixed_costs) / (annual_gross * (1 - variable_rate))
    else:
        breakeven_occ = 1.0

    # 35年キャッシュフロー
    years = config["analysis"]["years"]
    cashflows = []
    cumulative = 0
    payback_year = None
    cf_for_irr = [-equity]
    prop_decline = get_property_decline_rate(property_data.get("structure", "RC"), config)

    current_rent = monthly_rent
    current_prop_value = price

    for y in range(1, years + 1):
        # 家賃下落
        decline_rate = get_rent_decline_rate(y, config)
        current_rent *= (1 - decline_rate)
        year_gross = current_rent * 12 * (1 - rc["vacancy_rate"])

        year_expenses = (
            year_gross * rc["management_fee_rate"]
            + year_gross * rc["maintenance_reserve"]
            + rc["insurance_annual"]
            + property_tax
        )
        year_noi = year_gross - year_expenses

        if y <= loan_years:
            year_ds = annual_debt_service
        else:
            year_ds = 0

        year_ncf = year_noi - year_ds
        cumulative += year_ncf

        # 物件価値下落
        current_prop_value *= (1 - prop_decline)

        loan_bal = calc_loan_balance(loan_amount, loan_rate, loan_years, min(y, loan_years)) if y <= loan_years else 0

        cashflows.append(CashFlowResult(
            year=y,
            gross_income=year_gross,
            operating_expenses=year_expenses,
            noi=year_noi,
            debt_service=year_ds,
            net_cash_flow=year_ncf,
            cumulative_cf=cumulative,
            loan_balance=loan_bal,
            property_value=current_prop_value,
        ))

        cf_for_irr.append(year_ncf)

        if payback_year is None and cumulative >= 0:
            payback_year = y

    # 最終年に売却想定を加算（IRR計算用）
    final_sale = current_prop_value * (1 - config["exit_strategy"]["selling_cost_rate"])
    final_loan_bal = cashflows[-1].loan_balance
    cf_for_irr[-1] += final_sale - final_loan_bal

    # IRR計算
    irr = _calc_irr(cf_for_irr)

    # ROI（初年度）
    roi = (net_cf + (price * prop_decline * -1)) / equity * 100 if equity > 0 else 0

    return AnalysisResult(
        gross_yield=round(gross_yield, 2),
        net_yield=round(net_yield, 2),
        cap_rate=round(cap_rate, 2),
        cash_on_cash=round(cash_on_cash, 2),
        roi=round(roi, 2),
        irr=round(irr * 100, 2) if irr is not None else None,
        dscr=round(dscr, 2),
        payback_years=payback_year,
        annual_gross_income=round(effective_income),
        annual_operating_expenses=round(annual_expenses),
        annual_noi=round(noi),
        annual_debt_service=round(annual_debt_service),
        annual_net_cf=round(net_cf),
        total_investment=round(total_investment),
        equity=round(equity),
        loan_amount=round(loan_amount),
        cashflows=cashflows,
        breakeven_occupancy=round(breakeven_occ * 100, 1),
    )


def analyze_minpaku(property_data: dict, config: dict, loan_rate: float, loan_years: int, ltv: float, nightly_rate: float | None = None) -> AnalysisResult:
    """民泊収支分析"""
    price = property_data["price"] * 10000
    mc = config["minpaku_costs"]
    pc = config["purchase_costs"]

    # 諸費用
    purchase_costs = (
        price * pc["registration_tax"]
        + price * pc["acquisition_tax"]
        + price * pc["stamp_duty"]
        + price * pc["agent_fee"]
        + pc["judicial_scrivener"]
        + pc["misc"]
        + mc["license_cost"]
    )

    loan_amount = price * ltv
    equity = price - loan_amount + purchase_costs
    total_investment = price + purchase_costs

    # 民泊収入推定
    if nightly_rate is None:
        # 賃料の2.5倍を日額として推定
        monthly_rent = property_data.get("current_rent_monthly", 0) * 10000
        nightly_rate = monthly_rent / 30 * 2.5 if monthly_rent > 0 else 10000

    annual_gross = nightly_rate * 365 * mc["occupancy_rate"]

    # 年間支出
    property_tax = price * mc["assessed_value_ratio"] * mc["property_tax_rate"]
    cleaning_annual = mc["cleaning_per_stay"] * mc["avg_stays_per_month"] * 12
    annual_expenses = (
        annual_gross * mc["management_fee_rate"]
        + annual_gross * mc["platform_fee_rate"]
        + cleaning_annual
        + mc["amenity_monthly"] * 12
        + mc["insurance_annual"]
        + property_tax
    )

    noi = annual_gross - annual_expenses

    monthly_payment = calc_monthly_payment(loan_amount, loan_rate, loan_years)
    annual_debt_service = monthly_payment * 12
    net_cf = noi - annual_debt_service

    gross_yield = annual_gross / price * 100
    net_yield = noi / price * 100
    cap_rate = noi / price * 100
    cash_on_cash = net_cf / equity * 100 if equity > 0 else 0
    dscr = noi / annual_debt_service if annual_debt_service > 0 else float("inf")

    # 損益分岐稼働率
    fixed_costs = cleaning_annual + mc["amenity_monthly"] * 12 + mc["insurance_annual"] + property_tax
    variable_rate = mc["management_fee_rate"] + mc["platform_fee_rate"]
    daily_revenue = nightly_rate * 365
    if daily_revenue > 0:
        breakeven_occ = (annual_debt_service + fixed_costs) / (daily_revenue * (1 - variable_rate))
    else:
        breakeven_occ = 1.0

    # 35年CF
    years = config["analysis"]["years"]
    cashflows = []
    cumulative = 0
    payback_year = None
    cf_for_irr = [-equity]
    prop_decline = get_property_decline_rate(property_data.get("structure", "RC"), config)

    current_nightly = nightly_rate
    current_prop_value = price

    for y in range(1, years + 1):
        decline = get_rent_decline_rate(y, config)
        current_nightly *= (1 - decline * 0.5)  # 民泊は下落率半分と仮定

        year_gross = current_nightly * 365 * mc["occupancy_rate"]
        year_expenses = (
            year_gross * mc["management_fee_rate"]
            + year_gross * mc["platform_fee_rate"]
            + cleaning_annual
            + mc["amenity_monthly"] * 12
            + mc["insurance_annual"]
            + property_tax
        )
        year_noi = year_gross - year_expenses
        year_ds = annual_debt_service if y <= loan_years else 0
        year_ncf = year_noi - year_ds
        cumulative += year_ncf

        current_prop_value *= (1 - prop_decline)
        loan_bal = calc_loan_balance(loan_amount, loan_rate, loan_years, min(y, loan_years)) if y <= loan_years else 0

        cashflows.append(CashFlowResult(
            year=y,
            gross_income=year_gross,
            operating_expenses=year_expenses,
            noi=year_noi,
            debt_service=year_ds,
            net_cash_flow=year_ncf,
            cumulative_cf=cumulative,
            loan_balance=loan_bal,
            property_value=current_prop_value,
        ))
        cf_for_irr.append(year_ncf)
        if payback_year is None and cumulative >= 0:
            payback_year = y

    final_sale = current_prop_value * (1 - config["exit_strategy"]["selling_cost_rate"])
    final_loan_bal = cashflows[-1].loan_balance
    cf_for_irr[-1] += final_sale - final_loan_bal

    irr = _calc_irr(cf_for_irr)
    roi = (net_cf + (price * prop_decline * -1)) / equity * 100 if equity > 0 else 0

    return AnalysisResult(
        gross_yield=round(gross_yield, 2),
        net_yield=round(net_yield, 2),
        cap_rate=round(cap_rate, 2),
        cash_on_cash=round(cash_on_cash, 2),
        roi=round(roi, 2),
        irr=round(irr * 100, 2) if irr is not None else None,
        dscr=round(dscr, 2),
        payback_years=payback_year,
        annual_gross_income=round(annual_gross),
        annual_operating_expenses=round(annual_expenses),
        annual_noi=round(noi),
        annual_debt_service=round(annual_debt_service),
        annual_net_cf=round(net_cf),
        total_investment=round(total_investment),
        equity=round(equity),
        loan_amount=round(loan_amount),
        cashflows=cashflows,
        breakeven_occupancy=round(breakeven_occ * 100, 1),
    )


def sensitivity_analysis(property_data: dict, config: dict, loan_rate: float, loan_years: int, ltv: float, mode: str = "rental") -> dict:
    """感度分析"""
    sens = config["sensitivity"]
    results = {"rent": {}, "occupancy": {}, "interest": {}}

    analyze = analyze_rental if mode == "rental" else analyze_minpaku

    base = analyze(property_data, config, loan_rate, loan_years, ltv)

    # 家賃変動
    for delta in sens["rent_change"]:
        modified = property_data.copy()
        if modified.get("current_rent_monthly"):
            modified["current_rent_monthly"] = modified["current_rent_monthly"] * (1 + delta)
        r = analyze(modified, config, loan_rate, loan_years, ltv)
        label = f"{delta:+.0%}"
        results["rent"][label] = {
            "net_yield": r.net_yield,
            "cash_on_cash": r.cash_on_cash,
            "dscr": r.dscr,
            "annual_net_cf": r.annual_net_cf,
        }

    # 稼働率変動（configを一時変更）
    for delta in sens["occupancy_change"]:
        modified_config = _deep_copy_config(config)
        if mode == "rental":
            base_vr = modified_config["rental_costs"]["vacancy_rate"]
            modified_config["rental_costs"]["vacancy_rate"] = max(0, base_vr - delta)
        else:
            base_or = modified_config["minpaku_costs"]["occupancy_rate"]
            modified_config["minpaku_costs"]["occupancy_rate"] = min(1.0, base_or + delta)
        r = analyze(property_data, modified_config, loan_rate, loan_years, ltv)
        label = f"{delta:+.0%}"
        results["occupancy"][label] = {
            "net_yield": r.net_yield,
            "cash_on_cash": r.cash_on_cash,
            "dscr": r.dscr,
            "annual_net_cf": r.annual_net_cf,
        }

    # 金利変動
    for delta in sens["interest_change"]:
        new_rate = max(0.001, loan_rate + delta)
        r = analyze(property_data, config, new_rate, loan_years, ltv)
        label = f"{delta:+.2%}"
        results["interest"][label] = {
            "net_yield": r.net_yield,
            "cash_on_cash": r.cash_on_cash,
            "dscr": r.dscr,
            "annual_net_cf": r.annual_net_cf,
        }

    return results


def _calc_irr(cashflows: list[float]) -> float | None:
    """IRR計算（Newton法）"""
    try:
        return float(np.irr(cashflows)) if hasattr(np, 'irr') else _irr_newton(cashflows)
    except Exception:
        return _irr_newton(cashflows)


def _irr_newton(cashflows: list[float], tol: float = 1e-8, max_iter: int = 1000) -> float | None:
    """Newton法によるIRR計算"""
    rate = 0.1
    for _ in range(max_iter):
        npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))
        dnpv = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cashflows))
        if abs(dnpv) < 1e-12:
            return None
        new_rate = rate - npv / dnpv
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate
        if abs(rate) > 10:
            return None
    return None


def _deep_copy_config(config: dict) -> dict:
    """configのディープコピー"""
    import copy
    return copy.deepcopy(config)
