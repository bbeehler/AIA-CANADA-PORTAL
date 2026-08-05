#!/usr/bin/env python3
"""Load official 2021 Census Profile demographics into Supabase.

Run only from a trusted operator terminal. The secret key must never be added to
Streamlit secrets, committed to GitHub, or pasted into chat.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aia_portal.statcan import METRIC_SPECS, FLOW_LEVELS, StatCanCensusClient, batches  # noqa: E402


LEVEL_FLOWS = {level: flow for flow, level in FLOW_LEVELS.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Statistics Canada Census Profile demographics.")
    parser.add_argument(
        "--levels",
        nargs="+",
        choices=sorted(LEVEL_FLOWS),
        default=["province", "municipality", "postal_region"],
        help="Geographic levels to refresh.",
    )
    parser.add_argument("--api-batch-size", type=int, default=35)
    parser.add_argument("--database-batch-size", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.api_batch_size < 1 or args.api_batch_size > 50:
        print("--api-batch-size must be between 1 and 50.", file=sys.stderr)
        return 2

    url = os.getenv("SUPABASE_URL", "")
    secret = os.getenv("SUPABASE_SECRET_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not secret:
        print("Set SUPABASE_URL and SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY).", file=sys.stderr)
        return 2

    supabase = create_client(url, secret)
    started = supabase.table("demographic_sync_runs").insert({
        "status": "running",
        "levels": args.levels,
    }).execute()
    run_id = (started.data or [{}])[0].get("id")
    geography_count = 0
    observation_count = 0

    try:
        statcan = StatCanCensusClient()
        for level in args.levels:
            flow = LEVEL_FLOWS[level]
            level_observation_count = 0
            geographies = statcan.geographies(flow)
            if not geographies:
                raise RuntimeError(f"No {level} geographies were returned by Statistics Canada")

            for batch in batches(geographies, args.database_batch_size):
                supabase.table("demographic_geographies").upsert(
                    batch,
                    on_conflict="geo_uid",
                ).execute()
            geography_count += len(geographies)

            metrics = statcan.metric_map(flow, str(geographies[0]["geo_uid"]))
            if not metrics:
                raise RuntimeError(f"No supported demographic characteristics were found for {level}")
            missing_count = len(METRIC_SPECS) - len(metrics)
            if missing_count:
                print(f"Warning: {missing_count} expected metric(s) were not available for {level}.")

            geography_ids = [str(item["geo_uid"]) for item in geographies]
            for api_batch in batches(geography_ids, args.api_batch_size):
                observations = statcan.observations(flow, api_batch, metrics)
                for database_batch in batches(observations, args.database_batch_size):
                    supabase.table("demographic_observations").upsert(
                        database_batch,
                        on_conflict="geography_id,metric_code,reference_period",
                    ).execute()
                observation_count += len(observations)
                level_observation_count += len(observations)
                print(
                    f"{level}: {level_observation_count} observations loaded",
                    flush=True,
                )

        if run_id is not None:
            supabase.table("demographic_sync_runs").update({
                "status": "completed",
                "geography_count": geography_count,
                "observation_count": observation_count,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", run_id).execute()
        print(f"Loaded {geography_count} geographies and {observation_count} demographic observations.")
        return 0
    except Exception as exc:
        if run_id is not None:
            supabase.table("demographic_sync_runs").update({
                "status": "failed",
                "geography_count": geography_count,
                "observation_count": observation_count,
                "message": str(exc)[:1000],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", run_id).execute()
        print(f"Demographic sync failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
