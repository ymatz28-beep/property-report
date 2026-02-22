"""個人vs法人の税務比較モジュール"""

from dataclasses import dataclass


@dataclass
class TaxResult:
    """税務計算結果"""
    entity_type: str  # "個人" or "法人"
    taxable_income: float
    income_tax: float
    resident_tax: float
    corporate_tax: float
    total_tax: float
    net_income_after_tax: float
    effective_tax_rate: float
    setup_cost: float  # 初期費用（法人設立費等）
    annual_overhead: float  # 年間固定費（税理士等）
    ten_year_total_tax: float
    ten_year_net_income: float
    advantages: list[str]
    disadvantages: list[str]


def calc_individual_tax(noi: float, depreciation: float, loan_interest: float, config: dict, investor_salary: int = 0) -> TaxResult:
    """個人での税額計算

    investor_salary: 投資家の給与所得（円）。指定時は給与+不動産の合算所得で累進税率を適用。
    """
    tc = config["tax_individual"]

    # 不動産所得
    real_estate_income = noi - depreciation - loan_interest

    if investor_salary > 0:
        # 給与所得 + 不動産所得の合算（損益通算対応）
        taxable = investor_salary + real_estate_income
        taxable = max(0, taxable)
    else:
        taxable = max(0, real_estate_income)

    # 所得税（合算所得に対して累進税率を適用）
    income_tax = 0
    for bracket in tc["income_brackets"]:
        if taxable <= bracket["upper"]:
            income_tax = taxable * bracket["rate"] - bracket["deduction"]
            break

    # 給与所得のみの場合の税額を差し引いて不動産分の追加税額を算出
    if investor_salary > 0:
        salary_tax = 0
        for bracket in tc["income_brackets"]:
            if investor_salary <= bracket["upper"]:
                salary_tax = investor_salary * bracket["rate"] - bracket["deduction"]
                break
        salary_tax = max(0, salary_tax)
        salary_resident = investor_salary * tc["resident_tax_rate"]

        income_tax = max(0, income_tax)
        resident_tax = taxable * tc["resident_tax_rate"]

        # 不動産分の追加税負担
        incremental_income_tax = income_tax - salary_tax
        incremental_resident_tax = resident_tax - salary_resident
        total_tax = incremental_income_tax + incremental_resident_tax
        effective_rate = total_tax / noi if noi > 0 else 0
    else:
        income_tax = max(0, income_tax)
        resident_tax = taxable * tc["resident_tax_rate"]
        total_tax = income_tax + resident_tax
        effective_rate = total_tax / noi if noi > 0 else 0

    net_after_tax = noi - total_tax

    advantages = [
        "設立費用不要",
        "確定申告のみで対応可能",
        "青色申告特別控除（65万円）利用可",
        "損益通算による節税可能",
    ]
    disadvantages = [
        "累進課税（所得増加で税率上昇）",
        "経費計上の範囲が限定的",
        "相続時の評価額が高くなりやすい",
    ]

    return TaxResult(
        entity_type="個人",
        taxable_income=round(taxable),
        income_tax=round(income_tax),
        resident_tax=round(resident_tax),
        corporate_tax=0,
        total_tax=round(total_tax),
        net_income_after_tax=round(net_after_tax),
        effective_tax_rate=round(effective_rate * 100, 1),
        setup_cost=0,
        annual_overhead=0,
        ten_year_total_tax=round(total_tax * 10),
        ten_year_net_income=round(net_after_tax * 10),
        advantages=advantages,
        disadvantages=disadvantages,
    )


