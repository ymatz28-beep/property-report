from pathlib import Path

from generate_search_report_common import ReportConfig, generate_report

DATA_DIR = Path("data")


def find_extra_data_paths(city_key: str) -> list[Path]:
    """Find multi-site data files for this city."""
    paths = []
    combined = DATA_DIR / f"multi_site_{city_key}_raw.txt"
    if combined.exists():
        paths.append(combined)
    else:
        for pattern in [f"rakumachi_{city_key}_raw.txt", f"yahoo_{city_key}_raw.txt", f"athome_{city_key}_raw.txt"]:
            p = DATA_DIR / pattern
            if p.exists():
                paths.append(p)
    # f-takken.com (ふれんず)
    ftakken = DATA_DIR / f"ftakken_{city_key}_raw.txt"
    if ftakken.exists():
        paths.append(ftakken)
    # R不動産
    restate = DATA_DIR / f"restate_{city_key}_raw.txt"
    if restate.exists():
        paths.append(restate)
    return paths


def main() -> None:
    config = ReportConfig(
        city_key="fukuoka",
        city_label="福岡",
        accent="#ff6b6b",
        accent_rgb="255,107,107",
        data_path=Path("data/suumo_fukuoka_raw.txt"),
        output_path=Path("output/fukuoka_search_report.html"),
        hero_conditions=[
            "福岡市博多区・中央区・南区中心",
            "価格上限 5,000万円",
            "専有面積 40-70㎡目安",
            "ペット可/相談可重視（評価項目）",
        ],
        search_condition_bullets=[
            "SUUMO + 楽待 + Yahoo不動産 + ふれんず + 福岡R不動産のマルチソース",
            "天神/中洲、博多駅前/祇園を高評価エリアとして優先",
            "ペット可は高加点（15点）、リノベ未実施は加点、仲介手数料割引も加点",
        ],
        investor_notes=[
            "法人（iUMAプロパティマネジメント）での購入を第一優先",
            "福岡は既存物件あり（筑波銀行1,540万）",
            "博多・天神エリアはインバウンド需要が高い",
            "ペット可否はスコアリング要素として評価（ハードフィルタではない）",
            "管理規約の民泊可否は個別確認が必要",
        ],
        include_osaka_r=False,
        extra_data_paths=find_extra_data_paths("fukuoka"),
    )
    out = generate_report(config)
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()

