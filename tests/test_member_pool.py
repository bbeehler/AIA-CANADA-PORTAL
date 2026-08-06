from datetime import date
from pathlib import Path

from aia_portal.auth import DEMO_USERS
from aia_portal.repository import DemoRepository


VALID_CONTRIBUTION = (
    b"reporting_month,province,shop_type,bay_count,technician_count,repair_orders,"
    b"hours_sold,labour_sales_cad,parts_sales_cad,tire_sales_cad\n"
    b"2026-01,ON,Mechanical,5,4,220,420,52500,76000,0\n"
)


def test_approving_contribution_ingests_validated_rows_into_private_pool():
    repo = DemoRepository({})
    contribution = repo.submit_contribution(
        user=DEMO_USERS["member"],
        organization="Maple Auto Service",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        filename="shop.csv",
        payload=VALID_CONTRIBUTION,
        row_count=1,
        notes="",
    )

    result = repo.review_contribution(contribution["id"], "approved", "Validated")

    approved = next(item for item in repo.contributions(DEMO_USERS["admin"], True))
    assert approved["status"] == "approved"
    assert approved["ingested_row_count"] == 1
    assert result["ingested_row_count"] == 1
    assert repo.state["demo_approved_shop_observations"][0]["province"] == "ON"


def test_member_aggregates_never_expose_cohorts_below_privacy_threshold():
    data = DemoRepository({}).member_benchmark_aggregates()

    assert not data.empty
    assert (data["privacy_threshold"] >= 5).all()
    assert (data["contributor_count"] >= data["privacy_threshold"]).all()


def test_member_pool_migration_enables_rls_and_restricts_aggregate_function():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "20260806100000_member_data_pool.sql"
    ).read_text()

    assert "approved_shop_observations enable row level security" in migration
    assert "member_benchmark_aggregates enable row level security" in migration
    assert "having count(distinct observations.contributor_id) >= 5" in migration
    assert "security invoker" in migration
    assert (
        "revoke execute on function public.rebuild_member_benchmark_aggregates() "
        "from public, anon"
    ) in migration
