#!/usr/bin/env python3
"""
大阪R不動産 4物件 比較分析（自宅兼民泊モデル）

前提:
- 3拠点以上の多拠点生活（不在時に民泊稼働）
- 区分マンション: 最低40㎡、理想50㎡以上
- 予算: 5,000万円以下
- 収益性が最重要

投資家プロフィール（確定申告データ）:
- Cisco給与: 約1,600万円
- 不動産収入: 約1,400万円/年（赤字で損益通算）
- 既存借入残高: 約3億円
- 保有物件: 4棟
- 法人: iUMAプロパティマネジメント合同会社
"""

import json
import math
from dataclasses import dataclass

# ============================================================
# 投資家プロフィール
# ============================================================
SALARY_INCOME = 16_000_000       # Cisco給与
RE_INCOME = 13_982_505           # 不動産収入（2024年）
RE_EXPENSES = 21_608_736         # 不動産経費（2024年: 収入13,982,505 - 所得-7,626,231）
EXISTING_LOAN_BALANCE = 308_391_766  # 既存借入残高
EXISTING_PROPERTY_COUNT = 4
ANNUAL_INCOME = SALARY_INCOME + RE_INCOME  # 約3,000万

# ============================================================
# 物件データ
# ============================================================
properties = [
    {
        "id": 1,
        "name": "扇町公園の近くでペットと暮らす",
        "url_id": 25517,
        "address": "北区天神橋3丁目",
        "price": 4580,  # 万円
        "area_sqm": 66.21,
        "year_built": 1976,
        "floor": "3F / SRC12階建",
        "structure": "SRC",
        "station": "天満/扇町 徒歩6分",
        "layout": "1LDK+フリースペース",
        "management_fee": 9000,
        "repair_reserve": 8000,
        "pet": True,
        "new_quake_standard": False,
        "features": "南向き, 無垢フローリング, 室内窓, 家具付き, リノベ済",
        # 民泊パラメータ
        "tourist_area_score": 4,  # 5段階（天神橋筋商店街、扇町公園）
        "estimated_nightly_min": 10000,
        "estimated_nightly_max": 15000,
        "minpaku_regulation": "特区民泊可（大阪市）",
    },
    {
        "id": 2,
        "name": "贅沢な二人暮らし",
        "url_id": 24124,
        "address": "中央区谷町5丁目",
        "price": 4100,
        "area_sqm": 67.15,
        "year_built": 1980,
        "floor": "10F最上階角 / SRC10階建",
        "structure": "SRC",
        "station": "谷町六丁目 徒歩2分",
        "layout": "1LDK(元3LDK)",
        "management_fee": 17051,
        "repair_reserve": 16735,
        "pet": False,
        "new_quake_standard": False,
        "features": "最上階角部屋, メープル無垢材, 西向き, ワークスペース, リノベ済",
        "tourist_area_score": 3,  # 谷町は観光エリアとしてはやや弱い
        "estimated_nightly_min": 9000,
        "estimated_nightly_max": 13000,
        "minpaku_regulation": "特区民泊可（大阪市）",
    },
    {
        "id": 3,
        "name": "暮らしが教える、この魅力。",
        "url_id": 24522,
        "address": "北区東天満2丁目",
        "price": 3480,
        "area_sqm": 60.39,
        "year_built": 1980,
        "floor": "13F / SRC14階建",
        "structure": "SRC",
        "station": "大阪天満宮 徒歩5分 / 南森町 徒歩8分",
        "layout": "L字型LDK",
        "management_fee": 9660,
        "repair_reserve": 10870,
        "pet": True,
        "new_quake_standard": False,
        "features": "南向き13F大阪城ビュー, トランクルーム付, 回遊動線, 2018年リノベ",
        "tourist_area_score": 4,  # 天満宮・南森町は好立地、大阪城ビューは民泊で高評価
        "estimated_nightly_min": 10000,
        "estimated_nightly_max": 14000,
        "minpaku_regulation": "特区民泊可（大阪市）",
    },
    {
        "id": 4,
        "name": "立ち止まる余白",
        "url_id": 24891,
        "address": "中央区谷町5丁目",
        "price": 5980,
        "area_sqm": 60.46,
        "year_built": 2005,
        "floor": "6F / SRC14階建",
        "structure": "SRC",
        "station": "谷町六丁目 徒歩3分 / 谷町四丁目 徒歩4分",
        "layout": "リノベ1LDK",
        "management_fee": 8740,
        "repair_reserve": 16450,
        "pet": True,
        "new_quake_standard": True,
        "features": "新耐震, 二面採光, 造作デスク, ローン控除OK, 2025年リノベ",
        "tourist_area_score": 3,
        "estimated_nightly_min": 9000,
        "estimated_nightly_max": 13000,
        "minpaku_regulation": "特区民泊可（大阪市）",
    },
]

