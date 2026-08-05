import pytest

from aia_portal.market import calculate_market_scenario


def test_market_scenario_keeps_assumptions_explicit():
    scenario = calculate_market_scenario(
        occupied_households=10_000,
        vehicles_per_household=1.5,
        annual_spend_per_vehicle=1_200,
        shops_serving_market=20,
        target_share_percent=2,
    )

    assert scenario.estimated_vehicles == 15_000
    assert scenario.annual_auto_care_pool == 18_000_000
    assert scenario.annual_pool_per_shop == 900_000
    assert scenario.target_share_vehicles == 300
    assert scenario.target_share_revenue == 360_000


def test_market_scenario_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="At least one shop"):
        calculate_market_scenario(
            occupied_households=100,
            vehicles_per_household=1,
            annual_spend_per_vehicle=1_000,
            shops_serving_market=0,
            target_share_percent=1,
        )
