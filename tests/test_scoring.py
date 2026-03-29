"""Regression tests for generate_search_report_common.py scoring functions.

Run with:
    .venv/bin/python -m pytest tests/test_scoring.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make property-analyzer root importable without installing
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
# Also add Projects root so `lib` is importable
_PROJECTS = _ROOT.parent
if str(_PROJECTS) not in sys.path:
    sys.path.insert(0, str(_PROJECTS))

import pytest

from generate_search_report_common import (
    PropertyRow,
    ReportConfig,
    area_score,
    budget_score,
    classify_location_fukuoka,
    classify_location_osaka,
    classify_location_tokyo,
    earthquake_score,
    layout_score,
    maintenance_fee_score,
    pet_score_for_row,
    score_row,
    station_score,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_row(**kwargs) -> PropertyRow:
    """Build a minimal PropertyRow with sensible defaults."""
    defaults = dict(
        source="test",
        name="テストマンション",
        price_text="2000万円",
        location="福岡市中央区",
        area_text="50m2",
        built_text="2000年1月",
        station_text="天神 徒歩5分",
        layout="1LDK",
        url="https://example.com/test",
        price_man=2000,
        area_sqm=50.0,
        built_year=2000,
        built_month=1,
        walk_min=5,
        maintenance_fee=15000,
        pet_status="可",
        minpaku_status="",
    )
    defaults.update(kwargs)
    return PropertyRow(**defaults)


def make_config(city_key: str = "fukuoka") -> ReportConfig:
    return ReportConfig(
        city_key=city_key,
        city_label="テスト市",
        accent="#fff",
        accent_rgb="255,255,255",
        data_path=Path("/tmp/dummy.json"),
        output_path=Path("/tmp/dummy_out.html"),
        hero_conditions=[],
        search_condition_bullets=[],
        investor_notes=[],
    )


# ===========================================================================
# area_score
# ===========================================================================

class TestAreaScore:
    def test_none_returns_zero(self):
        assert area_score(None) == 0

    def test_sweet_spot_40_to_60(self):
        assert area_score(40.0) == 15
        assert area_score(50.0) == 15
        assert area_score(59.9) == 15

    def test_boundary_60_exact(self):
        # 60㎡ falls in [60, 70) → 10
        assert area_score(60.0) == 10

    def test_small_studio_25_to_40(self):
        """25-40㎡ = 10 (short-term rental viable)."""
        assert area_score(25.0) == 10
        assert area_score(30.0) == 10
        assert area_score(39.9) == 10

    def test_large_60_to_70(self):
        assert area_score(65.0) == 10

    def test_very_large_70_plus(self):
        assert area_score(70.0) == 5
        assert area_score(100.0) == 5

    def test_too_small_under_25(self):
        """<25㎡ = -5 (too small for viable use)."""
        assert area_score(24.9) == -5
        assert area_score(10.0) == -5
        assert area_score(0.1) == -5

    def test_boundary_25_exact(self):
        # 25.0 is in [25, 40) → 10, not -5
        assert area_score(25.0) == 10

    def test_boundary_40_exact(self):
        # 40.0 is in [40, 60) → 15
        assert area_score(40.0) == 15


# ===========================================================================
# earthquake_score
# ===========================================================================

class TestEarthquakeScore:
    def test_none_year_returns_zero(self):
        assert earthquake_score(None, None) == 0

    def test_before_1981_returns_zero(self):
        assert earthquake_score(1980, 12) == 0
        assert earthquake_score(1970, None) == 0

    def test_after_1981_returns_15(self):
        assert earthquake_score(1982, 1) == 15
        assert earthquake_score(2000, 6) == 15
        assert earthquake_score(2020, None) == 15

    def test_1981_before_july_returns_zero(self):
        # New seismic standard took effect June 1981 → month < 7 means old standard
        assert earthquake_score(1981, 1) == 0
        assert earthquake_score(1981, 6) == 0

    def test_1981_july_and_after_returns_15(self):
        assert earthquake_score(1981, 7) == 15
        assert earthquake_score(1981, 12) == 15

    def test_1981_none_month_defaults_to_january(self):
        # month defaults to 1 (January) → < 7 → 0
        assert earthquake_score(1981, None) == 0


# ===========================================================================
# station_score
# ===========================================================================

class TestStationScore:
    def test_none_returns_zero(self):
        assert station_score(None) == 0

    def test_within_5_minutes(self):
        assert station_score(1) == 15
        assert station_score(5) == 15

    def test_6_to_10_minutes(self):
        assert station_score(6) == 10
        assert station_score(10) == 10

    def test_11_to_15_minutes(self):
        assert station_score(11) == -5
        assert station_score(15) == -5

    def test_16_to_20_minutes(self):
        assert station_score(16) == -15
        assert station_score(20) == -15

    def test_over_20_minutes(self):
        """station >20min = -15 (not -25, excessive penalty was reduced)."""
        assert station_score(21) == -15
        assert station_score(30) == -15
        assert station_score(60) == -15

    def test_boundary_5_exact(self):
        assert station_score(5) == 15

    def test_boundary_10_exact(self):
        assert station_score(10) == 10

    def test_boundary_15_exact(self):
        assert station_score(15) == -5

    def test_boundary_20_exact(self):
        assert station_score(20) == -15


# ===========================================================================
# layout_score
# ===========================================================================

class TestLayoutScore:
    def test_2ldk(self):
        assert layout_score("2LDK") == 10

    def test_3ldk(self):
        assert layout_score("3LDK") == 10

    def test_1ldk(self):
        assert layout_score("1LDK") == 5

    def test_1k_returns_zero(self):
        assert layout_score("1K") == 0

    def test_studio_returns_zero(self):
        assert layout_score("ワンルーム") == 0

    def test_empty_string_returns_zero(self):
        assert layout_score("") == 0

    def test_3ldk_with_suffix(self):
        assert layout_score("3LDK+S") == 10

    def test_2ldk_lowercase_no_match(self):
        # regex uses uppercase [23]LDK — lowercase won't match
        assert layout_score("2ldk") == 0


# ===========================================================================
# classify_location_osaka
# ===========================================================================

class TestClassifyLocationOsaka:
    def test_kitahorie(self):
        label, score = classify_location_osaka("大阪市西区北堀江")
        assert label == "北堀江/南堀江"
        assert score == 15

    def test_nakatsu(self):
        label, score = classify_location_osaka("大阪市北区中津")
        assert label == "中津/中崎町"
        assert score == 12

    def test_umeda(self):
        label, score = classify_location_osaka("大阪市北区梅田")
        assert label == "梅田/大淀/福島"
        assert score == 10

    def test_tanimachi(self):
        label, score = classify_location_osaka("大阪市中央区谷町")
        assert label == "谷町"
        assert score == 8

    def test_other_returns_positive_5(self):
        """osaka Other = +5 (intentionally positive, unlike fukuoka/tokyo at 0)."""
        label, score = classify_location_osaka("大阪市平野区")
        assert label == "Other"
        assert score == 5

    def test_empty_string_returns_other(self):
        label, score = classify_location_osaka("")
        assert label == "Other"
        assert score == 5


# ===========================================================================
# classify_location_fukuoka
# ===========================================================================

class TestClassifyLocationFukuoka:
    def test_hakata(self):
        label, score = classify_location_fukuoka("福岡市博多区博多駅")
        assert label == "博多駅/祇園"
        assert score == 20

    def test_tenjin(self):
        label, score = classify_location_fukuoka("福岡市中央区天神")
        assert label == "天神/中洲/春吉"
        assert score == 20

    def test_yakuin(self):
        label, score = classify_location_fukuoka("福岡市中央区薬院")
        assert label == "薬院"
        assert score == 18

    def test_ohashi(self):
        label, score = classify_location_fukuoka("福岡市南区大橋")
        assert label == "大橋/高宮"
        assert score == 0

    def test_other_returns_zero(self):
        """fukuoka Other = 0 (was -5, updated to neutral)."""
        label, score = classify_location_fukuoka("福岡市東区箱崎")
        assert label == "Other"
        assert score == 0

    def test_empty_string_returns_other_zero(self):
        label, score = classify_location_fukuoka("")
        assert label == "Other"
        assert score == 0

    def test_railway_line_strip(self):
        """'西鉄天神大牟田線' should not match '天神' location."""
        label, score = classify_location_fukuoka("西鉄天神大牟田線沿線 郊外エリア")
        assert label == "Other"
        assert score == 0


# ===========================================================================
# classify_location_tokyo
# ===========================================================================

class TestClassifyLocationTokyo:
    def test_shibuya(self):
        label, score = classify_location_tokyo("東京都渋谷区渋谷")
        assert label == "渋谷/恵比寿/代官山"
        assert score == 20

    def test_asakusa(self):
        label, score = classify_location_tokyo("東京都台東区浅草")
        assert label == "浅草/蔵前/押上"
        assert score == 18

    def test_nakameguro(self):
        label, score = classify_location_tokyo("東京都目黒区中目黒")
        assert label == "中目黒/代々木"
        assert score == 18

    def test_other_returns_zero(self):
        """tokyo Other = 0 (was -5, updated to neutral)."""
        label, score = classify_location_tokyo("東京都足立区北千住")
        assert label == "Other"
        assert score == 0

    def test_empty_string_returns_other_zero(self):
        label, score = classify_location_tokyo("")
        assert label == "Other"
        assert score == 0


# ===========================================================================
# pet_score_for_row
# ===========================================================================

class TestPetScoreForRow:
    def test_pet_allowed(self):
        row = make_row(pet_status="可", name="テスト", minpaku_status="")
        assert pet_score_for_row(row) == 15

    def test_pet_negotiable(self):
        row = make_row(pet_status="相談可", name="テスト", minpaku_status="")
        assert pet_score_for_row(row) == 10

    def test_pet_not_allowed(self):
        row = make_row(pet_status="不可", name="テスト", minpaku_status="")
        assert pet_score_for_row(row) == -5

    def test_pet_unknown_returns_minus_5(self):
        """pet unknown = -5 (not 0, not -15) — probably 不可 + confirmation needed."""
        row = make_row(pet_status="", name="テスト", minpaku_status="")
        assert pet_score_for_row(row) == -5

    def test_pet_allowed_in_name(self):
        """ペット可 appearing in name field should score 15."""
        row = make_row(pet_status="", name="ペット可マンション", minpaku_status="")
        assert pet_score_for_row(row) == 15

    def test_pet_fuka_in_name_wins_over_empty_status(self):
        """ペット不可 in name should score -5."""
        row = make_row(pet_status="", name="ペット不可マンション", minpaku_status="")
        assert pet_score_for_row(row) == -5

    def test_fuka_checked_before_ka(self):
        """不可 must be checked before 可 to avoid false positive."""
        row = make_row(pet_status="不可", name="ペット可", minpaku_status="")
        # pet_status="不可" takes precedence
        assert pet_score_for_row(row) == -5


# ===========================================================================
# maintenance_fee_score
# ===========================================================================

class TestMaintenanceFeeScore:
    def test_zero_fee_unknown_penalty(self):
        """Unknown (fee=0) gets -3 to prevent unverified properties ranking high."""
        assert maintenance_fee_score(0) == -3

    def test_very_low_under_10000(self):
        assert maintenance_fee_score(5000) == 10
        assert maintenance_fee_score(10000) == 10

    def test_10001_to_15000(self):
        assert maintenance_fee_score(12000) == 7
        assert maintenance_fee_score(15000) == 7

    def test_15001_to_20000(self):
        assert maintenance_fee_score(18000) == 5
        assert maintenance_fee_score(20000) == 5

    def test_20001_to_25000(self):
        assert maintenance_fee_score(23000) == 3
        assert maintenance_fee_score(25000) == 3

    def test_25001_to_30000(self):
        assert maintenance_fee_score(28000) == 0
        assert maintenance_fee_score(30000) == 0

    def test_30001_to_40000(self):
        assert maintenance_fee_score(35000) == -5
        assert maintenance_fee_score(40000) == -5

    def test_40001_to_50000(self):
        assert maintenance_fee_score(45000) == -8
        assert maintenance_fee_score(50000) == -8

    def test_over_50000(self):
        assert maintenance_fee_score(50001) == -10
        assert maintenance_fee_score(100000) == -10

    def test_boundary_10000_exact(self):
        assert maintenance_fee_score(10000) == 10

    def test_boundary_15000_exact(self):
        assert maintenance_fee_score(15000) == 7


# ===========================================================================
# score_row (orchestrator)
# ===========================================================================

class TestScoreRow:
    def test_modifies_row_in_place(self):
        row = make_row()
        config = make_config("fukuoka")
        score_row(row, config)
        assert row.total_score != 0 or isinstance(row.total_score, int)
        assert isinstance(row.score_breakdown, dict)
        assert row.tier_label != ""
        assert row.detail_comment != ""

    def test_score_breakdown_keys(self):
        row = make_row()
        config = make_config("fukuoka")
        score_row(row, config)
        expected_keys = {"budget", "area", "earthquake", "station", "location",
                         "layout", "pet", "maintenance", "renovation",
                         "brokerage", "minpaku_penalty"}
        assert expected_keys == set(row.score_breakdown.keys())

    def test_total_score_equals_sum_of_breakdown(self):
        row = make_row()
        config = make_config("fukuoka")
        score_row(row, config)
        expected = sum(row.score_breakdown.values())
        assert row.total_score == expected

    def test_city_key_osaka_uses_osaka_classifier(self):
        row = make_row(location="大阪市西区北堀江", station_text="")
        config = make_config("osaka")
        score_row(row, config)
        assert row.bucket_label == "北堀江/南堀江"
        assert row.score_breakdown["location"] == 15

    def test_city_key_tokyo_uses_tokyo_classifier(self):
        row = make_row(location="東京都渋谷区渋谷", station_text="")
        config = make_config("tokyo")
        score_row(row, config)
        assert row.bucket_label == "渋谷/恵比寿/代官山"
        assert row.score_breakdown["location"] == 20

    def test_city_key_fukuoka_uses_fukuoka_classifier(self):
        row = make_row(location="福岡市中央区天神", station_text="")
        config = make_config("fukuoka")
        score_row(row, config)
        assert row.bucket_label == "天神/中洲/春吉"
        assert row.score_breakdown["location"] == 20


# ===========================================================================
# Golden test: complete score_row for a known property
# ---------------------------------------------------------------------------
# Property: 福岡・天神エリア・築2000年・徒歩5分・50㎡・1LDK・ペット可
#           価格2000万・管理費15000・仲介手数料なし
#
# Expected breakdown:
#   budget       = 20   (2000万 ≤ 3500万)
#   area         = 15   (50㎡ in [40, 60))
#   earthquake   = 15   (2000年 > 1981)
#   station      = 15   (5分 ≤ 5)
#   location     = 20   (天神)
#   layout       = 5    (1LDK)
#   pet          = 15   (可)
#   maintenance  = 7    (15000 in (10000, 15000])
#   renovation   = 3    (unknown — no keywords → likely unrenovated)
#   brokerage    = 0    (empty)
#   minpaku_penalty = 0
#
# Total = 20+15+15+15+20+5+15+7+3+0+0 = 115
# ===========================================================================

class TestGoldenScoreRow:
    GOLDEN_ROW_PARAMS = dict(
        source="suumo",
        name="テスト天神マンション",
        price_text="2000万円",
        location="福岡市中央区天神",
        area_text="50.00m2",
        built_text="2000年1月",
        station_text="天神 徒歩5分",
        layout="1LDK",
        url="https://suumo.jp/test",
        price_man=2000,
        area_sqm=50.0,
        built_year=2000,
        built_month=1,
        walk_min=5,
        maintenance_fee=15000,
        pet_status="可",
        minpaku_status="",
        brokerage_text="",
        raw_line="",
    )

    def _build(self) -> PropertyRow:
        return PropertyRow(**self.GOLDEN_ROW_PARAMS)

    def test_golden_total_score(self):
        row = self._build()
        config = make_config("fukuoka")
        score_row(row, config)
        assert row.total_score == 115, (
            f"Golden score mismatch. Got {row.total_score}, "
            f"breakdown={row.score_breakdown}"
        )

    def test_golden_breakdown_individual(self):
        row = self._build()
        config = make_config("fukuoka")
        score_row(row, config)
        b = row.score_breakdown
        assert b["budget"] == 20,       f"budget: {b['budget']}"
        assert b["area"] == 15,         f"area: {b['area']}"
        assert b["earthquake"] == 15,   f"earthquake: {b['earthquake']}"
        assert b["station"] == 15,      f"station: {b['station']}"
        assert b["location"] == 20,     f"location: {b['location']}"
        assert b["layout"] == 5,        f"layout: {b['layout']}"
        assert b["pet"] == 15,          f"pet: {b['pet']}"
        assert b["maintenance"] == 7,   f"maintenance: {b['maintenance']}"
        assert b["renovation"] == 3,    f"renovation: {b['renovation']}"
        assert b["brokerage"] == 0,     f"brokerage: {b['brokerage']}"
        assert b["minpaku_penalty"] == 0, f"minpaku_penalty: {b['minpaku_penalty']}"

    def test_golden_tier_label(self):
        row = self._build()
        config = make_config("fukuoka")
        score_row(row, config)
        # 115 >= 80 → "強く推奨"
        assert row.tier_label == "強く推奨"

    def test_golden_bucket_label(self):
        row = self._build()
        config = make_config("fukuoka")
        score_row(row, config)
        assert row.bucket_label == "天神/中洲/春吉"