# ============================================================
# 分析パラメータ
# ============================================================
CURRENT_YEAR = 2026
SRC_USEFUL_LIFE = 47

# 融資条件（旧耐震区分は厳しめ）
VARIABLE_RATE = 0.005

# 民泊パラメータ（自宅兼用モデル）
SELF_USE_DAYS = 120          # 年間自己利用日数（月10日）
AVAILABLE_DAYS = 365 - SELF_USE_DAYS  # 民泊可能日数 245日
OCCUPANCY_RATE = 0.70        # 稼働可能日に対する稼働率
PLATFORM_FEE = 0.03          # Airbnb手数料（ホスト負担）
MANAGEMENT_FEE_RATE = 0.20   # 運営代行費率
CLEANING_PER_STAY = 5000     # 清掃費/回
AVG_STAY_NIGHTS = 2.5        # 平均宿泊日数
AMENITY_MONTHLY = 8000       # アメニティ・消耗品
MINPAKU_LICENSE = 0          # 特区民泊届出費用（大阪市は比較的安価）
INSURANCE_ANNUAL = 60000     # 民泊保険

# 購入諸費用率
PURCHASE_COST_RATE = 0.07    # 仲介手数料+登記+取得税+印紙等

# 税率
INCOME_TAX_MARGINAL = 0.33   # 給与1,600万+不動産の限界税率（所得税）
RESIDENT_TAX_RATE = 0.10
MARGINAL_TAX_RATE = INCOME_TAX_MARGINAL + RESIDENT_TAX_RATE  # 43%

# 法人税率（iUMA）
CORPORATE_TAX_RATE_SMALL = 0.25   # 800万以下
ACCOUNTANT_ANNUAL = 300_000       # 税理士追加費用
CORP_MIN_TAX = 70_000             # 均等割


def monthly_payment(principal, annual_rate, years):
    if annual_rate == 0:
        return principal / (years * 12)
    r = annual_rate / 12
    n = years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def loan_balance_at(principal, annual_rate, years, elapsed):
    if annual_rate == 0:
        return principal * (1 - elapsed / years)
    r = annual_rate / 12
    n = years * 12
    p = elapsed * 12
    mp = monthly_payment(principal, annual_rate, years)
    return principal * (1 + r) ** p - mp * ((1 + r) ** p - 1) / r


print("=" * 72)
print("  大阪R不動産 4物件 比較分析")
print("  モデル: 自宅兼民泊（多拠点生活 / 不在時Airbnb稼働）")
print("=" * 72)

# ============================================================
# 0. 予算スクリーニング
# ============================================================
print("\n■ 予算スクリーニング（上限5,000万円）")
print("-" * 72)
for p in properties:
    status = "✅ 予算内" if p["price"] <= 5000 else "❌ 予算オーバー"
    print(f"  #{p['id']} {p['address']:12s}  {p['price']:,}万円  → {status}")

print()

# ============================================================
# 1. 民泊収益シミュレーション
# ============================================================
print("■ 民泊収益シミュレーション（自宅兼用モデル）")
print(f"  前提: 自己利用{SELF_USE_DAYS}日/年, 民泊可能{AVAILABLE_DAYS}日, 稼働率{OCCUPANCY_RATE:.0%}")
print("-" * 72)

results = []

