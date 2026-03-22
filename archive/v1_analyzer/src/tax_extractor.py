"""確定申告PDF から財務情報を自動抽出するモジュール（Claude Vision使用）"""

import anthropic
import base64
import json
import re
import tempfile
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime


TAX_EXTRACTION_PROMPT = """この確定申告書類（または関連する税務書類）の画像から、以下の財務情報をJSON形式で抽出してください。
読み取れない項目はnullとしてください。

{
  "tax_year": "申告年度（例: 2024）",
  "document_type": "書類の種類（確定申告書B/青色申告決算書/収支内訳書/源泉徴収票/その他）",

  "income": {
    "salary": 給与所得の金額（円）,
    "salary_employer": "勤務先名",
    "real_estate_revenue": 不動産収入の金額（円）,
    "real_estate_income": 不動産所得の金額（円）,
    "business_income": 事業所得の金額（円）,
    "dividend_income": 配当所得の金額（円）,
    "other_income": その他の所得（円）,
    "total_income": 合計所得金額（円）
  },

  "deductions": {
    "blue_return_special": 青色申告特別控除額（円）,
    "depreciation_total": 減価償却費合計（円）,
    "loan_interest": 借入金利子合計（円）,
    "management_fees": 管理費・委託費合計（円）,
    "repair_costs": 修繕費合計（円）,
    "insurance": 保険料合計（円）,
    "property_tax": 租税公課合計（円）,
    "other_expenses": その他経費合計（円）,
    "total_expenses": 必要経費合計（円）
  },

  "tax": {
    "taxable_income": 課税される所得金額（円）,
    "income_tax": 所得税額（円）,
    "resident_tax": 住民税額（円）,
    "total_tax": 納付税額合計（円）
  },

  "real_estate_detail": {
    "properties": [
      {
        "name": "物件名または所在地",
        "revenue": 年間収入（円）,
        "expenses": 年間経費（円）,
        "income": 所得（円）
      }
    ],
    "total_revenue": 不動産収入合計（円）,
    "total_expenses": 不動産経費合計（円）,
    "total_income": 不動産所得合計（円）
  },

  "loans": {
    "items": [
      {
        "lender": "借入先",
        "balance": 残高（円）,
        "annual_interest": 年間利息（円）,
        "property": "対象物件"
      }
    ],
    "total_balance": 借入残高合計（円）
  },

  "depreciation_detail": [
    {
      "asset_name": "資産名",
      "acquisition_cost": 取得価額（円）,
      "useful_life": 耐用年数,
      "annual_amount": 年間償却額（円）,
      "remaining_value": 未償却残高（円）
    }
  ]
}

重要:
- 金額は円単位の数値で返してください（カンマなし）
- 和暦は西暦に変換してください
- 複数ページにまたがる場合は全ページの情報を統合してください
- 確定申告書B の表面・裏面、青色申告決算書の各ページを想定しています
- JSONのみを返してください。説明文は不要です。
"""


