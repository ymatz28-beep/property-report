"""リスク分析・出口戦略モジュール"""

from dataclasses import dataclass
import datetime


@dataclass
class RiskItem:
    category: str       # 法規制/市場/物件/運営
    severity: str       # 高/中/低
    description: str
    mitigation: str     # 対策


@dataclass
class ExitScenario:
    year: int
    property_value: float
    loan_balance: float
    cumulative_cf: float
    sale_proceeds: float      # 売却手取り
    total_profit: float       # 総利益（CF + 売却益）
    total_roi: float          # 総ROI
    annualized_roi: float     # 年率ROI
    capital_gains_tax: float  # 譲渡所得税


def assess_risks(property_data: dict, config: dict) -> list[RiskItem]:
    """リスク要因の洗い出し"""
    risks = []
    year_built = property_data.get("year_built")
    structure = property_data.get("structure", "RC")
    land_rights = property_data.get("land_rights", "所有権")
    road_access = property_data.get("road_access", "")
    zoning = property_data.get("zoning", "")
    address = property_data.get("address", "")

    age = datetime.datetime.now().year - year_built if year_built else 0

    # --- 物件リスク ---
    if year_built and year_built < 1981:
        risks.append(RiskItem(
            "物件", "高",
            f"旧耐震基準（{year_built}年築）。1981年以前の建物は耐震性に懸念。",
            "耐震診断の実施。耐震補強費用の見積もり取得。地震保険加入必須。"
        ))
    elif year_built and year_built < 2000:
        risks.append(RiskItem(
            "物件", "中",
            f"新耐震だが築{age}年。大規模修繕の必要性あり。",
            "修繕履歴の確認。今後の修繕計画と費用の見積もり。"
        ))

    if structure == "木造" and age > 20:
        risks.append(RiskItem(
            "物件", "高",
            f"木造築{age}年。耐用年数超過により融資困難・資産価値低下。",
            "現地での建物状態確認。シロアリ・雨漏り検査。出口戦略は土地値での売却想定。"
        ))

    if land_rights == "借地権":
        risks.append(RiskItem(
            "物件", "高",
            "借地権物件。地代負担あり・売却が困難。",
            "地代の確認。借地権の残存期間確認。地主との関係確認。"
        ))

    if road_access and ("接道なし" in road_access or "非道路" in road_access):
        risks.append(RiskItem(
            "法規制", "高",
            "再建築不可の可能性。接道義務を満たしていない。",
            "建築確認の可否を役所で確認。43条但書申請の可能性を調査。"
        ))

    # --- 法規制リスク ---
    if zoning and "工業" in zoning:
        risks.append(RiskItem(
            "法規制", "中",
            f"用途地域: {zoning}。住環境に影響する可能性。",
            "周辺環境の実地調査。入居者ターゲットの見直し。"
        ))

    # --- 市場リスク ---
    walk_min = property_data.get("walk_minutes")
    if walk_min and walk_min > 15:
        risks.append(RiskItem(
            "市場", "中",
            f"駅徒歩{walk_min}分。駅遠物件は空室リスクが高い。",
            "バス便の確認。駐車場付帯の検討。家賃設定の見直し。"
        ))

    gross_yield = property_data.get("gross_yield", 0)
    if gross_yield and gross_yield > 12:
        risks.append(RiskItem(
            "市場", "中",
            f"表面利回り{gross_yield}%。高利回りは何らかのリスクを内包している可能性。",
            "空室率・修繕状況・立地の詳細確認。レントロールの精査。"
        ))

    # --- 運営リスク ---
    total_units = property_data.get("total_units", 1)
    if total_units == 1:
        risks.append(RiskItem(
            "運営", "中",
            "単一テナント物件。退去時の収入ゼロリスク。",
            "入居者の属性確認。契約期間の確認。空室期間の資金準備。"
        ))

    # 一般的リスク（常に表示）
    risks.append(RiskItem(
        "市場", "中",
        "金利上昇リスク。変動金利の場合、返済額増加の可能性。",
        "固定金利の検討。金利+1%でのストレステスト実施済み。"
    ))
    risks.append(RiskItem(
        "運営", "低",
        "自然災害リスク（地震・水害・台風）。",
        "ハザードマップの確認。火災保険・地震保険の加入。"
    ))

    risks.sort(key=lambda r: {"高": 0, "中": 1, "低": 2}[r.severity])
    return risks


