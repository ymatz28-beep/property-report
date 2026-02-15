#!/usr/bin/env python3
"""大国町物件の分析テスト（登記簿情報 + 手動入力データ）"""

import json
from pathlib import Path
import yaml

from src.analyzer import analyze_rental, analyze_minpaku, sensitivity_analysis
from src.financing import simulate_all_banks, recommend_guarantee_companies
from src.tax_compare import compare_tax
from src.risk import assess_risks, calc_exit_strategies, make_investment_decision
from src.report_generator import generate_pdf, generate_excel

# 登記簿から読み取った物件データ + 手動補完
property_data = {
    "property_name": "大国町1丁目ビル",
    "address": "大阪市浪速区大国一丁目7-22",
    "price": 13000,  # 万円（1億3千万円）
    "structure": "重量鉄骨",  # 鉄骨造スレート葺
    "floors": 4,
    "total_units": 4,  # 4階建、店舗・共同住宅
    "land_area_sqm": 126.11,  # 登記簿: 128番14 宅地 126.11㎡
    "building_area_sqm": 275.48,  # 1F:66.23 + 2F:69.75 + 3F:69.75 + 4F:69.75
    "year_built": 1988,  # 昭和63年10月8日新築
    "station": "大国町",
    "walk_minutes": 3,  # 地図から推定
    "current_rent_monthly": None,  # 賃料不明→利回りから逆算
    "gross_yield": None,  # 不明
    "zoning": "商業地域",  # 地図から推定（大国町駅周辺）
    "building_coverage": 80,
    "floor_area_ratio": 400,
    "land_rights": "所有権",
    "road_access": "南側公道接道",
    "management_company": None,
    "remarks": (
        "現所有者: 緑和株式会社（令和6年7月取得）。"
        "所有権移転が頻繁（R5.11→R6.2→R6.5→R6.7→R6.8の5回）。"
        "建物用途: 店舗・共同住宅。鉄骨造スレート葺4階建。"
        "根抵当権設定あり（大阪厚生信用金庫、極度額8,400万円）。"
    ),
    "property_type": "店舗付住宅",
    "units_detail": [
        {"room": "1F", "layout": "店舗", "area_sqm": 66.23, "rent": None, "status": "不明"},
        {"room": "2F", "layout": "住居", "area_sqm": 69.75, "rent": None, "status": "不明"},
        {"room": "3F", "layout": "住居", "area_sqm": 69.75, "rent": None, "status": "不明"},
        {"room": "4F", "layout": "住居", "area_sqm": 69.75, "rent": None, "status": "不明"},
    ],
    "current_owner": "緑和株式会社",
    "ownership_history": "H9相続→H21売買→R5.11売買→R6.2売買→R6.5売買→R6.7売買→R6.8売買",
    "mortgage_info": "根抵当権: 大阪厚生信用金庫 極度額8,400万円",
    "building_use": "店舗・共同住宅",
}

# 賃料推定（大国町駅徒歩3分、店舗+住居、築36年）
# 大阪市浪速区の相場から推定:
#   1F店舗(66㎡): 約20万円/月
#   2-4F住居(各70㎡): 各約8万円/月
# 合計: 約44万円/月
print("賃料が不明のため、相場から推定します。")
print("  1F 店舗 66㎡: 約20万円/月")
print("  2F 住居 70㎡: 約8万円/月")
print("  3F 住居 70㎡: 約8万円/月")
print("  4F 住居 70㎡: 約8万円/月")
print("  合計: 44万円/月（年間528万円）")
print(f"  推定表面利回り: {528/13000*100:.1f}%")
print()

property_data["current_rent_monthly"] = 44.0
property_data["gross_yield"] = round(44 * 12 / 13000 * 100, 2)

# 設定読み込み
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# 融資条件
bank = config["financing"]["regional_bank"]
loan_rate = bank["interest_rate_typical"] / 100
loan_years = bank["max_term_years"]
ltv = bank["max_ltv"]

# 鉄骨造の残耐用年数: 34年 - (2026-1988) = 34-38 = -4年 → 耐用年数超過
# ただし融資はmax(残耐用年数, 耐用年数*20%) = max(-4, 6.8) = 7年程度
print("=" * 60)
print("  大国町1丁目ビル 投資分析")
print("=" * 60)
print()