@dataclass
class FinancialProfile:
    """確定申告から抽出した財務プロフィール"""
    tax_year: int | None = None
    fetch_date: str = ""

    # 所得
    salary_income: int = 0
    salary_employer: str = ""
    real_estate_revenue: int = 0
    real_estate_income: int = 0
    total_income: int = 0

    # 経費・控除
    blue_return_deduction: int = 0
    depreciation_total: int = 0
    loan_interest_total: int = 0
    total_expenses: int = 0

    # 税
    taxable_income: int = 0
    total_tax: int = 0

    # 不動産詳細
    property_count: int = 0
    properties: list = field(default_factory=list)

    # 借入
    total_loan_balance: int = 0
    loans: list = field(default_factory=list)

    # 減価償却
    depreciation_items: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def extract_from_tax_pdfs(pdf_paths: list[Path], model: str, api_key: str | None = None) -> FinancialProfile:
    """確定申告PDFから財務情報を抽出"""
    from src.extractor import pdf_to_images

    # PDF → 画像変換
    all_images = []
    for pdf_path in pdf_paths:
        images = pdf_to_images(pdf_path, dpi=200)
        all_images.extend(images)
        print(f"       {pdf_path.name}: {len(images)}ページ")

    if not all_images:
        raise ValueError("PDFから画像を抽出できませんでした")

    # Claude Vision APIで抽出
    client = anthropic.Anthropic(**{"api_key": api_key} if api_key else {})
    all_results = []

    # 5ページずつバッチ処理
    for i in range(0, len(all_images), 5):
        batch = all_images[i:i + 5]
        batch_num = i // 5 + 1
        total_batches = (len(all_images) + 4) // 5
        print(f"       抽出中... ({batch_num}/{total_batches})")

        content = []
        for img_path in batch:
            img_data = base64.standard_b64encode(img_path.read_bytes()).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_data,
                },
            })

        content.append({
            "type": "text",
            "text": "これらは同一納税者の確定申告関連書類です。全ページの情報を統合してください。\n\n"
                    + TAX_EXTRACTION_PROMPT,
        })

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        text = response.content[0].text
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                all_results.append(json.loads(json_match.group()))
            except json.JSONDecodeError:
                pass

    if not all_results:
        raise ValueError("確定申告書類から情報を抽出できませんでした")

    # 結果をマージしてFinancialProfileに変換
    merged = _merge_tax_results(all_results)
    return _to_financial_profile(merged)


def _merge_tax_results(results: list[dict]) -> dict:
    """複数バッチの抽出結果をマージ"""
    merged = {}
    for result in results:
        _deep_merge(merged, result)
    return merged


def _deep_merge(base: dict, update: dict):
    """ネストされたdictのマージ（null以外の値を優先）"""
    for key, value in update.items():
        if value is None:
            continue
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        elif key in base and isinstance(base[key], list) and isinstance(value, list):
            # リストは結合（重複排除は省略）
            base[key].extend(value)
        elif key not in base or base[key] is None:
            base[key] = value
        elif isinstance(value, (int, float)) and value > 0 and (not isinstance(base[key], (int, float)) or base[key] == 0):
            base[key] = value


def _to_financial_profile(data: dict) -> FinancialProfile:
    """抽出データをFinancialProfileに変換"""
    income = data.get("income", {})
    deductions = data.get("deductions", {})
    tax = data.get("tax", {})
    re_detail = data.get("real_estate_detail", {})
    loans_data = data.get("loans", {})

    profile = FinancialProfile(
        tax_year=_parse_int(data.get("tax_year")),
        fetch_date=datetime.now().isoformat(),
        salary_income=_parse_int(income.get("salary")),
        salary_employer=income.get("salary_employer", ""),
        real_estate_revenue=_parse_int(income.get("real_estate_revenue") or re_detail.get("total_revenue")),
        real_estate_income=_parse_int(income.get("real_estate_income") or re_detail.get("total_income")),
        total_income=_parse_int(income.get("total_income")),
        blue_return_deduction=_parse_int(deductions.get("blue_return_special")),
        depreciation_total=_parse_int(deductions.get("depreciation_total")),
        loan_interest_total=_parse_int(deductions.get("loan_interest")),
        total_expenses=_parse_int(deductions.get("total_expenses")),
        taxable_income=_parse_int(tax.get("taxable_income")),
        total_tax=_parse_int(tax.get("total_tax")),
        property_count=len(re_detail.get("properties", [])),
        properties=re_detail.get("properties", []),
        total_loan_balance=_parse_int(loans_data.get("total_balance")),
        loans=loans_data.get("items", []),
        depreciation_items=data.get("depreciation_detail", []),
    )

    return profile


def _parse_int(value) -> int:
    """値をint に変換（None/文字列対応）"""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[,\s円¥]", "", value)
        try:
            return int(cleaned)
        except ValueError:
            return 0
    return 0


def save_financial_profile(profile: FinancialProfile, output_path: Path):
    """財務プロフィールをJSONで保存"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)


def load_financial_profile(path: Path) -> FinancialProfile | None:
    """保存済み財務プロフィールを読み込み"""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    profile = FinancialProfile()
    for key, value in data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    return profile
