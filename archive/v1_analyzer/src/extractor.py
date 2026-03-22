"""物件チラシ画像・PDFからの情報抽出モジュール（Claude Vision API使用）"""

import anthropic
import base64
import json
import re
import tempfile
from pathlib import Path


EXTRACTION_PROMPT = """この不動産関連書類の画像から、以下の情報をJSON形式で抽出してください。
書類の種類（物件チラシ、登記簿謄本、重要事項説明書、地図等）を問わず、読み取れる情報をすべて抽出してください。
読み取れない項目はnullとしてください。

必須項目:
{
  "property_name": "物件名（建物名がなければ所在地から生成）",
  "address": "所在地",
  "price": 物件価格（万円単位の数値。記載がなければnull）,
  "structure": "構造（RC/SRC/木造/軽量鉄骨/重量鉄骨/鉄骨造）",
  "floors": 階数,
  "total_units": 総戸数,
  "land_area_sqm": 土地面積（㎡）,
  "building_area_sqm": 建物延床面積（㎡。各階合計）,
  "year_built": 築年（西暦。昭和63年→1988、平成5年→1993のように変換）,
  "station": "最寄り駅",
  "walk_minutes": 駅徒歩分数,
  "current_rent_monthly": 現行月額賃料合計（万円）,
  "gross_yield": 表面利回り（%）,
  "zoning": "用途地域",
  "building_coverage": 建蔽率（%）,
  "floor_area_ratio": 容積率（%）,
  "land_rights": "土地権利（所有権/借地権）",
  "road_access": "接道状況",
  "management_company": "管理会社",
  "remarks": "備考・特記事項（登記の注意点、抵当権情報、所有権移転履歴等があれば記載）",
  "property_type": "物件種別（一棟マンション/一棟アパート/区分マンション/戸建/店舗付住宅/事務所ビル）",
  "units_detail": [
    {"room": "部屋番号", "layout": "間取り", "area_sqm": 面積, "rent": 月額賃料, "status": "入居中/空室"}
  ],
  "current_owner": "現所有者（登記簿から読み取れる場合）",
  "ownership_history": "所有権移転履歴の概要",
  "mortgage_info": "抵当権・根抵当権の情報",
  "building_use": "建物用途（店舗・共同住宅等）"
}

重要:
- 価格は万円単位の数値で返してください（例: 5000万円 → 5000）
- 利回りは%の数値で返してください（例: 8.5% → 8.5）
- 面積は㎡の数値で返してください
- 和暦は西暦に変換してください（昭和63年→1988、令和6年→2024）
- 登記簿の場合、床面積は各階の合計を building_area_sqm に入れてください
- JSONのみを返してください。説明文は不要です。
"""


def get_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")


def pdf_to_images(pdf_path: Path, dpi: int = 200) -> list[Path]:
    """PDFを画像に変換"""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    image_paths = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="property_"))

    for page_num in range(len(doc)):
        page = doc[page_num]
        # DPI設定でレンダリング
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_path = tmp_dir / f"page_{page_num + 1}.png"
        pix.save(str(img_path))
        image_paths.append(img_path)

    doc.close()
    return image_paths


def collect_input_files(input_dir: Path) -> list[Path]:
    """input/フォルダから画像・PDFファイルを収集（PDFは画像に変換）"""
    supported_images = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    all_images = []

    for p in sorted(input_dir.iterdir()):
        if p.name.startswith("."):
            continue
        if p.suffix.lower() in supported_images:
            all_images.append(p)
        elif p.suffix.lower() == ".pdf":
            print(f"       PDF検出: {p.name} → 画像に変換中...")
            converted = pdf_to_images(p)
            print(f"       → {len(converted)}ページを変換")
            all_images.extend(converted)

    return all_images


def extract_from_image(image_path: Path, model: str, api_key: str | None = None) -> dict:
    """単一画像から物件情報を抽出"""
    client = anthropic.Anthropic(**{"api_key": api_key} if api_key else {})

    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
    media_type = get_media_type(image_path)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    )

    text = response.content[0].text
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        raise ValueError(f"JSONの抽出に失敗しました: {text[:200]}")

    return json.loads(json_match.group())


