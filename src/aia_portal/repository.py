from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, MutableMapping
from uuid import uuid4

import pandas as pd

from .auth import PortalUser
from .data import load_performance_benchmarks, load_segment_benchmarks


DEFAULT_RESOURCES = [
    {
        "id": "resource-1",
        "section": "Featured research",
        "title": "2015 Productivity Benchmarks",
        "summary": "Benchmark repair orders, labour sales and technician productivity by shop size and region.",
        "resource_type": "Research report",
        "external_url": "https://www.aiacanada.com/product/the-view-from-here-2015-productivity-benchmarks-in-the-canadian-automotive-service-sector/",
        "content": "",
        "published_at": "2016-09-01",
        "status": "published",
        "sort_order": 10,
    },
    {
        "id": "resource-2",
        "section": "Data guidance",
        "title": "How member contributions are reviewed",
        "summary": "AIA Canada validates structure, removes direct identifiers and approves data before aggregation.",
        "resource_type": "Methodology",
        "external_url": "",
        "content": (
            "### Review process\n\n"
            "1. **Prepare:** Members use the standard template and remove customer, employee, vehicle and invoice identifiers.\n"
            "2. **Validate:** The portal checks the file structure, reporting period, province and numeric values.\n"
            "3. **Review:** AIA Canada reviews each submission before approval.\n"
            "4. **Aggregate:** Approved information may be included only in anonymized industry benchmarks; raw shop files are not published."
        ),
        "published_at": "2026-08-01",
        "status": "published",
        "sort_order": 20,
    },
]

DEMO_DEMOGRAPHIC_VALUES = [
    ("population_2021", "Population, 2021", "Population", "count", "2021", 14_223_942),
    ("population_2016", "Population, 2016", "Population", "count", "2016", 13_448_494),
    ("population_growth_2016_2021", "Population growth, 2016 to 2021", "Population", "percent", "2016-2021", 5.8),
    ("population_density", "Population density", "Population", "people_per_square_km", "2021", 15.9),
    ("total_private_dwellings", "Total private dwellings", "Households", "count", "2021", 5_929_250),
    ("occupied_private_dwellings", "Occupied private dwellings", "Households", "count", "2021", 5_491_201),
    ("average_household_size", "Average household size", "Households", "count", "2021", 2.6),
    ("one_person_households", "One-person households", "Households", "count", "2021", 1_452_540),
    ("age_0_14", "Population aged 0 to 14", "Age", "count", "2021", 2_251_795),
    ("age_15_64", "Population aged 15 to 64", "Age", "count", "2021", 9_334_440),
    ("age_65_plus", "Population aged 65 and over", "Age", "count", "2021", 2_637_710),
    ("median_age", "Median age", "Age", "years", "2021", 41.6),
    ("median_household_income", "Median household income, 2020", "Income", "cad", "2020", 91_000),
    ("average_household_income", "Average household income, 2020", "Income", "cad", "2020", 116_000),
    ("median_after_tax_household_income", "Median after-tax household income, 2020", "Income", "cad", "2020", 79_500),
    ("average_after_tax_household_income", "Average after-tax household income, 2020", "Income", "cad", "2020", 95_300),
    ("participation_rate", "Labour-force participation rate", "Workforce", "percent", "2021", 62.8),
    ("employment_rate", "Employment rate", "Workforce", "percent", "2021", 55.1),
    ("unemployment_rate", "Unemployment rate", "Workforce", "percent", "2021", 12.2),
]


