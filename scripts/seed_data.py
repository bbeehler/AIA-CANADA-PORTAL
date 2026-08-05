#!/usr/bin/env python3
"""Load the extracted AIA 2015 benchmark CSVs into a configured Supabase project.

Run from a trusted operator workstation. Never put the secret/service-role key in
Streamlit secrets or browser-facing code.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from supabase import create_client


ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = "22222222-2222-4222-8222-222222222222"


def records(path: Path) -> list[dict]:
    frame = pd.read_csv(path)
    frame = frame.astype(object).where(pd.notna(frame), None)
    return frame.to_dict(orient="records")


def batches(items: list[dict], size: int = 100):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def main() -> int:
    url = os.getenv("SUPABASE_URL", "")
    secret = os.getenv("SUPABASE_SECRET_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not secret:
        print("Set SUPABASE_URL and SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY).", file=sys.stderr)
        return 2

    client = create_client(url, secret)
    segment_rows = records(ROOT / "data" / "aia_2015_segment_benchmarks.csv")
    performance_rows = records(ROOT / "data" / "aia_2015_performance_benchmarks.csv")
    for row in segment_rows + performance_rows:
        row["dataset_id"] = DATASET_ID

    for batch in batches(segment_rows):
        client.table("benchmark_observations").upsert(
            batch,
            on_conflict="dataset_id,segment,shop_size,geography_type,geography,affiliation",
        ).execute()
    for batch in batches(performance_rows):
        client.table("performance_benchmarks").upsert(
            batch,
            on_conflict="dataset_id,shop_type,cohort,metric_code",
        ).execute()

    total = len(segment_rows) + len(performance_rows)
    client.table("datasets").update({"row_count": total}).eq("id", DATASET_ID).execute()
    print(f"Loaded {len(segment_rows)} segment and {len(performance_rows)} performance rows ({total} total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
