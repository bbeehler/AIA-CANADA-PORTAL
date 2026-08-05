from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketScenario:
    estimated_vehicles: float
    annual_auto_care_pool: float
    annual_pool_per_shop: float
    target_share_vehicles: float
    target_share_revenue: float


def calculate_market_scenario(
    *,
    occupied_households: float,
    vehicles_per_household: float,
    annual_spend_per_vehicle: float,
    shops_serving_market: int,
    target_share_percent: float,
) -> MarketScenario:
    """Calculate a transparent, user-controlled market scenario.

    These outputs are directional assumptions, not observed vehicle or spending data.
    """
    inputs = {
        "occupied_households": occupied_households,
        "vehicles_per_household": vehicles_per_household,
        "annual_spend_per_vehicle": annual_spend_per_vehicle,
        "shops_serving_market": shops_serving_market,
        "target_share_percent": target_share_percent,
    }
    if any(value < 0 for value in inputs.values()):
        raise ValueError("Market scenario inputs cannot be negative")
    if shops_serving_market < 1:
        raise ValueError("At least one shop must serve the market")
    if target_share_percent > 100:
        raise ValueError("Target market share cannot exceed 100 percent")

    estimated_vehicles = occupied_households * vehicles_per_household
    annual_pool = estimated_vehicles * annual_spend_per_vehicle
    share = target_share_percent / 100
    return MarketScenario(
        estimated_vehicles=estimated_vehicles,
        annual_auto_care_pool=annual_pool,
        annual_pool_per_shop=annual_pool / shops_serving_market,
        target_share_vehicles=estimated_vehicles * share,
        target_share_revenue=annual_pool * share,
    )
