from pathlib import Path

from generate_search_report_common import ReportConfig, generate_report

DATA_DIR = Path("data")


def find_extra_data_paths(city_key: str) -> list[Path]:
    """Find multi-site data files for this city."""
    paths = []
    combined = DATA_DIR / f"multi_site_{city_key}_raw.txt"
    if combined.exists():
        paths.append(combined)
        return paths  # Combined file has everything
    # Fallback: individual site files
    for pattern in [f"rakumachi_{city_key}_raw.txt", f"yahoo_{city_key}_raw.txt", f"athome_{city_key}_raw.txt"]:
        p = DATA_DIR / pattern
        if p.exists():
            paths.append(p)
    return paths


def main() -> None:
    config = ReportConfig(
        city_key="osaka",
        city_label="大阪",
        accent="#6ee7ff",
        accent_rgb="110,231,255",
        data_path=Path("data/suumo_osaka_v2_raw.txt"),
        output_path=Path("output/osaka_search_report.html"),
        hero_conditions=[
            "大阪市西区・北区・中央区中心",
            "価格上限 5,000万円",
            "専有面積 40-70㎡目安",
            "ペット可/相談可優先",
        ],
        search_condition_bullets=[
            "大阪R不動産の4件を別ソースとして追加（民泊可否メモ付き）",
            "SUUMO + 楽待 + Yahoo不動産のマルチソース",
            "北堀江/南堀江を最優先、天満・中津・心斎橋周辺も重点評価",
            "ペット可は高加点（15点）、リノベ未実施は加点、仲介手数料割引も加点",
        ],
        investor_notes=[
            "法人（iUMAプロパティマネジメント）での購入を第一優先",
            "セゾンファンデックス・筑波銀行の融資枠を活用",
            "特区民泊の制度期限は2026/5/29。間に合わなければ簡易宿所許可で対応",
            "管理規約の民泊可否は個別確認が必要",
            "戸建て・メゾネットは管理規約制約なしのため並行検索推奨",
        ],
        include_osaka_r=True,
        extra_data_paths=find_extra_data_paths("osaka"),
    )
    out = generate_report(config)
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()

