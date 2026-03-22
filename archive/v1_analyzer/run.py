#!/usr/bin/env python3
"""
不動産投資分析システム - メイン実行ファイル

使い方:
  1. input/ フォルダに物件チラシ画像またはPDFを配置
  2. python run.py を実行
  3. output/ フォルダにレポートが生成される

環境変数:
  ANTHROPIC_API_KEY: Anthropic APIキー（config.yamlでも設定可）
"""

import sys
import json
import datetime
from pathlib import Path

import yaml

from src.extractor import (
    collect_input_files, extract_from_images, fill_defaults, prompt_missing_info
)
from src.analyzer import analyze_rental, analyze_minpaku, sensitivity_analysis
from src.financing import simulate_all_banks, recommend_guarantee_companies
from src.tax_compare import compare_tax
from src.risk import assess_risks, calc_exit_strategies, make_investment_decision
from src.report_generator import generate_pdf, generate_excel
from src.tax_extractor import (
    FinancialProfile, extract_from_tax_pdfs, save_financial_profile, load_financial_profile
)


BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fetch_investor_profile(config: dict, api_key: str | None) -> FinancialProfile | None:
    """投資家の財務プロフィールを取得（Google Drive → ローカル → キャッシュの順）"""
    # 1. キャッシュ済みプロフィール確認
    cache_path = DATA_DIR / "investor_profile.json"
    cached = load_financial_profile(cache_path)

    # 2. Google Driveから取得
    gdrive_config = config.get("google_drive", {})
    if gdrive_config.get("enabled") and gdrive_config.get("folder_id"):
        try:
            from src.gdrive import fetch_tax_returns, check_available
            if check_available():
                print("       Google Driveから確定申告書類を取得中...")
                pdf_paths, metadata = fetch_tax_returns(config)
                if pdf_paths:
                    profile = extract_from_tax_pdfs(pdf_paths, config["api"]["model"], api_key)
                    save_financial_profile(profile, cache_path)
                    print(f"       財務プロフィール保存: {cache_path.name}")
                    return profile
            else:
                print("       Google Drive: 認証情報なし（スキップ）")
        except Exception as e:
            print(f"       Google Drive取得エラー: {e}")

    # 3. ローカルPDFから取得（input/ に確定申告PDFがある場合）
    local_tax_pdfs = list(INPUT_DIR.glob("*確定申告*")) + list(INPUT_DIR.glob("*kakutei*"))
    local_tax_pdfs += list(INPUT_DIR.glob("*tax_return*")) + list(INPUT_DIR.glob("*源泉徴収*"))
    local_tax_pdfs = [p for p in local_tax_pdfs if p.suffix.lower() == ".pdf"]

    if local_tax_pdfs:
        try:
            print(f"       ローカル確定申告PDF検出: {len(local_tax_pdfs)}ファイル")
            profile = extract_from_tax_pdfs(local_tax_pdfs, config["api"]["model"], api_key)
            save_financial_profile(profile, cache_path)
            print(f"       財務プロフィール保存: {cache_path.name}")
            return profile
        except Exception as e:
            print(f"       ローカルPDF抽出エラー: {e}")

    # 4. キャッシュがあればそれを使用
    if cached:
        print(f"       キャッシュ済み財務プロフィールを使用（{cached.fetch_date[:10] if cached.fetch_date else '日付不明'}）")
        return cached

    return None