for p in properties:
    price_yen = p["price"] * 10000
    age = CURRENT_YEAR - p["year_built"]
    remaining_life = SRC_USEFUL_LIFE - age

    # ローン条件
    if p["new_quake_standard"]:
        loan_term = 35
    else:
        loan_term = min(max(remaining_life, 20), 25)

    loan_amount = price_yen  # フルローン想定
    purchase_costs = price_yen * PURCHASE_COST_RATE

    # 民泊収入（保守的に min と mid の中間）
    nightly_mid = (p["estimated_nightly_min"] + p["estimated_nightly_max"]) / 2
    actual_operating_days = AVAILABLE_DAYS * OCCUPANCY_RATE
    stays_per_year = actual_operating_days / AVG_STAY_NIGHTS

    gross_revenue = nightly_mid * actual_operating_days

    # 民泊経費
    platform_fee = gross_revenue * PLATFORM_FEE
    mgmt_fee = gross_revenue * MANAGEMENT_FEE_RATE
    cleaning_total = CLEANING_PER_STAY * stays_per_year
    amenity_total = AMENITY_MONTHLY * 12
    insurance = INSURANCE_ANNUAL
    monthly_mgmt = p["management_fee"] + p["repair_reserve"]
    mgmt_repair_annual = monthly_mgmt * 12

    # 固定資産税（簡易：評価額70% × 1.4%）
    property_tax = price_yen * 0.7 * 0.014

    total_expenses = (
        platform_fee + mgmt_fee + cleaning_total +
        amenity_total + insurance + mgmt_repair_annual + property_tax
    )

    noi = gross_revenue - total_expenses

    # ローン返済
    mp = monthly_payment(loan_amount, VARIABLE_RATE, loan_term)
    annual_debt = mp * 12

    # 税引前キャッシュフロー
    pre_tax_cf = noi - annual_debt

    # 減価償却（建物60%想定）
    building_value = price_yen * 0.6
    depreciation = building_value / max(remaining_life, SRC_USEFUL_LIFE * 0.2)

    # 不動産所得
    re_income = noi - depreciation - (loan_amount * VARIABLE_RATE)

    # === 個人での税効果 ===
    # 既存の不動産赤字に加算される
    # 赤字なら損益通算で節税、黒字なら限界税率43%で課税
    if re_income < 0:
        tax_saving = abs(re_income) * MARGINAL_TAX_RATE  # 節税額
        tax_impact = tax_saving  # プラス
        tax_label = "節税"
    else:
        tax_cost = re_income * MARGINAL_TAX_RATE
        tax_impact = -tax_cost  # マイナス
        tax_label = "課税"

    after_tax_cf = pre_tax_cf + tax_impact

    # === 法人（iUMA）での税効果 ===
    corp_re_income = noi - depreciation - (loan_amount * VARIABLE_RATE)
    if corp_re_income < 0:
        corp_tax = 0
        corp_tax_impact = 0  # 法人は損益通算できない（給与と）が繰越控除可
    else:
        corp_tax = corp_re_income * CORPORATE_TAX_RATE_SMALL + CORP_MIN_TAX
        corp_tax_impact = -corp_tax

    corp_after_tax_cf = pre_tax_cf + corp_tax_impact - ACCOUNTANT_ANNUAL / 1  # 追加税理士費用は既存に含まれるなら不要

    # 投資指標
    equity = purchase_costs  # フルローンの場合、自己資金=諸費用のみ
    gross_yield = gross_revenue / price_yen * 100
    net_yield = noi / price_yen * 100
    dscr = noi / annual_debt if annual_debt > 0 else 0
    ccr = after_tax_cf / equity * 100 if equity > 0 else 0

    # 損益分岐稼働率
    fixed_costs_no_revenue = mgmt_repair_annual + insurance + amenity_total + property_tax + annual_debt
    revenue_per_day_net = nightly_mid * (1 - PLATFORM_FEE - MANAGEMENT_FEE_RATE) - CLEANING_PER_STAY / AVG_STAY_NIGHTS
    if revenue_per_day_net > 0:
        breakeven_days = fixed_costs_no_revenue / revenue_per_day_net
        breakeven_occupancy = breakeven_days / AVAILABLE_DAYS * 100
    else:
        breakeven_occupancy = 999

    # DTI（既存+新規）
    existing_annual_payment = EXISTING_LOAN_BALANCE * 0.06  # 年間返済額概算（残高の6%）
    total_annual_payment = existing_annual_payment + annual_debt
    dti = total_annual_payment / ANNUAL_INCOME * 100

    result = {
        "id": p["id"],
        "name": p["name"][:15],
        "address": p["address"],
        "price": p["price"],
        "area_sqm": p["area_sqm"],
        "pet": p["pet"],
        "budget_ok": p["price"] <= 5000,
        "nightly_rate": nightly_mid,
        "operating_days": actual_operating_days,
        "gross_revenue": gross_revenue,
        "total_expenses": total_expenses,
        "noi": noi,
        "annual_debt": annual_debt,
        "pre_tax_cf": pre_tax_cf,
        "depreciation": depreciation,
        "re_income": re_income,
        "tax_impact": tax_impact,
        "tax_label": tax_label,
        "after_tax_cf_individual": after_tax_cf,
        "after_tax_cf_corporate": corp_after_tax_cf,
        "equity": equity,
        "gross_yield": gross_yield,
        "net_yield": net_yield,
        "dscr": dscr,
        "ccr": ccr,
        "breakeven_occupancy": breakeven_occupancy,
        "loan_term": loan_term,
        "monthly_payment": mp,
        "monthly_mgmt": monthly_mgmt,
        "monthly_total": mp + monthly_mgmt,
        "dti": dti,
        "age": age,
        "remaining_life": remaining_life,
        "new_quake": p["new_quake_standard"],
        "tourist_score": p["tourist_area_score"],
    }
    results.append(result)