def calc_exit_strategies(cashflows: list, equity: float, property_data: dict, config: dict, loan_rate: float) -> list[ExitScenario]:
    """出口戦略の分析"""
    exit_conf = config["exit_strategy"]
    price = property_data["price"] * 10000
    tc = config["tax_individual"]

    scenarios = []
    for target_year in exit_conf["analysis_years"]:
        if target_year > len(cashflows):
            continue

        cf = cashflows[target_year - 1]
        sale_price = cf.property_value
        selling_costs = sale_price * exit_conf["selling_cost_rate"]
        sale_proceeds = sale_price - selling_costs - cf.loan_balance

        # 譲渡所得税
        if target_year <= 5:
            cg_rate = tc["capital_gains_short"]
        else:
            cg_rate = tc["capital_gains_long"]

        capital_gain = sale_price - price  # 簡易版（取得費=購入価格）
        cg_tax = max(0, capital_gain * cg_rate)

        net_sale = sale_proceeds - cg_tax
        total_profit = cf.cumulative_cf + net_sale - equity
        total_roi = total_profit / equity * 100 if equity > 0 else 0
        annual_roi = total_roi / target_year if target_year > 0 else 0

        scenarios.append(ExitScenario(
            year=target_year,
            property_value=round(sale_price),
            loan_balance=round(cf.loan_balance),
            cumulative_cf=round(cf.cumulative_cf),
            sale_proceeds=round(net_sale),
            total_profit=round(total_profit),
            total_roi=round(total_roi, 1),
            annualized_roi=round(annual_roi, 1),
            capital_gains_tax=round(cg_tax),
        ))

    return scenarios


def make_investment_decision(rental_result, minpaku_result, risks: list[RiskItem], exit_scenarios: list[ExitScenario]) -> dict:
    """投資判断の総合評価"""
    score = 50  # 基準点

    # 利回り評価
    best_result = rental_result if rental_result.net_yield >= (minpaku_result.net_yield if minpaku_result else 0) else minpaku_result
    if best_result is None:
        best_result = rental_result

    if best_result.net_yield >= 6:
        score += 15
    elif best_result.net_yield >= 4:
        score += 8
    elif best_result.net_yield >= 2:
        score += 0
    else:
        score -= 15

    # DSCR評価
    if best_result.dscr >= 1.5:
        score += 10
    elif best_result.dscr >= 1.2:
        score += 5
    elif best_result.dscr >= 1.0:
        score -= 5
    else:
        score -= 20

    # CCR評価
    if best_result.cash_on_cash >= 8:
        score += 10
    elif best_result.cash_on_cash >= 4:
        score += 5
    elif best_result.cash_on_cash < 0:
        score -= 15

    # IRR評価
    if best_result.irr and best_result.irr >= 8:
        score += 10
    elif best_result.irr and best_result.irr >= 4:
        score += 5

    # リスク評価
    high_risks = sum(1 for r in risks if r.severity == "高")
    score -= high_risks * 10

    # 損益分岐稼働率
    if best_result.breakeven_occupancy <= 70:
        score += 5
    elif best_result.breakeven_occupancy >= 90:
        score -= 10

    score = max(0, min(100, score))

    # 判定
    if score >= 75:
        verdict = "買い推奨"
        verdict_detail = "投資指標が良好で、リスクも許容範囲内です。購入を検討すべき物件です。"
    elif score >= 55:
        verdict = "条件付き推奨"
        verdict_detail = "基本的な投資指標は合格ですが、いくつかの懸念事項があります。条件交渉や追加調査の上、判断してください。"
    elif score >= 35:
        verdict = "慎重検討"
        verdict_detail = "リスク要因が多く、慎重な検討が必要です。価格交渉や条件改善がなければ見送りを推奨します。"
    else:
        verdict = "見送り推奨"
        verdict_detail = "投資指標が基準を満たしておらず、リスクが高い物件です。見送りを強く推奨します。"

    return {
        "score": score,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "key_metrics": {
            "net_yield": best_result.net_yield,
            "dscr": best_result.dscr,
            "cash_on_cash": best_result.cash_on_cash,
            "irr": best_result.irr,
            "breakeven_occupancy": best_result.breakeven_occupancy,
        },
        "high_risk_count": high_risks,
    }
