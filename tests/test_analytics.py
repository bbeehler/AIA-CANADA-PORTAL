import pandas as pd

from aia_portal.analytics import (
    current_explorer_comparison,
    current_metric_value,
    select_member_benchmark,
)


def member_rows():
    return pd.DataFrame([
        {
            "reporting_month": "2026-06-01",
            "geography_type": "national",
            "geography_code": "CA",
            "shop_type": "Mechanical",
            "contributor_count": 10,
            "privacy_threshold": 5,
            "average_repair_orders": 220,
            "hours_per_repair_order": 2.0,
        },
        {
            "reporting_month": "2026-06-01",
            "geography_type": "province",
            "geography_code": "ON",
            "shop_type": "Mechanical",
            "contributor_count": 6,
            "privacy_threshold": 5,
            "average_repair_orders": 225,
            "hours_per_repair_order": 2.1,
        },
    ])


def test_province_selection_prefers_current_province_cohort():
    selection = select_member_benchmark(
        member_rows(), province_code="ON", shop_type="Mechanical"
    )

    assert selection.available
    assert selection.geography_label == "ON"
    assert not selection.used_national_fallback
    assert selection.record["hours_per_repair_order"] == 2.1


def test_missing_province_falls_back_to_qualified_national_cohort():
    selection = select_member_benchmark(
        member_rows(), province_code="BC", shop_type="Mechanical"
    )

    assert selection.available
    assert selection.geography_label == "Canada"
    assert selection.used_national_fallback


def test_current_repair_orders_are_annualized_for_historical_comparison():
    selection = select_member_benchmark(member_rows(), shop_type="Mechanical")

    assert current_metric_value(selection.record, "average_repair_orders_year") == 2_640


def test_explorer_comparison_uses_latest_privacy_safe_province_rows():
    comparison = current_explorer_comparison(
        member_rows(),
        historical_metric_code="average_hours_repair_order",
        shop_type="Mechanical",
        geography_type="province",
        province_codes=["ON"],
    )

    assert comparison.iloc[0]["geography_code"] == "ON"
    assert comparison.iloc[0]["value"] == 2.1
    assert comparison.iloc[0]["contributor_count"] == 6


def test_incompatible_historical_metric_does_not_claim_a_direct_comparison():
    comparison = current_explorer_comparison(
        member_rows(),
        historical_metric_code="hours_sold_technician_day",
        shop_type="Mechanical",
        geography_type="national",
    )

    assert comparison.empty