# 表示
for r in results:
    budget_mark = "✅" if r["budget_ok"] else "⚠️ 予算超"
    pet_mark = "🐾可" if r["pet"] else "🚫不可"
    print(f"\n  #{r['id']} {r['address']} ({r['price']:,}万円) {budget_mark} {pet_mark}")
    print(f"     宿泊単価: ¥{r['nightly_rate']:,.0f}/泊 × {r['operating_days']:.0f}日稼働")
    print(f"     民泊売上:     ¥{r['gross_revenue']:>12,.0f}/年")
    print(f"     経費合計:    -¥{r['total_expenses']:>12,.0f}/年")
    print(f"     NOI:          ¥{r['noi']:>12,.0f}/年")
    print(f"     ローン返済:  -¥{r['annual_debt']:>12,.0f}/年（{r['loan_term']}年, 変動0.5%）")
    print(f"     税引前CF:     ¥{r['pre_tax_cf']:>12,.0f}/年")
    print(f"     減価償却:     ¥{r['depreciation']:>12,.0f}/年")
    print(f"     不動産所得:   ¥{r['re_income']:>12,.0f}/年 → {r['tax_label']}効果: ¥{r['tax_impact']:>+12,.0f}")
    print(f"     税引後CF(個人): ¥{r['after_tax_cf_individual']:>10,.0f}/年")
    print(f"     税引後CF(法人): ¥{r['after_tax_cf_corporate']:>10,.0f}/年")

print()

# ============================================================
# 2. 投資指標比較
# ============================================================
print("■ 投資指標比較")
print("-" * 72)
hdr = f"{'#':>3} {'エリア':12s} {'表面':>6s} {'NOI':>6s} {'DSCR':>6s} {'CCR':>7s} {'BE稼働率':>8s} {'DTI':>6s}"
print(hdr)
print("-" * 72)

for r in results:
    dscr_mark = "✅" if r["dscr"] >= 1.2 else ("⚠️" if r["dscr"] >= 1.0 else "❌")
    be_mark = "✅" if r["breakeven_occupancy"] <= 70 else ("⚠️" if r["breakeven_occupancy"] <= 85 else "❌")
    dti_mark = "✅" if r["dti"] <= 45 else ("⚠️" if r["dti"] <= 50 else "❌")

    print(f"  {r['id']:>1} {r['address']:12s} {r['gross_yield']:>5.1f}% {r['net_yield']:>5.1f}% {r['dscr']:>4.2f}{dscr_mark} {r['ccr']:>5.1f}% {r['breakeven_occupancy']:>5.1f}%{be_mark} {r['dti']:>4.1f}%{dti_mark}")

