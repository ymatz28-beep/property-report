from pathlib import Path

from generate_search_report_common import ReportConfig, generate_report

DATA_DIR = Path("data")


def find_extra_data_paths(city_key: str) -> list[Path]:
    """Find individual enriched source files for this city.

    Always loads individual site files (which contain enriched maintenance data)
    instead of multi_site_*_raw.txt (which is a stale merge without enrichment).
    """
    paths = []
    # Individual enriched source files (preferred over multi_site combined)
    for prefix in ["rakumachi", "yahoo", "athome", "cowcamo"]:
        p = DATA_DIR / f"{prefix}_{city_key}_raw.txt"
        if p.exists():
            paths.append(p)
    # R不動産
    restate = DATA_DIR / f"restate_{city_key}_raw.txt"
    if restate.exists():
        paths.append(restate)
    # LIFULL HOME'S
    lifull = DATA_DIR / f"lifull_{city_key}_raw.txt"
    if lifull.exists():
        paths.append(lifull)
    return paths


def main() -> None:
    config = ReportConfig(
        city_key="tokyo",
        city_label="東京",
        accent="#a78bfa",
        accent_rgb="167,139,250",
        data_path=Path("data/suumo_tokyo_raw.txt"),
        output_path=Path("output/minpaku-tokyo.html"),
        hero_conditions=[
            "渋谷区・新宿区・目黒区・台東区・豊島区中心",
            "価格上限 5,000万円",
            "専有面積 40-70㎡目安",
            "ペット可/相談可優先",
        ],
        search_condition_bullets=[
            "SUUMO + 楽待 + Yahoo不動産 + athome + LIFULL + カウカモのマルチソース",
            "渋谷/恵比寿/新宿を最優先、浅草/池袋/上野も重点評価",
            "ペット可は高加点（+15）、不明は-15。リノベ未実施は加点、仲介手数料割引も加点",
        ],
        investor_notes=[
            "法人（iUMAプロパティマネジメント）での購入を第一優先",
            "セゾンファンデックス・筑波銀行の融資枠を活用",
            "東京は住宅宿泊事業法（年間180日）or 簡易宿所許可で民泊対応",
            "ペット可否はスコアリング要素として評価（ハードフィルタではない）",
            "管理規約の民泊可否は個別確認が必要",
        ],
        include_osaka_r=False,
        extra_data_paths=find_extra_data_paths("tokyo"),
    )
    out = generate_report(config)
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()
