#!/usr/bin/env python3
"""API呼び出しなしの動作確認テスト"""

import json
from pathlib import Path
import yaml

from src.analyzer import analyze_rental, analyze_minpaku, sensitivity_analysis
from src.financing import simulate_all_banks, recommend_guarantee_companies
from src.tax_compare import compare_tax
from src.risk import assess_risks, calc_exit_strategies, make_investment_decision
from src.report_generator import generate_pdf, generate_excel

# テスト用物件データ（実際はClaude Visionが抽出）
test_property = {
    "property_name": "テスト一棟マンション",
    "address": "東京都板橋区成増1-1-1",
    "price": 5000,  # 万円
    "structure": "RC",
    "floors": 3,
    "total_units": 6,
    "land_area_sqm": 120,
    "building_area_sqm": 200,
    "year_built": 2005,
    "station": "成増",
    "walk_minutes": 8,
    "current_rent_monthly": 35,  # 万円
    "gross_yield": 8.4,
    "zoning": "第一種住居地域",
    "building_coverage": 60,
    "floor_area_ratio": 200,
    "land_rights": "所有権",
    "road_access": "南側6m公道",
    "property_type": "一棟マンション",
    "units_detail": [],
}

# 設定読み込み
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# 融資条件
bank = config["financing"]["regional_bank"]
loan_rate = bank["interest_rate_typical"] / 100
loan_years = bank["max_term_years"]
ltv = bank["max_ltv"]

print("=== 賃貸分析 ===")
rental = analyze_rental(test_property, config, loan_rate, loan_years, ltv)
print(f"表面利回り: {rental.gross_yield}%")
print(f"実質利回り: {rental.net_yield}%")
print(f"DSCR: {rental.dscr}")
print(f"CCR: {rental.cash_on_cash}%")
print(f"IRR: {rental.irr}%")
print(f"年間CF: ¥{rental.annual_net_cf:,.0f}")
print(f"損益分岐稼働率: {rental.breakeven_occupancy}%")

print("\n=== 民泊分析 ===")
minpaku = analyze_minpaku(test_property, config, loan_rate, loan_years, ltv)
print(f"表面利回り: {minpaku.gross_yield}%")
print(f"実質利回り: {minpaku.net_yield}%")
print(f"DSCR: {minpaku.dscr}")
print(f"年間CF: ¥{minpaku.annual_net_cf:,.0f}")

print("\n=== 融資シミュレーション ===")
loans = simulate_all_banks(test_property, config)
for lr in loans:
    status = "○" if lr.available else f"× {lr.reason}"
    rec = " ★推奨" if lr.recommended else ""
    print(f"  {lr.bank_name}: {lr.interest_rate}% 月額¥{lr.monthly_payment:,.0f} {status}{rec}")

print("\n=== 保証会社推奨 ===")
guarantees = recommend_guarantee_companies(test_property, config)
for gc in guarantees:
    print(f"  {gc.company_name}: {'★' * gc.match_score} - {gc.reason}")

print("\n=== 税務比較 ===")
tax = compare_tax(rental.annual_noi, test_property, config, loan_rate, rental.loan_amount)
print(f"推奨: {tax['recommendation']} ({tax['reason']})")
print(f"個人 税引後: ¥{tax['individual'].net_income_after_tax:,.0f}")
print(f"法人 税引後: ¥{tax['corporate'].net_income_after_tax:,.0f}")

print("\n=== リスク分析 ===")
risks = assess_risks(test_property, config)
for r in risks:
    print(f"  [{r.severity}] {r.category}: {r.description[:50]}")

print("\n=== 出口戦略 ===")
exits = calc_exit_strategies(rental.cashflows, rental.equity, test_property, config, loan_rate)
for es in exits:
    print(f"  {es.year}年目: 総利益¥{es.total_profit:,.0f} 年率ROI {es.annualized_roi}%")

print("\n=== 投資判断 ===")
decision = make_investment_decision(rental, minpaku, risks, exits)
print(f"スコア: {decision['score']}/100")
print(f"判定: {decision['verdict']}")
print(f"詳細: {decision['verdict_detail']}")

print("\n=== 感度分析 ===")
sens = sensitivity_analysis(test_property, config, loan_rate, loan_years, ltv)
print("家賃変動:")
for k, v in sens["rent"].items():
    print(f"  {k}: 実質{v['net_yield']}% CCR{v['cash_on_cash']}% DSCR{v['dscr']}")

# レポート生成
print("\n=== レポート生成 ===")
output_dir = Path("output")

try:
    generate_pdf(
        test_property, rental, minpaku, tax, loans, guarantees,
        risks, exits, sens, decision, output_dir / "test_report.pdf"
    )
    print("PDF: output/test_report.pdf ✓")
except Exception as e:
    print(f"PDF生成エラー: {e}")

try:
    generate_excel(
        test_property, rental, minpaku, tax, loans,
        risks, exits, sens, decision, output_dir / "test_report.xlsx"
    )
    print("Excel: output/test_report.xlsx ✓")
except Exception as e:
    print(f"Excel生成エラー: {e}")

print("\nテスト完了!")
