from datetime import date

import pytest

from aia_portal.auth import DEMO_USERS
from aia_portal.repository import DemoRepository, SupabaseRepository


def test_demo_repository_updates_user_profile_and_access():
    repo = DemoRepository({})

    repo.update_user(
        "demo-member",
        email="new.member@example.ca",
        full_name="New Member",
        organization="Updated Shop",
        province="BC",
        membership_status="suspended",
        role="analyst",
    )

    updated = next(profile for profile in repo.profiles() if profile["id"] == "demo-member")
    assert updated["email"] == "new.member@example.ca"
    assert updated["full_name"] == "New Member"
    assert updated["organization"] == "Updated Shop"
    assert updated["province"] == "BC"
    assert updated["membership_status"] == "suspended"
    assert updated["role"] == "analyst"


def test_demo_repository_permanently_deletes_user_contributions_and_file():
    repo = DemoRepository({})
    contribution = repo.submit_contribution(
        user=DEMO_USERS["member"],
        organization="Maple Auto Service",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        filename="shop.csv",
        payload=(
            b"reporting_month,province,shop_type,bay_count,technician_count,repair_orders,"
            b"hours_sold,labour_sales_cad,parts_sales_cad,tire_sales_cad\n"
            b"2026-01,ON,Mechanical,5,4,220,420,52500,76000,0\n"
        ),
        row_count=1,
        notes="",
    )

    repo.delete_user("demo-member")

    assert all(profile["id"] != "demo-member" for profile in repo.profiles())
    assert not repo.state["demo_contributions"]
    assert contribution["id"] not in repo.state["demo_contribution_payloads"]


def test_demo_repository_revalidates_contribution_payloads():
    repo = DemoRepository({})

    with pytest.raises(ValueError, match="Contribution validation failed"):
        repo.submit_contribution(
            user=DEMO_USERS["member"],
            organization="Maple Auto Service",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            filename="invalid.csv",
            payload=b"customer_email,labour_sales_cad\nperson@example.ca,1000\n",
            row_count=1,
            notes="",
        )


def test_demo_repository_protects_last_active_admin():
    repo = DemoRepository({})

    try:
        repo.delete_user("demo-admin")
    except ValueError as exc:
        assert "last one" in str(exc)
    else:
        raise AssertionError("Deleting the last active administrator should fail")


class FakeFunctions:
    def __init__(self):
        self.calls = []

    def invoke(self, name, options):
        self.calls.append((name, options))
        return {"ok": True}


class FakeClient:
    def __init__(self):
        self.functions = FakeFunctions()


def test_supabase_repository_invokes_server_side_user_admin_function():
    client = FakeClient()
    repo = SupabaseRepository(client)

    repo.update_user(
        "11111111-1111-4111-8111-111111111111",
        email="member@example.ca",
        full_name="Member Name",
        organization="Member Shop",
        province="ON",
        membership_status="active",
        role="member",
    )
    repo.delete_user("11111111-1111-4111-8111-111111111111")

    assert client.functions.calls[0][0] == "admin-users"
    assert client.functions.calls[0][1]["body"]["action"] == "update"
    assert client.functions.calls[0][1]["responseType"] == "json"
    assert client.functions.calls[1][1]["body"] == {
        "action": "delete",
        "user_id": "11111111-1111-4111-8111-111111111111",
    }