class DemoRepository:
    def __init__(self, state: MutableMapping[str, Any]):
        self.state = state
        self.state.setdefault("demo_contributions", [])
        self.state.setdefault("demo_contribution_payloads", {})
        self.state.setdefault("demo_resources", [dict(item) for item in DEFAULT_RESOURCES])
        self.state.setdefault("demo_datasets", [{
            "id": "dataset-aia-2015",
            "slug": "aia-2015-productivity-benchmarks",
            "title": "2015 Productivity Benchmarks",
            "description": "Regional, shop-size and high-performance cohort benchmarks.",
            "data_year": 2015,
            "status": "published",
            "version": 1,
            "row_count": 114,
            "created_at": "2016-09-01",
        }])
        self.state.setdefault("demo_users", [
            {
                "id": "demo-member", "email": "member@demo.aiacanada.com",
                "full_name": "Jordan Martin", "organization": "Maple Auto Service",
                "province": "ON", "role": "member", "membership_status": "active", "created_at": "2026-07-18",
            },
            {
                "id": "demo-pending", "email": "pending@demo.aiacanada.com",
                "full_name": "Sam Roy", "organization": "Northern Garage",
                "province": "QC", "role": "member", "membership_status": "pending", "created_at": "2026-08-02",
            },
            {
                "id": "demo-admin", "email": "admin@demo.aiacanada.com",
                "full_name": "Avery Chen", "organization": "AIA Canada",
                "province": "ON", "role": "admin", "membership_status": "active", "created_at": "2026-05-01",
            },
        ])

    def segment_benchmarks(self) -> pd.DataFrame:
        return load_segment_benchmarks().copy()

    def performance_benchmarks(self) -> pd.DataFrame:
        return load_performance_benchmarks().copy()

    def resources(self, include_unpublished: bool = False) -> list[dict[str, Any]]:
        resources = list(self.state["demo_resources"])
        if not include_unpublished:
            resources = [item for item in resources if item.get("status") == "published"]
        return sorted(resources, key=lambda item: (item.get("section", ""), item.get("sort_order", 0)))

    def demographic_geographies(
        self,
        geo_level: str,
        province_code: str | None = None,
        search_query: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if geo_level != "province" or (province_code and province_code != "ON"):
            return []
        if search_query and search_query.casefold() not in "ontario":
            return []
        return [{
            "geo_uid": "2021A000235",
            "geo_level": "province",
            "geo_code": "35",
            "geo_name": "Ontario",
            "province_code": "ON",
            "census_year": 2021,
            "source_flow": "DF_PR",
        }][:limit]

    def demographic_observations(self, geography_id: str) -> list[dict[str, Any]]:
        if geography_id != "2021A000235":
            return []
        return [
            {
                "metric_code": code,
                "label": label,
                "category": category,
                "unit": unit,
                "reference_period": period,
                "value": value,
                "source_characteristic_id": f"demo-{code}",
                "source_characteristic_name": label,
                "source_flow": "DF_PR",
                "source_url": "https://www12.statcan.gc.ca/wds-sdw/2021profile-profil2021-eng.cfm",
                "retrieved_at": "2026-08-05T19:06:20+00:00",
                "sort_order": index * 10,
            }
            for index, (code, label, category, unit, period, value)
            in enumerate(DEMO_DEMOGRAPHIC_VALUES, start=1)
        ]

    def demographic_sync_runs(self) -> list[dict[str, Any]]:
        return []

    def submit_contribution(
        self,
        *,
        user: PortalUser,
        organization: str,
        period_start: date,
        period_end: date,
        filename: str,
        payload: bytes,
        row_count: int,
        notes: str,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "contributor_id": user.id,
            "contributor_name": user.full_name,
            "organization": organization,
            "reporting_period_start": str(period_start),
            "reporting_period_end": str(period_end),
            "original_filename": Path(filename).name,
            "storage_path": f"demo/{Path(filename).name}",
            "row_count": row_count,
            "notes": notes,
            "status": "submitted",
            "admin_notes": "",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state["demo_contributions"].append(record)
        self.state["demo_contribution_payloads"][record["id"]] = payload
        return record

    def contributions(self, user: PortalUser, include_all: bool = False) -> list[dict[str, Any]]:
        records = list(self.state["demo_contributions"])
        if not (include_all and user.is_admin):
            records = [record for record in records if record["contributor_id"] == user.id]
        return sorted(records, key=lambda record: record["submitted_at"], reverse=True)

    def profiles(self) -> list[dict[str, Any]]:
        return list(self.state["demo_users"])

    def set_member_status(self, user_id: str, membership_status: str, role: str) -> None:
        for profile in self.state["demo_users"]:
            if profile["id"] == user_id:
                profile["membership_status"] = membership_status
                profile["role"] = role
                return
        raise KeyError("Member not found")

    def update_user(
        self,
        user_id: str,
        *,
        email: str,
        full_name: str,
        organization: str,
        province: str,
        membership_status: str,
        role: str,
    ) -> None:
        for profile in self.state["demo_users"]:
            if profile["id"] == user_id:
                profile.update({
                    "email": email,
                    "full_name": full_name,
                    "organization": organization,
                    "province": province,
                    "membership_status": membership_status,
                    "role": role,
                })
                return
        raise KeyError("Member not found")

    def delete_user(self, user_id: str) -> None:
        target = next((item for item in self.state["demo_users"] if item["id"] == user_id), None)
        if not target:
            raise KeyError("Member not found")
        if target.get("role") == "admin" and target.get("membership_status") == "active":
            active_admins = sum(
                item.get("role") == "admin" and item.get("membership_status") == "active"
                for item in self.state["demo_users"]
            )
            if active_admins <= 1:
                raise ValueError("Create another active administrator before removing the last one")
        deleted_contribution_ids = {
            item["id"]
            for item in self.state["demo_contributions"]
            if item["contributor_id"] == user_id
        }
        self.state["demo_contributions"] = [
            item for item in self.state["demo_contributions"] if item["contributor_id"] != user_id
        ]
        for contribution_id in deleted_contribution_ids:
            self.state["demo_contribution_payloads"].pop(contribution_id, None)
        self.state["demo_users"] = [item for item in self.state["demo_users"] if item["id"] != user_id]

    def review_contribution(self, contribution_id: str, status: str, admin_notes: str) -> None:
        for record in self.state["demo_contributions"]:
            if record["id"] == contribution_id:
                record["status"] = status
                record["admin_notes"] = admin_notes
                return
        raise KeyError("Contribution not found")

    def download_contribution(self, contribution: dict[str, Any]) -> bytes:
        return bytes(self.state["demo_contribution_payloads"].get(contribution["id"], b"Demo file payload"))

    def save_resource(self, resource: dict[str, Any]) -> None:
        resource = dict(resource)
        resource.setdefault("id", str(uuid4()))
        resource.setdefault("published_at", str(date.today()))
        self.state["demo_resources"].append(resource)

    def set_resource_status(self, resource_id: str, status: str) -> None:
        for resource in self.state["demo_resources"]:
            if resource["id"] == resource_id:
                resource["status"] = status
                return
        raise KeyError("Resource not found")

    def datasets(self) -> list[dict[str, Any]]:
        return list(self.state["demo_datasets"])

    def set_dataset_status(self, dataset_id: str, status: str) -> None:
        for dataset in self.state["demo_datasets"]:
            if dataset["id"] == dataset_id:
                dataset["status"] = status
                return
        raise KeyError("Dataset not found")

    def stage_dataset(
        self,
        *,
        title: str,
        slug: str,
        data_year: int,
        description: str,
        filename: str,
        payload: bytes,
        created_by: str,
    ) -> dict[str, Any]:
        frame = pd.read_csv(BytesIO(payload))
        record = {
            "id": str(uuid4()), "slug": slug, "title": title, "description": description,
            "data_year": data_year, "status": "draft", "version": 1,
            "row_count": len(frame), "source_filename": Path(filename).name,
            "created_by": created_by, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state["demo_datasets"].append(record)
        return record


class SupabaseRepository:
    def __init__(self, client: Any):
        self.client = client

    def segment_benchmarks(self) -> pd.DataFrame:
        response = self.client.table("benchmark_observations").select("*").execute()
        return pd.DataFrame(response.data or [])

    def performance_benchmarks(self) -> pd.DataFrame:
        response = self.client.table("performance_benchmarks").select("*").execute()
        return pd.DataFrame(response.data or [])

    def resources(self, include_unpublished: bool = False) -> list[dict[str, Any]]:
        query = self.client.table("resources").select("*").order("section").order("sort_order")
        if not include_unpublished:
            query = query.eq("status", "published")
        return list(query.execute().data or [])

    def demographic_geographies(
        self,
        geo_level: str,
        province_code: str | None = None,
        search_query: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = (
            self.client.table("demographic_geographies")
            .select("*")
            .eq("geo_level", geo_level)
        )
        if province_code:
            query = query.eq("province_code", province_code)
        if search_query and search_query.strip():
            query = query.ilike("geo_name", f"%{search_query.strip()}%")
        response = query.order("geo_name").limit(max(1, min(limit, 100))).execute()
        return list(response.data or [])

    def demographic_observations(self, geography_id: str) -> list[dict[str, Any]]:
        response = (
            self.client.table("demographic_observations")
            .select(
                "value,reference_period,source_characteristic_id,source_characteristic_name,"
                "source_flow,source_url,retrieved_at,"
                "demographic_metrics(metric_code,label,category,unit,description,sort_order)"
            )
            .eq("geography_id", geography_id)
            .execute()
        )
        rows: list[dict[str, Any]] = []
        for item in response.data or []:
            record = dict(item)
            metric = record.pop("demographic_metrics", {}) or {}
            record.update(metric)
            rows.append(record)
        return sorted(rows, key=lambda item: item.get("sort_order", 0))

    def demographic_sync_runs(self) -> list[dict[str, Any]]:
        response = (
            self.client.table("demographic_sync_runs")
            .select("*")
            .order("started_at", desc=True)
            .limit(20)
            .execute()
        )
        return list(response.data or [])

    def submit_contribution(
        self,
        *,
        user: PortalUser,
        organization: str,
        period_start: date,
        period_end: date,
        filename: str,
        payload: bytes,
        row_count: int,
        notes: str,
    ) -> dict[str, Any]:
        submission_id = str(uuid4())
        safe_name = Path(filename).name.replace(" ", "_")
        storage_path = f"{user.id}/{submission_id}/{safe_name}"
        mime = "text/csv" if safe_name.lower().endswith(".csv") else (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.client.storage.from_("member-contributions").upload(
            path=storage_path,
            file=payload,
            file_options={"content-type": mime, "upsert": "false"},
        )
        try:
            response = self.client.table("contributions").insert({
                "id": submission_id,
                "contributor_id": user.id,
                "organization": organization,
                "reporting_period_start": str(period_start),
                "reporting_period_end": str(period_end),
                "original_filename": safe_name,
                "storage_path": storage_path,
                "row_count": row_count,
                "notes": notes,
                "status": "submitted",
            }).execute()
            return dict((response.data or [{}])[0])
        except Exception:
            self.client.storage.from_("member-contributions").remove([storage_path])
            raise

    def contributions(self, user: PortalUser, include_all: bool = False) -> list[dict[str, Any]]:
        query = self.client.table("contributions").select("*").order("submitted_at", desc=True)
        if not (include_all and user.is_admin):
            query = query.eq("contributor_id", user.id)
        return list(query.execute().data or [])

    def profiles(self) -> list[dict[str, Any]]:
        return list(self.client.table("profiles").select("*").order("created_at", desc=True).execute().data or [])

    def set_member_status(self, user_id: str, membership_status: str, role: str) -> None:
        self.client.rpc("admin_update_member", {
            "target_user_id": user_id,
            "new_membership_status": membership_status,
            "new_role": role,
        }).execute()

    def update_user(
        self,
        user_id: str,
        *,
        email: str,
        full_name: str,
        organization: str,
        province: str,
        membership_status: str,
        role: str,
    ) -> None:
        self.client.functions.invoke("admin-users", {
            "body": {
                "action": "update",
                "user_id": user_id,
                "email": email,
                "full_name": full_name,
                "organization": organization,
                "province": province,
                "membership_status": membership_status,
                "role": role,
            },
            "responseType": "json",
        })

    def delete_user(self, user_id: str) -> None:
        self.client.functions.invoke("admin-users", {
            "body": {"action": "delete", "user_id": user_id},
            "responseType": "json",
        })

    def review_contribution(self, contribution_id: str, status: str, admin_notes: str) -> None:
        self.client.table("contributions").update({
            "status": status,
            "admin_notes": admin_notes,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", contribution_id).execute()

    def download_contribution(self, contribution: dict[str, Any]) -> bytes:
        return self.client.storage.from_("member-contributions").download(contribution["storage_path"])

    def save_resource(self, resource: dict[str, Any]) -> None:
        self.client.table("resources").insert(resource).execute()

    def set_resource_status(self, resource_id: str, status: str) -> None:
        self.client.table("resources").update({"status": status}).eq("id", resource_id).execute()

    def datasets(self) -> list[dict[str, Any]]:
        return list(self.client.table("datasets").select("*").order("created_at", desc=True).execute().data or [])

    def set_dataset_status(self, dataset_id: str, status: str) -> None:
        self.client.table("datasets").update({"status": status}).eq("id", dataset_id).execute()

    def stage_dataset(
        self,
        *,
        title: str,
        slug: str,
        data_year: int,
        description: str,
        filename: str,
        payload: bytes,
        created_by: str,
    ) -> dict[str, Any]:
        frame = pd.read_csv(BytesIO(payload))
        dataset_id = str(uuid4())
        safe_name = Path(filename).name.replace(" ", "_")
        storage_path = f"{dataset_id}/{safe_name}"
        self.client.storage.from_("admin-datasets").upload(
            path=storage_path,
            file=payload,
            file_options={"content-type": "text/csv", "upsert": "false"},
        )
        try:
            response = self.client.table("datasets").insert({
                "id": dataset_id, "slug": slug, "title": title, "description": description,
                "data_year": data_year, "status": "draft", "version": 1,
                "row_count": len(frame), "source_filename": safe_name,
                "storage_path": storage_path, "created_by": created_by,
            }).execute()
            return dict((response.data or [{}])[0])
        except Exception:
            self.client.storage.from_("admin-datasets").remove([storage_path])
            raise