print()

# ============================================================
# 3. 融資可否判定（既存借入3億考慮）
# ============================================================
print("■ 融資可否判定（既存借入3億円考慮）")
print("-" * 72)

for r in results:
    print(f"\n  #{r['id']} {r['address']}（{r['price']:,}万円）")
    print(f"     DTI: {r['dti']:.1f}%（既存返済+新規返済 / 年収{ANNUAL_INCOME/10000:,.0f}万円）")

    if r["dti"] <= 45:
        print(f"     判定: ✅ 融資可能性あり（DTI 45%以下）")
    elif r["dti"] <= 50:
        print(f"     判定: ⚠️  審査厳格行は困難。信金・ノンバンクなら可能性あり")
    else:
        print(f"     判定: ❌ 融資困難（DTI 50%超過）")

    if not r["new_quake"]:
        print(f"     注意: 旧耐震（築{r['age']}年）→ メガバンクは不可、地銀・信金で要相談")
    else:
        print(f"     優位: 新耐震（築{r['age']}年）→ 融資条件有利")

    # 法人（iUMA）で買う場合
    print(f"     法人取得: iUMAで取得すれば個人DTIに影響しない（法人審査に移行）")

print()

# ============================================================
# 4. 個人 vs 法人（iUMA）比較
# ============================================================
print("■ 個人 vs 法人（iUMA）取得比較")
print("-" * 72)

for r in results:
    print(f"\n  #{r['id']} {r['address']}")
    print(f"     個人: 税引後CF ¥{r['after_tax_cf_individual']:>+10,.0f}/年")
    if r["re_income"] < 0:
        print(f"           → 不動産所得赤字 → 給与と損益通算で節税¥{r['tax_impact']:,.0f}/年")
    else:
        print(f"           → 限界税率43%で課税")
    print(f"     法人: 税引後CF ¥{r['after_tax_cf_corporate']:>+10,.0f}/年")
    print(f"           → 法人税25% / 個人DTIに影響なし / 経費計上の幅広い")

    if r["after_tax_cf_individual"] > r["after_tax_cf_corporate"]:
        diff = r["after_tax_cf_individual"] - r["after_tax_cf_corporate"]
        print(f"     推奨: 個人（年間{diff:,.0f}円有利）+ 損益通算メリット")
    else:
        diff = r["after_tax_cf_corporate"] - r["after_tax_cf_individual"]
        print(f"     推奨: 法人（年間{diff:,.0f}円有利）+ DTI非影響")

print()

# ============================================================
# 5. 出口戦略（5年/10年/15年）
# ============================================================
print("■ 出口戦略（売却シミュレーション）")
print("-" * 72)

SRC_DECLINE = 0.012  # SRC年間下落率
SELLING_COST_RATE = 0.04
CG_SHORT = 0.3945  # 5年以下
CG_LONG = 0.2032   # 5年超

for r in results:
    price_yen = r["price"] * 10000
    print(f"\n  #{r['id']} {r['address']}（取得価格{r['price']:,}万円）")

    for yr in [5, 10, 15]:
        # 物件価値（SRC下落）
        prop_value = price_yen * (1 - SRC_DECLINE) ** yr
        # ローン残高
        loan_bal = loan_balance_at(price_yen, VARIABLE_RATE, r["loan_term"], yr) if yr <= r["loan_term"] else 0
        # 売却手取り
        sale_net = prop_value * (1 - SELLING_COST_RATE) - loan_bal
        # 譲渡所得税
        cg = prop_value - price_yen
        cg_rate = CG_SHORT if yr <= 5 else CG_LONG
        cg_tax = max(0, cg * cg_rate)
        # 累積CF
        cum_cf = r["after_tax_cf_individual"] * yr
        # 総利益
        total_profit = cum_cf + sale_net - cg_tax - r["equity"]
        annual_roi = total_profit / r["equity"] / yr * 100 if r["equity"] > 0 and yr > 0 else 0

        print(f"     {yr:>2}年後: 物件{prop_value/10000:>5,.0f}万 / 残債{loan_bal/10000:>5,.0f}万 / CF累計{cum_cf/10000:>+5,.0f}万 / 総利益{total_profit/10000:>+6,.0f}万（年率ROI {annual_roi:>+.1f}%）")

