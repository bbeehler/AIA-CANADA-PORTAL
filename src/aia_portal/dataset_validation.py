from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re

import pandas as pd

from .config import DATA_DIR


DATASET_SEGMENT = "segment"
DATASET_PERFORMANCE = "performance"
DATASET_TYPE_LABELS = {
    DATASET_SEGMENT: "Regional and shop-size benchmarks",
    DATASET_PERFORMANCE: "Performance cohort benchmarks",
}

SEGMENT_COLUMNS = [
    "segment",
    "shop_size",
    "geography_type",
    "geography",
    "affiliation",
    "sample_size",
    "average_repair_orders_year",
    "average_hours_repair_order",
    "average_repair_orders_technician_day",
    "percentage_exceed_two_hours",
    "percentage_sales_from_tires",
    "percentage_with_apprentices",
    "hours_sold_technician_day",
    "percentage_with_service_advisor",
    "percentage_parts_from_oem",
    "source_page",
]
SEGMENT_METRIC_COLUMNS = [
    "average_repair_orders_year",
    "average_hours_repair_order",
    "average_repair_orders_technician_day",
    "percentage_exceed_two_hours",
    "percentage_sales_from_tires",
    "percentage_with_apprentices",
    "hours_sold_technician_day",
    "percentage_with_service_advisor",
    "percentage_parts_from_oem",
]
SEGMENT_PERCENT_COLUMNS = [
    "percentage_exceed_two_hours",
    "percentage_sales_from_tires",
    "percentage_with_apprentices",
    "percentage_with_service_advisor",
    "percentage_parts_from_oem",
]
PERFORMANCE_COLUMNS = [
    "shop_type",
    "cohort",
    "metric_code",
    "metric_label",
    "value",
    "unit",
    "sort_order",
    "source_page",
]
PERFORMANCE_UNITS = ["count", "hours", "percent", "ratio", "cad", "days", "years"]

TEMPLATE_FILES = {
    DATASET_SEGMENT: DATA_DIR / "segment_benchmark_upload_template.csv",
    DATASET_PERFORMANCE: DATA_DIR / "performance_benchmark_upload_template.csv",
}

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_METRIC_CODE_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


@dataclass
class DatasetValidationResult:
    data: pd.DataFrame | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.data is not None and not self.errors


def dataset_template_bytes(dataset_type: str) -> bytes:
    try:
        path = TEMPLATE_FILES[dataset_type]
    except KeyError as exc:
        raise ValueError("Unknown dataset type.") from exc
    return Path(path).read_bytes()


def read_dataset_csv(payload: bytes) -> pd.DataFrame:
    if not payload:
        raise ValueError("The CSV file is empty.")
    try:
        return pd.read_csv(BytesIO(payload))
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError(f"The file is not a readable CSV: {exc}") from exc


def validate_dataset_slug(value: str) -> str:
    slug = value.strip().lower()
    if not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError("Slug must use lowercase letters, numbers and single hyphens only.")
    return slug


def _required_text(frame: pd.DataFrame, columns: list[str], errors: list[str]) -> None:
    for column in columns:
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        blank_count = int(frame[column].eq("").sum())
        if blank_count:
            errors.append(f"{column} has {blank_count} blank value(s).")
        formula_count = int(frame[column].str.startswith(("=", "+", "@", "\t", "\r")).sum())
        if formula_count:
            errors.append(f"{column} contains {formula_count} formula-like value(s); use plain text.")


def _numeric_column(
    frame: pd.DataFrame,
    column: str,
    errors: list[str],
    *,
    required: bool = False,
    integer: bool = False,
) -> pd.Series:
    raw = frame[column]
    blank = raw.isna() | raw.astype(str).str.strip().eq("")
    numeric = pd.to_numeric(raw.mask(blank), errors="coerce")
    invalid_count = int((~blank & numeric.isna()).sum())
    if invalid_count:
        errors.append(f"{column} contains {invalid_count} non-numeric value(s).")
    if required and blank.any():
        errors.append(f"{column} has {int(blank.sum())} blank value(s).")
    if integer:
        non_integer_count = int(((numeric.dropna() % 1) != 0).sum())
        if non_integer_count:
            errors.append(f"{column} contains {non_integer_count} non-integer value(s).")
    frame[column] = numeric
    return numeric


