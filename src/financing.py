"""融資シミュレーション・保証会社推奨モジュール"""

from dataclasses import dataclass
from src.analyzer import calc_monthly_payment, calc_loan_balance


@dataclass
class LoanSimResult:
    """融資シミュレーション結果"""
    bank_name: str
    bank_key: str
    interest_rate: float
    loan_amount: float
    loan_years: int
    monthly_payment: float
    annual_payment: float
    total_payment: float
    total_interest: float
    ltv: float
    available: bool
    reason: str  # 利用不可の場合の理由
    notes: str
    recommended: bool


@dataclass
class GuaranteeRecommendation:
    """保証会社推奨結果"""
    company_name: str
    guarantee_fee_rate: float
    guarantee_fee_amount: float
    features: str
    match_score: int  # 1-5のマッチスコア
    reason: str


def simulate_all_banks(property_data: dict, config: dict, use_minpaku: bool = False, annual_income: int = 5000000) -> list[LoanSimResult]:
    """全金融機関での融資シミュレーション"""
    price = property_data["price"] * 10000
    results = []

    for bank_key, bank in config["financing"].items():
        rate = bank["interest_rate_typical"] / 100
        ltv = bank["max_ltv"]
        loan_years = bank["max_term_years"]
        loan_amount = price * ltv

        # 利用可否判定
        available = True
        reason = ""

        if use_minpaku and not bank["minpaku_ok"]:
            available = False
            reason = "民泊非対応"
        elif annual_income < bank.get("min_annual_income", 0):
            available = False
            reason = f"年収{bank['min_annual_income']:,}円以上必要"

        # 築年チェック（耐用年数超え）
        year_built = property_data.get("year_built")
        if year_built:
            import datetime
            age = datetime.datetime.now().year - year_built
            structure = property_data.get("structure", "RC")
            useful_life = {"木造": 22, "軽量鉄骨": 27, "RC": 47, "SRC": 47, "重量鉄骨": 34}.get(structure, 47)
            remaining = useful_life - age
            if remaining < 10 and bank.get("strict_review"):
                available = False
                reason = f"残耐用年数{remaining}年（審査厳格行では困難）"
            elif remaining > 0:
                loan_years = min(loan_years, remaining)

        if available:
            monthly = calc_monthly_payment(loan_amount, rate, loan_years)
            annual = monthly * 12
            total = annual * loan_years
            total_interest = total - loan_amount
        else:
            monthly = annual = total = total_interest = 0

        # 推奨判定
        recommended = False
        if available:
            noi = property_data.get("current_rent_monthly", 0) * 10000 * 12 * 0.75
            dscr = noi / annual if annual > 0 else 0
            if dscr >= 1.2 and rate <= 0.03:
                recommended = True

        results.append(LoanSimResult(
            bank_name=bank["name"],
            bank_key=bank_key,
            interest_rate=bank["interest_rate_typical"],
            loan_amount=round(loan_amount),
            loan_years=loan_years,
            monthly_payment=round(monthly),
            annual_payment=round(annual),
            total_payment=round(total),
            total_interest=round(total_interest),
            ltv=ltv,
            available=available,
            reason=reason,
            notes=bank["notes"],
            recommended=recommended,
        ))

    # 推奨が1つもなければ、利用可能な中で最も金利の低いものを推奨
    available_results = [r for r in results if r.available]
    if available_results and not any(r.recommended for r in results):
        best = min(available_results, key=lambda r: r.interest_rate)
        best.recommended = True

    return results


def recommend_guarantee_companies(property_data: dict, config: dict) -> list[GuaranteeRecommendation]:
    """保証会社の推奨"""
    price = property_data["price"] * 10000
    annual_rent = property_data.get("current_rent_monthly", 0) * 10000 * 12
    year_built = property_data.get("year_built")
    structure = property_data.get("structure", "RC")
    land_rights = property_data.get("land_rights", "所有権")

    import datetime
    age = datetime.datetime.now().year - year_built if year_built else 0

    results = []
    for key, gc in config["guarantee_companies"].items():
        fee_rate = (gc["guarantee_fee_rate_min"] + gc["guarantee_fee_rate_max"]) / 2
        fee_amount = annual_rent * fee_rate

        # マッチスコア計算
        score = 3  # 基準
        reasons = []

        if key == "saison_fundex":
            if age > 30:
                score += 1
                reasons.append("築古物件に強い")
            if land_rights == "借地権":
                score += 1
                reasons.append("借地権対応可")
            if structure == "木造" and age > 20:
                score += 1
                reasons.append("木造築古対応")
            reasons.append("柔軟審査で幅広い属性に対応")

        elif key == "zenpo_ren":
            if age <= 20:
                score += 1
                reasons.append("標準物件に最適")
            reasons.append("業界最大手の安心感")

        elif key == "nihon_safety":
            reasons.append("幅広い物件種別に対応")
            if property_data.get("property_type") in ["一棟マンション", "区分マンション"]:
                score += 1
                reasons.append("マンション実績豊富")

        elif key == "casa":
            reasons.append("IT対応でスムーズな手続き")

        results.append(GuaranteeRecommendation(
            company_name=gc["name"],
            guarantee_fee_rate=fee_rate,
            guarantee_fee_amount=round(fee_amount),
            features=gc["features"],
            match_score=min(score, 5),
            reason="。".join(reasons),
        ))

    results.sort(key=lambda x: x.match_score, reverse=True)
    return results
