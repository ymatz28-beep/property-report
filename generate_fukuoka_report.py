from pathlib import Path

from generate_search_report_common import ReportConfig, generate_report


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
            "天神/中洲、博多駅前/祇園を高評価エリアとして優先",
            "ペット可否はスコアリング要素（ハードフィルタではない）",
            "バス便物件は候補から除外せず、駅距離評価のみ減点",
        ],
        investor_notes=[
            "法人（iUMAプロパティマネジメント）での購入を第一優先",
            "福岡は既存物件あり（筑波銀行1,540万）",
            "博多・天神エリアはインバウンド需要が高い",
            "ペット可否はスコアリング要素として評価（ハードフィルタではない）",
            "管理規約の民泊可否は個別確認が必要",
        ],
        include_osaka_r=False,
    )
    out = generate_report(config)
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()

