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
        "external_url": "",
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
        "published_at": "2026-08-01",
        "status": "published",
        "sort_order": 20,
    },
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
