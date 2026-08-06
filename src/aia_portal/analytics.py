from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


SOURCE_BEST_AVAILABLE = "Best available · current + historical"
SOURCE_HISTORICAL_ONLY = "Historical benchmark only"
SOURCE_OPTIONS = [SOURCE_BEST_AVAILABLE, SOURCE_HISTORICAL_ONLY]

MEMBER_NUMERIC_COLUMNS = [
    "contributor_count",
    "submitted_row_count",
    "privacy_threshold",
    "average_bay_count",
    "average_technician_count",
    "average_repair_orders",
    "average_hours_sold",
    "hours_per_repair_order",
    "hours_per_technician",
    "average_labour_sales_cad",
    "average_parts_sales_cad",
    "average_tire_sales_cad",
    "average_total_sales_cad",
    "sales_per_repair_order_cad",
]

# Historical segment metric -> compatible current member metric and conversion.
CURRENT_METRIC_MAP = {
    "average_hours_repair_order": ("hours_per_repair_order", 1.0),
    "average_repair_orders_year": ("average_repair_orders", 12.0),
}


@dataclass(frozen=True)
class MemberBenchmarkSelection:
    record: dict | None
    geography_label: str
    used_national_fallback: bool = False

    @property
    def available(self) -> bool:
        return self.record is not None


def normalize_member_benchmarks(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    normalized = frame.copy()
    for column in MEMBER_NUMERIC_COLUMNS:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized["reporting_month"] = pd.to_datetime(
        normalized["reporting_month"], errors="coerce"
    )
    return normalized.dropna(subset=["reporting_month"]).copy()


def select_member_benchmark(
    frame: pd.DataFrame,
    *,
    province_code: str | None = None,
    shop_type: str = "Mechanical",
) -> MemberBenchmarkSelection:
    data = normalize_member_benchmarks(frame)
    if data.empty:
        return MemberBenchmarkSelection(None, "No qualified current cohort")
    scoped = data[data["shop_type"] == shop_type]
    if province_code:
        province = scoped[
            (scoped["geography_type"] == "province")
            & (scoped["geography_code"] == province_code)
        ]
        if not province.empty:
            latest = province.sort_values("reporting_month").iloc[-1]
            return MemberBenchmarkSelection(latest.to_dict(), province_code)
    national = scoped[
        (scoped["geography_type"] == "national")
        & (scoped["geography_code"] == "CA")
    ]
    if not national.empty:
        latest = national.sort_values("reporting_month").iloc[-1]
        return MemberBenchmarkSelection(
            latest.to_dict(),
            "Canada",
            used_national_fallback=province_code is not None,
        )
    return MemberBenchmarkSelection(None, "No qualified current cohort")


def current_metric_value(record: dict, historical_metric_code: str) -> float | None:
    mapping = CURRENT_METRIC_MAP.get(historical_metric_code)
    if not mapping:
        return None
    current_code, multiplier = mapping
    value = record.get(current_code)
    if value is None or pd.isna(value):
        return None
    return float(value) * multiplier


def current_explorer_comparison(
    frame: pd.DataFrame,
    *,
    historical_metric_code: str,
    shop_type: str,
    geography_type: str,
    province_codes: list[str] | None = None,
) -> pd.DataFrame:
    data = normalize_member_benchmarks(frame)
    mapping = CURRENT_METRIC_MAP.get(historical_metric_code)
    if data.empty or not mapping:
        return pd.DataFrame()
    current_code, multiplier = mapping
    scoped = data[(data["shop_type"] == shop_type) & (data["geography_type"] == geography_type)]
    if geography_type == "national":
        scoped = scoped[scoped["geography_code"] == "CA"]
    elif province_codes is not None:
        scoped = scoped[scoped["geography_code"].isin(province_codes)]
    if scoped.empty:
        return pd.DataFrame()
    latest = (
        scoped.sort_values("reporting_month")
        .groupby("geography_code", as_index=False)
        .tail(1)
        .copy()
    )
    latest["value"] = latest[current_code] * multiplier
    latest["reference_period"] = latest["reporting_month"].dt.strftime("%Y-%m")
    latest["data_source"] = "Approved AIA member data"
    return latest[
        [
            "geography_code",
            "shop_type",
            "reference_period",
            "contributor_count",
            "privacy_threshold",
            "value",
            "data_source",
        ]
    ].sort_values("geography_code")