print()

# ============================================================
# 6. リスク評価
# ============================================================
print("■ リスク評価")
print("-" * 72)

for r in results:
    risks = []

    # 予算
    if not r["budget_ok"]:
        risks.append(("高", "❌ 予算5,000万超過"))

    # ペット
    if not r["pet"]:
        risks.append(("高", "❌ ペット不可"))

    # 耐震
    if not r["new_quake"]:
        risks.append(("高", f"旧耐震（築{r['age']}年）→ 融資制限・資産価値下落"))

    # DTI
    if r["dti"] > 50:
        risks.append(("高", f"DTI {r['dti']:.0f}%超過 → 融資困難"))
    elif r["dti"] > 45:
        risks.append(("中", f"DTI {r['dti']:.0f}% → 審査厳格行は困難"))

    # DSCR
    if r["dscr"] < 1.0:
        risks.append(("高", f"DSCR {r['dscr']:.2f} → 返済余力不足"))
    elif r["dscr"] < 1.2:
        risks.append(("中", f"DSCR {r['dscr']:.2f} → 返済余力が限定的"))

    # 管理費
    if r["monthly_mgmt"] > 25000:
        risks.append(("中", f"管理費+修繕{r['monthly_mgmt']:,}円/月 → 値上げリスク"))

    # 大規模修繕
    if r["age"] > 40:
        risks.append(("中", f"築{r['age']}年 → 大規模修繕一時金リスク"))

    # 民泊規制変更
    risks.append(("低", "大阪市特区民泊の規制変更リスク"))

    # 既存ポートフォリオ
    risks.append(("中", f"保有{EXISTING_PROPERTY_COUNT}件+新規 → ポートフォリオ集中"))

    print(f"\n  #{r['id']} {r['address']}")
    risk_count = {"高": 0, "中": 0, "低": 0}
    for sev, desc in risks:
        risk_count[sev] += 1
        print(f"     [{sev}] {desc}")
    print(f"     → 高{risk_count['高']} / 中{risk_count['中']} / 低{risk_count['低']}")

print()

# ============================================================
# 7. 総合スコアリング
# ============================================================
print("■ 総合スコアリング（自宅兼民泊・多拠点モデル）")
print("=" * 72)

for r in results:
    score = 50
    details = []

    # 予算（必須）
    if not r["budget_ok"]:
        score -= 20
        details.append("予算超 -20")
    else:
        details.append("予算内 +0")

    # ペット（重要）
    if not r["pet"]:
        score -= 15
        details.append("ペット不可 -15")
    else:
        score += 5
        details.append("ペット可 +5")

    # 民泊収益性（最重要）
    if r["after_tax_cf_individual"] > 500000:
        score += 20
        details.append(f"高収益CF +20")
    elif r["after_tax_cf_individual"] > 0:
        score += 10
        details.append(f"黒字CF +10")
    elif r["after_tax_cf_individual"] > -200000:
        score += 0
        details.append(f"微赤字CF ±0")
    else:
        score -= 10
        details.append(f"赤字CF -10")

    # DSCR
    if r["dscr"] >= 1.5:
        score += 10
        details.append("DSCR優 +10")
    elif r["dscr"] >= 1.2:
        score += 5
        details.append("DSCR良 +5")
    elif r["dscr"] < 1.0:
        score -= 15
        details.append("DSCR不足 -15")

    # 観光立地
    if r["tourist_score"] >= 4:
        score += 10
        details.append("観光立地◎ +10")
    elif r["tourist_score"] >= 3:
        score += 5
        details.append("観光立地○ +5")

    # 耐震
    if r["new_quake"]:
        score += 10
        details.append("新耐震 +10")
    else:
        score -= 5
        details.append("旧耐震 -5")

    # 融資（DTI）
    if r["dti"] <= 45:
        score += 5
        details.append("DTI良 +5")
    elif r["dti"] > 50:
        score -= 10
        details.append("DTI超 -10")

    # 面積
    if r["area_sqm"] >= 60:
        score += 5
        details.append("面積60㎡↑ +5")

    # 損益通算メリット
    if r["re_income"] < 0:
        score += 5
        details.append("損益通算◎ +5")

    score = max(0, min(100, score))

    # 判定
    if score >= 75:
        verdict = "★★★ 強く推奨"
    elif score >= 60:
        verdict = "★★☆ 推奨"
    elif score >= 45:
        verdict = "★☆☆ 条件付き"
    else:
        verdict = "☆☆☆ 見送り"

    print(f"\n  #{r['id']} {r['address']} ({r['price']:,}万円)")
    print(f"     スコア: {score}/100  →  {verdict}")
    print(f"     CF(税引後): ¥{r['after_tax_cf_individual']:>+10,.0f}/年（個人）/ ¥{r['after_tax_cf_corporate']:>+10,.0f}/年（法人）")
    print(f"     月額負担: ¥{r['monthly_total']:>8,.0f}（ローン+管理修繕）")
    print(f"     [{', '.join(details)}]")

