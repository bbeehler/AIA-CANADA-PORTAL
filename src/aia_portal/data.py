from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .config import DATA_DIR


SEGMENT_FILE = DATA_DIR / "aia_2015_segment_benchmarks.csv"
PERFORMANCE_FILE = DATA_DIR / "aia_2015_performance_benchmarks.csv"
TEMPLATE_FILE = DATA_DIR / "member_shop_upload_template.csv"

METRICS = {
    "average_repair_orders_year": ("Repair orders / year", "count"),
    "average_hours_repair_order": ("Hours sold / repair order", "hours"),
    "average_repair_orders_technician_day": ("Repair orders / technician / day", "count"),
    "percentage_exceed_two_hours": ("Shops exceeding 2 hours / repair order", "percent"),
    "percentage_sales_from_tires": ("Sales from tires", "percent"),
    "percentage_with_apprentices": ("Shops with apprentices", "percent"),
    "hours_sold_technician_day": ("Hours sold / technician / day", "hours"),
    "percentage_with_service_advisor": ("Shops with a service advisor", "percent"),
    "percentage_parts_from_oem": ("Parts purchased from OEM", "percent"),
}

PERFORMANCE_FOCUS_METRICS = [
    "hours_repair_order",
    "hours_technician_day",
    "repair_orders_technician_day",
    "labour_revenue_paid_tech_hour",
    "labour_revenue_vs_door_rate",
]


@lru_cache(maxsize=1)
def load_segment_benchmarks() -> pd.DataFrame:
    frame = pd.read_csv(SEGMENT_FILE)
    numeric = [column for column in frame.columns if column not in {
        "segment", "shop_size", "geography_type", "geography", "affiliation"
    }]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    return frame


@lru_cache(maxsize=1)
def load_performance_benchmarks() -> pd.DataFrame:
    frame = pd.read_csv(PERFORMANCE_FILE)
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    return frame


def national_segment_snapshot() -> pd.DataFrame:
    data = load_segment_benchmarks()
    return data[
        (data["geography_type"] == "national")
        & (data["geography"] == "Canada")
        & (data["affiliation"] == "All")
    ].copy()


def read_template_bytes() -> bytes:
    return TEMPLATE_FILE.read_bytes()


def metric_label(code: str) -> str:
    return METRICS.get(code, (code.replace("_", " ").title(), "count"))[0]


def format_metric(value: float, unit: str) -> str:
    if pd.isna(value):
        return "—"
    if unit == "percent":
        return f"{value:.0f}%"
    if unit == "cad":
        return f"${value:,.2f}"
    if unit in {"hours", "ratio"}:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"