print("=== 賃貸分析 ===")
rental = analyze_rental(property_data, config, loan_rate, loan_years, ltv)
print(f"表面利回り: {rental.gross_yield}%")
print(f"実質利回り: {rental.net_yield}%")
print(f"DSCR: {rental.dscr}")
print(f"CCR: {rental.cash_on_cash}%")
print(f"IRR: {rental.irr}%")
print(f"年間CF: ¥{rental.annual_net_cf:,.0f}")
print(f"損益分岐稼働率: {rental.breakeven_occupancy}%")
print(f"総投資額: {rental.total_investment/10000:,.0f}万円")
print(f"自己資金: {rental.equity/10000:,.0f}万円")
print(f"借入額: {rental.loan_amount/10000:,.0f}万円")

print("\n=== 民泊分析 ===")
minpaku = analyze_minpaku(property_data, config, loan_rate, loan_years, ltv)
print(f"表面利回り: {minpaku.gross_yield}%")
print(f"実質利回り: {minpaku.net_yield}%")
print(f"DSCR: {minpaku.dscr}")
print(f"年間CF: ¥{minpaku.annual_net_cf:,.0f}")

print("\n=== 融資シミュレーション ===")
loans = simulate_all_banks(property_data, config)
for lr in loans:
    status = "○" if lr.available else f"× {lr.reason}"
    rec = " ★推奨" if lr.recommended else ""
    period = f" {lr.loan_years}年" if lr.available else ""
    print(f"  {lr.bank_name}: {lr.interest_rate}% {status}{period}{rec}")
    if lr.available:
        print(f"    月額¥{lr.monthly_payment:,.0f} / 年額¥{lr.annual_payment:,.0f} / 総利息¥{lr.total_interest:,.0f}")

print("\n=== 保証会社推奨 ===")
guarantees = recommend_guarantee_companies(property_data, config)
for gc in guarantees:
    print(f"  {gc.company_name}: {'★' * gc.match_score} - {gc.reason}")

print("\n=== 税務比較 ===")
tax = compare_tax(rental.annual_noi, property_data, config, loan_rate, rental.loan_amount)
print(f"推奨: {tax['recommendation']} ({tax['reason']})")
print(f"個人 税引後: ¥{tax['individual'].net_income_after_tax:,.0f}")
print(f"法人 税引後: ¥{tax['corporate'].net_income_after_tax:,.0f}")
print(f"年間減価償却: ¥{tax['depreciation_annual']:,.0f}")

print("\n=== リスク分析 ===")
risks = assess_risks(property_data, config)
for r in risks:
    print(f"  [{r.severity}] {r.category}: {r.description[:60]}")

print("\n=== 出口戦略 ===")
exits = calc_exit_strategies(rental.cashflows, rental.equity, property_data, config, loan_rate)
for es in exits:
    print(f"  {es.year}年目: 物件価値{es.property_value/10000:,.0f}万 総利益{es.total_profit/10000:,.0f}万 年率ROI{es.annualized_roi}%")

print("\n=== 投資判断 ===")
decision = make_investment_decision(rental, minpaku, risks, exits)
print(f"スコア: {decision['score']}/100")
print(f"判定: {decision['verdict']}")
print(f"詳細: {decision['verdict_detail']}")

# 感度分析
print("\n=== 感度分析 ===")
sens = sensitivity_analysis(property_data, config, loan_rate, loan_years, ltv)
print("家賃変動:")
for k, v in sens["rent"].items():
    print(f"  {k}: 実質{v['net_yield']}% CCR{v['cash_on_cash']}% DSCR{v['dscr']} CF¥{v['annual_net_cf']:,.0f}")

# レポート生成
print("\n=== レポート生成 ===")
output_dir = Path("output")

try:
    generate_pdf(
        property_data, rental, minpaku, tax, loans, guarantees,
        risks, exits, sens, decision, output_dir / "daikoku_report.pdf"
    )
    print("PDF: output/daikoku_report.pdf ✓")
except Exception as e:
    print(f"PDF生成エラー: {e}")

try:
    generate_excel(
        property_data, rental, minpaku, tax, loans,
        risks, exits, sens, decision, output_dir / "daikoku_report.xlsx"
    )
    print("Excel: output/daikoku_report.xlsx ✓")
except Exception as e:
    print(f"Excel生成エラー: {e}")

# 抽出データ保存
with open("data/daikoku_extracted.json", "w", encoding="utf-8") as f:
    json.dump(property_data, f, ensure_ascii=False, indent=2)
print("データ: data/daikoku_extracted.json ✓")

print("\n完了!")