def _validate_segment(frame: pd.DataFrame, errors: list[str], warnings: list[str]) -> None:
    _required_text(frame, ["segment", "shop_size", "geography_type", "geography", "affiliation"], errors)
    frame["segment"] = frame["segment"].str.title()
    frame["geography_type"] = frame["geography_type"].str.lower()

    invalid_segments = sorted(set(frame.loc[~frame["segment"].isin({"Mechanical", "Tire"}), "segment"]))
    if invalid_segments:
        errors.append("segment must be Mechanical or Tire; found: " + ", ".join(invalid_segments[:10]))
    invalid_geo_types = sorted(set(
        frame.loc[~frame["geography_type"].isin({"region", "national"}), "geography_type"]
    ))
    if invalid_geo_types:
        errors.append("geography_type must be region or national; found: " + ", ".join(invalid_geo_types[:10]))
    invalid_national = frame[
        frame["geography_type"].eq("national") & ~frame["geography"].str.casefold().eq("canada")
    ]
    if not invalid_national.empty:
        errors.append("Rows with geography_type national must use Canada as the geography.")

    sample_size = _numeric_column(frame, "sample_size", errors, integer=True)
    if (sample_size.dropna() < 0).any():
        errors.append("sample_size cannot be negative.")

    for column in SEGMENT_METRIC_COLUMNS:
        values = _numeric_column(frame, column, errors)
        if (values.dropna() < 0).any():
            errors.append(f"{column} cannot be negative.")
    for column in SEGMENT_PERCENT_COLUMNS:
        values = frame[column].dropna()
        if ((values < 0) | (values > 100)).any():
            errors.append(f"{column} must be between 0 and 100.")

    source_page = _numeric_column(frame, "source_page", errors, integer=True)
    if (source_page.dropna() <= 0).any():
        errors.append("source_page must be a positive integer when provided.")
    if source_page.isna().any():
        warnings.append(f"{int(source_page.isna().sum())} row(s) have no source page.")

    rows_without_metrics = frame[SEGMENT_METRIC_COLUMNS].isna().all(axis=1)
    if rows_without_metrics.any():
        errors.append(f"{int(rows_without_metrics.sum())} row(s) contain no benchmark metric values.")

    duplicate_count = int(frame.duplicated(
        subset=["segment", "shop_size", "geography_type", "geography", "affiliation"]
    ).sum())
    if duplicate_count:
        errors.append(f"{duplicate_count} duplicate segment/geography row(s) were found.")


def _validate_performance(frame: pd.DataFrame, errors: list[str], warnings: list[str]) -> None:
    _required_text(frame, ["shop_type", "cohort", "metric_code", "metric_label", "unit"], errors)
    frame["shop_type"] = frame["shop_type"].str.title()
    frame["metric_code"] = frame["metric_code"].str.lower()
    frame["unit"] = frame["unit"].str.lower()

    invalid_shop_types = sorted(set(
        frame.loc[~frame["shop_type"].isin({"Mechanical", "Tire"}), "shop_type"]
    ))
    if invalid_shop_types:
        errors.append("shop_type must be Mechanical or Tire; found: " + ", ".join(invalid_shop_types[:10]))
    invalid_codes = sorted({code for code in frame["metric_code"] if not _METRIC_CODE_PATTERN.fullmatch(code)})
    if invalid_codes:
        errors.append(
            "metric_code must use lowercase letters, numbers and underscores; found: "
            + ", ".join(invalid_codes[:10])
        )
    invalid_units = sorted(set(frame.loc[~frame["unit"].isin(PERFORMANCE_UNITS), "unit"]))
    if invalid_units:
        errors.append("Unsupported unit(s): " + ", ".join(invalid_units[:10]))

    values = _numeric_column(frame, "value", errors, required=True)
    if (values.dropna() < 0).any():
        errors.append("value cannot be negative.")
    percent_values = frame.loc[frame["unit"].eq("percent"), "value"].dropna()
    if ((percent_values < 0) | (percent_values > 100)).any():
        errors.append("Values with unit percent must be between 0 and 100.")

    sort_order = _numeric_column(frame, "sort_order", errors, required=True, integer=True)
    if (sort_order.dropna() < 0).any():
        errors.append("sort_order cannot be negative.")
    source_page = _numeric_column(frame, "source_page", errors, integer=True)
    if (source_page.dropna() <= 0).any():
        errors.append("source_page must be a positive integer when provided.")
    if source_page.isna().any():
        warnings.append(f"{int(source_page.isna().sum())} row(s) have no source page.")

    duplicate_count = int(frame.duplicated(
        subset=["shop_type", "cohort", "metric_code"]
    ).sum())
    if duplicate_count:
        errors.append(f"{duplicate_count} duplicate shop/cohort/metric row(s) were found.")


def validate_dataset(frame: pd.DataFrame, dataset_type: str) -> DatasetValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if dataset_type not in DATASET_TYPE_LABELS:
        return DatasetValidationResult(None, ["Unknown dataset type."], warnings)

    normalized = frame.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    expected = SEGMENT_COLUMNS if dataset_type == DATASET_SEGMENT else PERFORMANCE_COLUMNS
    missing = [column for column in expected if column not in normalized.columns]
    unexpected = [column for column in normalized.columns if column not in expected]
    if missing:
        errors.append("Missing required columns: " + ", ".join(missing))
    if unexpected:
        errors.append("Unexpected columns: " + ", ".join(unexpected))
    if errors:
        return DatasetValidationResult(None, errors, warnings)

    normalized = normalized[expected].copy()
    if normalized.empty:
        return DatasetValidationResult(None, ["The dataset has no data rows."], warnings)
    if len(normalized) > 10_000:
        errors.append("A dataset can contain at most 10,000 rows.")

    if dataset_type == DATASET_SEGMENT:
        _validate_segment(normalized, errors, warnings)
    else:
        _validate_performance(normalized, errors, warnings)

    return DatasetValidationResult(normalized if not errors else None, errors, warnings)