def calc_corporate_tax(noi: float, depreciation: float, loan_interest: float, config: dict) -> TaxResult:
    """法人での税額計算"""
    tc = config["tax_corporate"]

    # 法人所得（役員報酬控除後）
    officer_salary = min(noi * 0.3, 3600000)  # NOIの30%または360万円の低い方
    taxable = noi - depreciation - loan_interest - officer_salary - tc["accountant_annual"]
    taxable = max(0, taxable)

    # 法人税
    if taxable <= 8000000:
        corp_tax = taxable * tc["effective_rate_small"]
    else:
        corp_tax = 8000000 * tc["effective_rate_small"] + (taxable - 8000000) * tc["effective_rate_large"]

    corp_tax = max(corp_tax, tc["annual_min_tax"])

    # 役員報酬に対する個人の税金（簡易計算）
    personal_tax = officer_salary * 0.15  # 給与所得控除後の実効税率約15%と仮定

    total_tax = corp_tax + personal_tax
    effective_rate = total_tax / noi if noi > 0 else 0
    net_after_tax = noi - total_tax - tc["accountant_annual"]

    advantages = [
        "実効税率が一定（約25-35%）",
        "経費計上の幅が広い（役員報酬、出張旅費等）",
        "損金繰越が10年間可能",
        "相続対策として有効",
        "社会的信用が高い",
    ]
    disadvantages = [
        f"法人設立費用: {tc['establishment_cost']:,}円",
        f"税理士費用: 年間{tc['accountant_annual']:,}円",
        f"均等割: 年間{tc['annual_min_tax']:,}円（赤字でも必要）",
        "社会保険料の負担",
    ]

    return TaxResult(
        entity_type="法人",
        taxable_income=round(taxable),
        income_tax=0,
        resident_tax=0,
        corporate_tax=round(corp_tax),
        total_tax=round(total_tax),
        net_income_after_tax=round(net_after_tax),
        effective_tax_rate=round(effective_rate * 100, 1),
        setup_cost=tc["establishment_cost"],
        annual_overhead=tc["accountant_annual"] + tc["annual_min_tax"],
        ten_year_total_tax=round(total_tax * 10 + tc["establishment_cost"]),
        ten_year_net_income=round(net_after_tax * 10 - tc["establishment_cost"]),
        advantages=advantages,
        disadvantages=disadvantages,
    )


def compare_tax(noi: float, property_data: dict, config: dict, loan_rate: float, loan_amount: float, investor_profile=None) -> dict:
    """個人vs法人の税務比較"""
    # 減価償却計算（簡易版）
    price = property_data["price"] * 10000
    structure = property_data.get("structure", "RC")
    year_built = property_data.get("year_built")

    useful_life = {"木造": 22, "軽量鉄骨": 27, "RC": 47, "SRC": 47, "重量鉄骨": 34}.get(structure, 47)

    import datetime
    age = datetime.datetime.now().year - year_built if year_built else 0
    remaining_life = max(useful_life - age, useful_life * 0.2)

    # 建物比率推定（土地:建物 = 4:6と仮定）
    building_ratio = 0.6
    building_value = price * building_ratio
    annual_depreciation = building_value / remaining_life

    # ローン利息（初年度概算）
    annual_interest = loan_amount * loan_rate

    investor_salary = 0
    if investor_profile is not None:
        investor_salary = investor_profile.salary_income

    individual = calc_individual_tax(noi, annual_depreciation, annual_interest, config, investor_salary=investor_salary)
    corporate = calc_corporate_tax(noi, annual_depreciation, annual_interest, config)

    # 推奨判定
    if noi > 5000000 and corporate.ten_year_net_income > individual.ten_year_net_income:
        recommendation = "法人"
        reason = "NOIが500万円超で法人の方が10年間の手取りが多い"
    elif noi <= 3000000:
        recommendation = "個人"
        reason = "NOIが300万円以下で法人の固定費負担が大きい"
    else:
        diff = individual.ten_year_net_income - corporate.ten_year_net_income
        if diff > 0:
            recommendation = "個人"
            reason = f"10年間の手取り差: 個人が{diff:,.0f}円有利"
        else:
            recommendation = "法人"
            reason = f"10年間の手取り差: 法人が{-diff:,.0f}円有利"

    return {
        "individual": individual,
        "corporate": corporate,
        "recommendation": recommendation,
        "reason": reason,
        "depreciation_annual": round(annual_depreciation),
    }
