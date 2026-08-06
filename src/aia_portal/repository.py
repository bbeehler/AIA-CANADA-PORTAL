from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, MutableMapping
from uuid import uuid4

import pandas as pd

from .auth import PortalUser
from .data import load_performance_benchmarks, load_segment_benchmarks
from .dataset_validation import read_dataset_csv, validate_dataset, validate_dataset_slug
from .validation import read_uploaded_table, validate_shop_upload


DEFAULT_RESOURCES = [
    {
        "id": "resource-1",
        "section": "Featured research",
        "title": "2015 Productivity Benchmarks",
        "summary": "Benchmark repair orders, labour sales and technician productivity by shop size and region.",
        "resource_type": "Research report",
        "delivery_type": "external",
        "content_format": "markdown",
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
        "delivery_type": "internal",
        "content_format": "markdown",
        "external_url": "",
        "content": (
            "### Review process\n\n"
            "1. **Prepare:** Members use the standard template and remove customer, employee, vehicle and invoice identifiers.\n"
            "2. **Validate:** The portal checks the file structure, reporting period, province and numeric values.\n"
            "3. **Review:** AIA Canada reviews each submission before approval.\n"
            "4. **Aggregate:** Approved rows enter the governed data pool automatically. Only cohorts with at least five distinct contributors are published; raw shop figures remain private."
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

DEMO_MEMBER_BENCHMARKS = [
    {
        "reporting_month": month,
        "geography_type": geography_type,
        "geography_code": geography_code,
        "shop_type": "Mechanical",
        "contributor_count": contributors,
        "submitted_row_count": contributors,
        "privacy_threshold": 5,
        "average_bay_count": 5.1,
        "average_technician_count": 4.2,
        "average_repair_orders": repair_orders,
        "average_hours_sold": hours_sold,
        "hours_per_repair_order": round(hours_sold / repair_orders, 2),
        "hours_per_technician": round(hours_sold / 4.2, 2),
        "average_labour_sales_cad": labour_sales,
        "average_parts_sales_cad": parts_sales,
        "average_tire_sales_cad": tire_sales,
        "average_total_sales_cad": labour_sales + parts_sales + tire_sales,
        "sales_per_repair_order_cad": round(
            (labour_sales + parts_sales + tire_sales) / repair_orders, 2
        ),
        "refreshed_at": "2026-08-06T10:00:00+00:00",
    }
    for month, geography_type, geography_code, contributors, repair_orders, hours_sold,
    labour_sales, parts_sales, tire_sales in [
        ("2026-04-01", "national", "CA", 9, 205, 398, 49_800, 70_100, 8_200),
        ("2026-05-01", "national", "CA", 10, 214, 421, 52_400, 73_800, 9_100),
        ("2026-06-01", "national", "CA", 11, 221, 439, 54_700, 76_600, 9_800),
        ("2026-04-01", "province", "ON", 6, 211, 410, 51_200, 72_300, 7_900),
        ("2026-05-01", "province", "ON", 7, 219, 432, 53_500, 75_100, 8_700),
        ("2026-06-01", "province", "ON", 7, 226, 447, 55_900, 78_200, 9_400),
    ]
]

CONTRIBUTION_REVIEW_STATUSES = {"in_review", "approved", "rejected", "archived"}


def contribution_observation_rows(
    contribution: dict[str, Any], data: pd.DataFrame
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in data.reset_index(drop=True).iterrows():
        municipality = str(item.get("municipality") or "").strip() or None
        fsa = str(item.get("forward_sortation_area") or "").strip().upper() or None
        rows.append({
            "contribution_id": contribution["id"],
            "contributor_id": contribution["contributor_id"],
            "row_number": index + 1,
            "reporting_month": f"{item['reporting_month']}-01",
            "province": str(item["province"]),
            "municipality": municipality,
            "forward_sortation_area": fsa,
            "shop_type": str(item["shop_type"]),
            "bay_count": float(item["bay_count"]),
            "technician_count": float(item["technician_count"]),
            "repair_orders": float(item["repair_orders"]),
            "hours_sold": float(item["hours_sold"]),
            "labour_sales_cad": float(item["labour_sales_cad"]),
            "parts_sales_cad": float(item["parts_sales_cad"]),
            "tire_sales_cad": float(item["tire_sales_cad"]),
        })
    return rows


class DemoRepository:
    def __init__(self, state: MutableMapping[str, Any]):
        self.state = state
        self.state.setdefault("demo_contributions", [])
        self.state.setdefault("demo_contribution_payloads", {})
        self.state.setdefault("demo_approved_shop_observations", [])
        self.state.setdefault("demo_resources", [dict(item) for item in DEFAULT_RESOURCES])
        self.state.setdefault("demo_datasets", [{
            "id": "dataset-aia-2015",
            "slug": "aia-2015-productivity-benchmarks",
            "title": "2015 Productivity Benchmarks",
            "description": "Regional, shop-size and high-performance cohort benchmarks.",
            "data_year": 2015,
            "dataset_type": "mixed",
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

    def member_benchmark_aggregates(self) -> pd.DataFrame:
        return pd.DataFrame(DEMO_MEMBER_BENCHMARKS).copy()

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
        frame = read_uploaded_table(payload, filename)
        validation = validate_shop_upload(frame)
        if not validation.valid:
            raise ValueError("Contribution validation failed: " + " ".join(validation.errors))
        if row_count != len(validation.data):
            raise ValueError("Contribution row count does not match the validated data.")
        normalized_payload = validation.data.to_csv(index=False).encode("utf-8")
        safe_name = f"{Path(filename).stem}.csv"
        record = {
            "id": str(uuid4()),
            "contributor_id": user.id,
            "contributor_name": user.full_name,
            "organization": organization,
            "reporting_period_start": str(period_start),
            "reporting_period_end": str(period_end),
            "original_filename": safe_name,
            "storage_path": f"demo/{safe_name}",
            "row_count": len(validation.data),
            "notes": notes,
            "status": "submitted",
            "admin_notes": "",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state["demo_contributions"].append(record)
        self.state["demo_contribution_payloads"][record["id"]] = normalized_payload
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
        self.state["demo_approved_shop_observations"] = [
            item
            for item in self.state["demo_approved_shop_observations"]
            if item["contributor_id"] != user_id
        ]
        for contribution_id in deleted_contribution_ids:
            self.state["demo_contribution_payloads"].pop(contribution_id, None)
        self.state["demo_users"] = [item for item in self.state["demo_users"] if item["id"] != user_id]

    def review_contribution(
        self, contribution_id: str, status: str, admin_notes: str
    ) -> dict[str, int]:
        if status not in CONTRIBUTION_REVIEW_STATUSES:
            raise ValueError("Unknown contribution review status")
        for record in self.state["demo_contributions"]:
            if record["id"] == contribution_id:
                ingested_row_count = 0
                if status == "approved":
                    payload = self.download_contribution(record)
                    validation = validate_shop_upload(read_uploaded_table(payload, record["original_filename"]))
                    if not validation.valid or validation.data is None:
                        raise ValueError(
                            "Contribution validation failed: " + " ".join(validation.errors)
                        )
                    approved_rows = contribution_observation_rows(record, validation.data)
                    self.state["demo_approved_shop_observations"] = [
                        item
                        for item in self.state["demo_approved_shop_observations"]
                        if item["contribution_id"] != contribution_id
                    ]
                    self.state["demo_approved_shop_observations"].extend(approved_rows)
                    ingested_row_count = len(approved_rows)
                    record["ingested_row_count"] = ingested_row_count
                    record["ingested_at"] = datetime.now(timezone.utc).isoformat()
                record["status"] = status
                record["admin_notes"] = admin_notes
                record["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                return {
                    "ingested_row_count": ingested_row_count,
                    "aggregate_count": len(DEMO_MEMBER_BENCHMARKS),
                }
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
        dataset_type: str,
        description: str,
        filename: str,
        payload: bytes,
        created_by: str,
    ) -> dict[str, Any]:
        slug = validate_dataset_slug(slug)
        frame = read_dataset_csv(payload)
        validation = validate_dataset(frame, dataset_type)
        if not validation.valid:
            raise ValueError("Dataset validation failed: " + " ".join(validation.errors))
        normalized_payload = validation.data.to_csv(index=False).encode("utf-8")
        record = {
            "id": str(uuid4()), "slug": slug, "title": title, "description": description,
            "data_year": data_year, "dataset_type": dataset_type, "status": "draft", "version": 1,
            "row_count": len(validation.data), "source_filename": Path(filename).name,
            "created_by": created_by, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state["demo_datasets"].append(record)
        self.state.setdefault("demo_dataset_payloads", {})[record["id"]] = normalized_payload
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

    def member_benchmark_aggregates(self) -> pd.DataFrame:
        response = (
            self.client.table("member_benchmark_aggregates")
            .select("*")
            .order("reporting_month", desc=True)
            .execute()
        )
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
        frame = read_uploaded_table(payload, filename)
        validation = validate_shop_upload(frame)
        if not validation.valid:
            raise ValueError("Contribution validation failed: " + " ".join(validation.errors))
        if row_count != len(validation.data):
            raise ValueError("Contribution row count does not match the validated data.")
        normalized_payload = validation.data.to_csv(index=False).encode("utf-8")
        submission_id = str(uuid4())
        safe_name = f"{Path(filename).stem.replace(' ', '_')}.csv"
        storage_path = f"{user.id}/{submission_id}/{safe_name}"
        self.client.storage.from_("member-contributions").upload(
            path=storage_path,
            file=normalized_payload,
            file_options={"content-type": "text/csv", "upsert": "false"},
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
                "row_count": len(validation.data),
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

    def review_contribution(
        self, contribution_id: str, status: str, admin_notes: str
    ) -> dict[str, int]:
        if status not in CONTRIBUTION_REVIEW_STATUSES:
            raise ValueError("Unknown contribution review status")
        response = (
            self.client.table("contributions")
            .select("*")
            .eq("id", contribution_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise KeyError("Contribution not found")
        contribution = dict(response.data[0])
        reviewed_at = datetime.now(timezone.utc).isoformat()
        ingested_row_count = 0

        if status == "approved":
            payload = self.download_contribution(contribution)
            validation = validate_shop_upload(
                read_uploaded_table(payload, contribution["original_filename"])
            )
            if not validation.valid or validation.data is None:
                raise ValueError("Contribution validation failed: " + " ".join(validation.errors))
            approved_rows = contribution_observation_rows(contribution, validation.data)

            # Remove any previously published effect before replacing an approved submission.
            self.client.table("contributions").update({
                "status": "in_review",
                "admin_notes": admin_notes,
                "reviewed_at": reviewed_at,
            }).eq("id", contribution_id).execute()
            self.client.rpc("rebuild_member_benchmark_aggregates").execute()
            self.client.table("approved_shop_observations").delete().eq(
                "contribution_id", contribution_id
            ).execute()
            if approved_rows:
                self.client.table("approved_shop_observations").insert(approved_rows).execute()
            ingested_row_count = len(approved_rows)
            self.client.table("contributions").update({
                "status": "approved",
                "admin_notes": admin_notes,
                "reviewed_at": reviewed_at,
                "ingested_row_count": ingested_row_count,
                "ingested_at": reviewed_at,
            }).eq("id", contribution_id).execute()
        else:
            self.client.table("contributions").update({
                "status": status,
                "admin_notes": admin_notes,
                "reviewed_at": reviewed_at,
            }).eq("id", contribution_id).execute()

        aggregate_response = self.client.rpc("rebuild_member_benchmark_aggregates").execute()
        aggregate_count = int(aggregate_response.data or 0)
        return {
            "ingested_row_count": ingested_row_count,
            "aggregate_count": aggregate_count,
        }

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
        dataset_type: str,
        description: str,
        filename: str,
        payload: bytes,
        created_by: str,
    ) -> dict[str, Any]:
        slug = validate_dataset_slug(slug)
        frame = read_dataset_csv(payload)
        validation = validate_dataset(frame, dataset_type)
        if not validation.valid:
            raise ValueError("Dataset validation failed: " + " ".join(validation.errors))
        normalized_payload = validation.data.to_csv(index=False).encode("utf-8")
        dataset_id = str(uuid4())
        safe_name = Path(filename).name.replace(" ", "_")
        storage_path = f"{dataset_id}/{safe_name}"
        self.client.storage.from_("admin-datasets").upload(
            path=storage_path,
            file=normalized_payload,
            file_options={"content-type": "text/csv", "upsert": "false"},
        )
        try:
            response = self.client.table("datasets").insert({
                "id": dataset_id, "slug": slug, "title": title, "description": description,
                "data_year": data_year, "dataset_type": dataset_type, "status": "draft", "version": 1,
                "row_count": len(validation.data), "source_filename": safe_name,
                "storage_path": storage_path, "created_by": created_by,
            }).execute()
            return dict((response.data or [{}])[0])
        except Exception:
            self.client.storage.from_("admin-datasets").remove([storage_path])
            raise