def main():
    print("=" * 60)
    print("  不動産投資分析システム")
    print("=" * 60)
    print()

    # 設定読み込み
    config = load_config()

    # APIキー設定（config.yaml → 環境変数の優先順位）
    api_key = config["api"].get("api_key") or None
    if api_key:
        import os
        os.environ["ANTHROPIC_API_KEY"] = api_key

    if not api_key and not __import__("os").environ.get("ANTHROPIC_API_KEY"):
        print("\nエラー: APIキーが設定されていません。")
        print("  方法1: config.yaml の api.api_key に設定")
        print("  方法2: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    print("[1/9] 設定ファイル読み込み完了")

    # ファイル検出（画像 + PDF対応）
    print("[2/9] 入力ファイル検出中...")
    images = collect_input_files(INPUT_DIR)
    if not images:
        print(f"\nエラー: input/ フォルダにファイルがありません。")
        print(f"  対応形式: .jpg, .jpeg, .png, .gif, .webp, .pdf")
        print(f"  パス: {INPUT_DIR}")
        sys.exit(1)

    print(f"       処理対象: {len(images)}ページ")

    # 投資家財務情報取得
    print("[3/9] 投資家財務情報を取得中...")
    investor_profile = _fetch_investor_profile(config, api_key)
    if investor_profile:
        print(f"       年収: {investor_profile.salary_income:,}円")
        print(f"       不動産所得: {investor_profile.real_estate_income:,}円")
        print(f"       既存借入残高: {investor_profile.total_loan_balance:,}円")
        print(f"       保有物件数: {investor_profile.property_count}件")
    else:
        print("       財務情報なし（従来モードで分析）")

    # 画像から物件情報抽出
    print("[4/9] 物件情報を抽出中（Claude Vision API）...")
    try:
        property_data = extract_from_images(images, config["api"]["model"], api_key)
    except Exception as e:
        print(f"\nエラー: 情報抽出に失敗しました。")
        print(f"  詳細: {e}")
        sys.exit(1)

    # 不足情報の対話的入力
    property_data = prompt_missing_info(property_data)
    property_data = fill_defaults(property_data)

    # 抽出データ保存
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    data_path = DATA_DIR / f"extracted_{timestamp}.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(property_data, f, ensure_ascii=False, indent=2)
    print(f"       抽出データ保存: {data_path.name}")

    prop_name = property_data.get("property_name", "不明物件")
    price = property_data.get("price", 0)
    rent = property_data.get("current_rent_monthly", 0)
    print(f"       物件名: {prop_name}")
    print(f"       価格: {price:,.0f}万円 / 月額賃料: {rent:,.1f}万円")

    if not price or not rent:
        print("\n警告: 価格または賃料が不足しています。分析精度が低下します。")

    # 融資条件（デフォルト: 地銀ベース）
    default_bank = config["financing"]["regional_bank"]
    loan_rate = default_bank["interest_rate_typical"] / 100
    loan_years = default_bank["max_term_years"]
    ltv = default_bank["max_ltv"]

    # 賃貸分析
    print("[5/9] 賃貸収支分析中...")
    rental_result = analyze_rental(property_data, config, loan_rate, loan_years, ltv)

    # 民泊分析
    print("[6/9] 民泊収支分析中...")
    minpaku_result = analyze_minpaku(property_data, config, loan_rate, loan_years, ltv)

    # 感度分析・融資シミュレーション
    print("[7/9] 感度分析・融資シミュレーション中...")
    sens_rental = sensitivity_analysis(property_data, config, loan_rate, loan_years, ltv, mode="rental")

    # 融資シミュレーション（investor_profile反映）
    loan_results = simulate_all_banks(property_data, config, use_minpaku=False, investor_profile=investor_profile)
    guarantee_results = recommend_guarantee_companies(property_data, config)

    # 税務比較（investor_profile反映）
    tax_comparison = compare_tax(
        rental_result.annual_noi, property_data, config,
        loan_rate, rental_result.loan_amount, investor_profile=investor_profile
    )

    # リスク分析（investor_profile反映）
    print("[8/9] リスク分析・出口戦略策定中...")
    risks = assess_risks(property_data, config, investor_profile=investor_profile)
    exit_scenarios = calc_exit_strategies(
        rental_result.cashflows, rental_result.equity, property_data, config, loan_rate
    )

    # 投資判断
    decision = make_investment_decision(rental_result, minpaku_result, risks, exit_scenarios)

    # レポート生成
    print("[9/9] レポート生成中...")

    pdf_path = OUTPUT_DIR / f"report_{timestamp}.pdf"
    excel_path = OUTPUT_DIR / f"report_{timestamp}.xlsx"

    try:
        generate_pdf(
            property_data, rental_result, minpaku_result, tax_comparison,
            loan_results, guarantee_results, risks, exit_scenarios,
            sens_rental, decision, pdf_path,
        )
        print(f"       PDF: {pdf_path.name}")
    except Exception as e:
        print(f"       PDF生成エラー: {e}")

    try:
        generate_excel(
            property_data, rental_result, minpaku_result, tax_comparison,
            loan_results, risks, exit_scenarios, sens_rental, decision,
            excel_path,
        )
        print(f"       Excel: {excel_path.name}")
    except Exception as e:
        print(f"       Excel生成エラー: {e}")

    # 結果サマリー
    print()
    print("=" * 60)
    print(f"  分析完了: {prop_name}")
    print("=" * 60)
    print()
    print(f"  【投資判断】 {decision['verdict']} （スコア: {decision['score']}/100）")
    print(f"  {decision['verdict_detail']}")
    print()
    print(f"  ■ 賃貸運用")
    print(f"    表面利回り: {rental_result.gross_yield}%")
    print(f"    実質利回り: {rental_result.net_yield}%")
    print(f"    DSCR: {rental_result.dscr}")
    print(f"    年間CF: ¥{rental_result.annual_net_cf:,.0f}")
    print()
    print(f"  ■ 民泊運用")
    print(f"    表面利回り: {minpaku_result.gross_yield}%")
    print(f"    実質利回り: {minpaku_result.net_yield}%")
    print(f"    DSCR: {minpaku_result.dscr}")
    print(f"    年間CF: ¥{minpaku_result.annual_net_cf:,.0f}")
    print()
    print(f"  ■ 税務")
    print(f"    推奨: {tax_comparison['recommendation']}（{tax_comparison['reason']}）")
    print()
    print(f"  ■ 推奨金融機関")
    for lr in loan_results:
        if lr.recommended:
            print(f"    ★ {lr.bank_name}（金利{lr.interest_rate}%）")
    print()
    print(f"  レポート出力先: {OUTPUT_DIR}/")
    print()


if __name__ == "__main__":
    main()