print()

# ============================================================
# 結論
# ============================================================
print("=" * 72)
print("  結論")
print("=" * 72)
print()
print("  #2（谷町5・4,100万）: ペット不可 → 対象外")
print("  #4（谷町5・5,980万）: 予算5,000万超過 → 要価格交渉 or 見送り")
print()
print("  ■ 実質候補: #1 天神橋3 vs #3 東天満2")
print()
print("  #3 東天満2（3,480万）が最有力:")
print("    ✅ 最安価 → 自己資金（諸費用）最小、融資負担最軽")
print("    ✅ 大阪城ビュー13F → 民泊で差別化ポイント（写真映え）")
print("    ✅ 南森町・大阪天満宮 → 観光アクセス良好")
print("    ✅ 60㎡・ペット可・トランクルーム付")
print("    ✅ 減価償却で不動産所得赤字 → 給与と損益通算で節税")
print("    ⚠️  旧耐震（1980年）→ 融資は地銀・信金で要相談")
print()
print("  #1 天神橋3（4,580万）は次点:")
print("    ✅ 66㎡で広い、家具付き（初期投資抑制）")
print("    ✅ 天神橋筋商店街 → 生活利便性◎")
print("    ⚠️  築50年で#3より古い、3Fで眺望なし")
print()
print("  #4 谷町5（5,980万）は予算交渉できれば:")
print("    ✅ 唯一の新耐震 → 融資・資産価値で圧倒的優位")
print("    ✅ ローン控除13年間で約200万節税")
print("    ❌ 5,000万超は厳しい。500万以上の値引き交渉が必要")
print()
print("  📌 推奨アクション:")
print("    1. #3 東天満を内見 → 民泊としての運用イメージ確認")
print("    2. #1 天神橋も同日内見 → 比較")
print("    3. #4 は価格交渉の余地があるか仲介に確認")
print("    4. 大阪市特区民泊の最新規制を確認（管理組合の民泊可否も）")
print()

# データ保存
output_data = {
    "analysis_date": "2026-02-19",
    "model": "自宅兼民泊（多拠点生活）",
    "investor_profile": {
        "salary_income": SALARY_INCOME,
        "real_estate_income": RE_INCOME,
        "existing_loan_balance": EXISTING_LOAN_BALANCE,
        "existing_property_count": EXISTING_PROPERTY_COUNT,
    },
    "parameters": {
        "self_use_days": SELF_USE_DAYS,
        "available_days": AVAILABLE_DAYS,
        "occupancy_rate": OCCUPANCY_RATE,
        "variable_rate": VARIABLE_RATE,
    },
    "results": results,
}

with open("/Users/yumatejima/Documents/Projects/property-analyzer/data/osaka_r_comparison.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)

print("  データ保存: data/osaka_r_comparison.json")