def extract_from_images(image_paths: list[Path], model: str, api_key: str | None = None) -> dict:
    """複数画像から物件情報を抽出・統合"""
    if len(image_paths) == 1:
        return extract_from_image(image_paths[0], model, api_key)

    client = anthropic.Anthropic(**{"api_key": api_key} if api_key else {})

    # 画像が多い場合はバッチ処理（APIの制限対策）
    # 最大5画像ずつ送信して統合
    max_per_batch = 5
    all_results = []

    for i in range(0, len(image_paths), max_per_batch):
        batch = image_paths[i:i + max_per_batch]

        content = []
        for path in batch:
            image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
            media_type = get_media_type(path)
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                }
            )

        prompt = (
            "これらは同一物件に関する書類（チラシ、登記簿、地図等）の画像です。"
            "全ページの情報を統合して1つのJSONにまとめてください。\n\n"
            + EXTRACTION_PROMPT
        )
        content.append({"type": "text", "text": prompt})

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        text = response.content[0].text
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            all_results.append(json.loads(json_match.group()))

    if not all_results:
        raise ValueError("どの画像からも情報を抽出できませんでした")

    # 複数バッチ結果を統合
    if len(all_results) == 1:
        return all_results[0]

    return _merge_results(all_results)


def _merge_results(results: list[dict]) -> dict:
    """複数の抽出結果を統合（null以外の値を優先）"""
    merged = {}
    for result in results:
        for key, value in result.items():
            if value is not None and (key not in merged or merged[key] is None):
                merged[key] = value
            elif key == "remarks" and value and merged.get(key):
                merged[key] = merged[key] + "。" + value
    return merged


def prompt_missing_info(data: dict) -> dict:
    """不足している重要情報をユーザーに入力してもらう"""
    print()
    print("  ─── 抽出結果の確認 ───")
    print(f"  物件名: {data.get('property_name', 'N/A')}")
    print(f"  所在地: {data.get('address', 'N/A')}")
    print(f"  構造: {data.get('structure', 'N/A')}")
    print(f"  築年: {data.get('year_built', 'N/A')}")
    print(f"  建物面積: {data.get('building_area_sqm', 'N/A')}㎡")
    print(f"  土地面積: {data.get('land_area_sqm', 'N/A')}㎡")
    print(f"  価格: {data.get('price', 'N/A')}万円")
    print(f"  月額賃料: {data.get('current_rent_monthly', 'N/A')}万円")
    print(f"  表面利回り: {data.get('gross_yield', 'N/A')}%")
    print()

    # 価格が不明な場合
    if not data.get("price"):
        print("  ⚠ 物件価格が書類から読み取れませんでした。")
        val = input("  物件価格（万円）を入力してください: ").strip()
        if val:
            data["price"] = float(val)

    # 月額賃料が不明な場合
    if not data.get("current_rent_monthly"):
        print("  ⚠ 月額賃料が書類から読み取れませんでした。")
        val = input("  月額賃料合計（万円）を入力してください: ").strip()
        if val:
            data["current_rent_monthly"] = float(val)

    # 最寄り駅が不明な場合
    if not data.get("station"):
        val = input("  最寄り駅を入力してください（例: 大国町）: ").strip()
        if val:
            data["station"] = val

    # 徒歩分数
    if not data.get("walk_minutes") and data.get("station"):
        val = input(f"  {data['station']}駅からの徒歩分数: ").strip()
        if val:
            data["walk_minutes"] = int(val)

    print()
    return data


def fill_defaults(data: dict) -> dict:
    """不足データにデフォルト値を設定"""
    defaults = {
        "structure": "RC",
        "total_units": 1,
        "vacancy_rate": 0.05,
        "land_rights": "所有権",
        "property_type": "一棟マンション",
        "units_detail": [],
    }
    for k, v in defaults.items():
        if data.get(k) is None:
            data[k] = v

    # 構造名の正規化
    structure = data.get("structure", "")
    if "鉄骨造" in structure or "鉄骨" in structure:
        if "鉄筋" in structure or "鉄骨鉄筋" in structure:
            data["structure"] = "SRC"
        else:
            data["structure"] = "重量鉄骨"
    elif "鉄筋コンクリート" in structure:
        data["structure"] = "RC"
    elif "木造" in structure:
        data["structure"] = "木造"

    # 表面利回りから月額賃料を逆算
    if data.get("current_rent_monthly") is None and data.get("gross_yield") and data.get("price"):
        annual_rent = data["price"] * (data["gross_yield"] / 100)
        data["current_rent_monthly"] = round(annual_rent / 12, 1)

    # 月額賃料から表面利回りを計算
    if data.get("gross_yield") is None and data.get("current_rent_monthly") and data.get("price"):
        annual_rent = data["current_rent_monthly"] * 12
        data["gross_yield"] = round(annual_rent / data["price"] * 100, 2)

    return data
