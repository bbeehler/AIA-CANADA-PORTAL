from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "reporting_month",
    "province",
    "shop_type",
    "bay_count",
    "technician_count",
    "repair_orders",
    "hours_sold",
    "labour_sales_cad",
    "parts_sales_cad",
    "tire_sales_cad",
]
OPTIONAL_COLUMNS = ["municipality", "forward_sortation_area"]

PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}
SHOP_TYPES = {"Mechanical", "Tire", "Collision", "Other"}
NUMERIC_COLUMNS = [
    "bay_count",
    "technician_count",
    "repair_orders",
    "hours_sold",
    "labour_sales_cad",
    "parts_sales_cad",
    "tire_sales_cad",
]
PII_COLUMN_FRAGMENTS = {
    "customer", "employee", "first_name", "last_name", "email", "phone", "address",
    "postal", "vin", "licence", "license", "plate", "work_order", "invoice_number",
}


def _is_pii_column(column: str) -> bool:
    return any(
        column == fragment
        or column.startswith(f"{fragment}_")
        or column.endswith(f"_{fragment}")
        or f"_{fragment}_" in column
        for fragment in PII_COLUMN_FRAGMENTS
    )


@dataclass
class ValidationResult:
    data: pd.DataFrame | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.data is not None and not self.errors


def read_uploaded_table(payload: bytes, filename: str) -> pd.DataFrame:
    extension = Path(filename).suffix.lower()
    if extension == ".csv":
        return pd.read_csv(BytesIO(payload))
    if extension == ".xlsx":
        return pd.read_excel(BytesIO(payload), engine="openpyxl")
    raise ValueError("Use a CSV or XLSX file.")


def validate_shop_upload(frame: pd.DataFrame) -> ValidationResult:
    normalized = frame.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    errors: list[str] = []
    warnings: list[str] = []

    pii_columns = sorted(
        column for column in normalized.columns
        if _is_pii_column(column)
    )
    if pii_columns:
        errors.append(
            "Remove customer or employee identifiers before uploading: " + ", ".join(pii_columns)
        )

    allowed_columns = set(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    unexpected = sorted(column for column in normalized.columns if column not in allowed_columns)
    if unexpected:
        errors.append("Unexpected columns: " + ", ".join(unexpected) + ". Use the AIA Canada template.")

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        errors.append("Missing required columns: " + ", ".join(missing))
        return ValidationResult(None, errors, warnings)

    present_optional = [column for column in OPTIONAL_COLUMNS if column in normalized.columns]
    normalized = normalized[REQUIRED_COLUMNS + present_optional].copy()
    if normalized.empty:
        errors.append("The upload has no data rows.")
        return ValidationResult(None, errors, warnings)
    if len(normalized) > 120:
        errors.append("A contribution can contain at most 120 monthly rows.")

    text_columns = ["reporting_month", "province", "shop_type"] + present_optional
    for column in text_columns:
        formula_like = (
            normalized[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.startswith(("=", "+", "@", "\t", "\r"))
        )
        if formula_like.any():
            errors.append(f"{column} contains formula-like text; enter plain values only.")

    periods = pd.to_datetime(normalized["reporting_month"], errors="coerce")
    if periods.isna().any():
        errors.append("reporting_month must contain valid dates or YYYY-MM values.")
    else:
        reporting_periods = periods.dt.to_period("M")
        if (reporting_periods > pd.Period(date.today(), freq="M")).any():
            errors.append("reporting_month cannot be in the future.")
        normalized["reporting_month"] = reporting_periods.astype(str)

    normalized["province"] = normalized["province"].astype(str).str.strip().str.upper()
    invalid_provinces = sorted(set(normalized.loc[~normalized["province"].isin(PROVINCES), "province"]))
    if invalid_provinces:
        errors.append("Unknown province or territory codes: " + ", ".join(invalid_provinces))

    if "municipality" in normalized.columns:
        normalized["municipality"] = normalized["municipality"].fillna("").astype(str).str.strip()
        if (normalized["municipality"].str.len() > 100).any():
            errors.append("municipality must be 100 characters or fewer.")

    if "forward_sortation_area" in normalized.columns:
        normalized["forward_sortation_area"] = (
            normalized["forward_sortation_area"].fillna("").astype(str).str.strip().str.upper()
        )
        populated_fsa = normalized["forward_sortation_area"] != ""
        invalid_fsa = normalized.loc[
            populated_fsa
            & ~normalized["forward_sortation_area"].str.fullmatch(r"[A-Z]\d[A-Z]"),
            "forward_sortation_area",
        ]
        if not invalid_fsa.empty:
            errors.append(
                "forward_sortation_area must contain exactly the first three postal-code characters, "
                "for example K1A. Do not submit a full postal code."
            )

    normalized["shop_type"] = normalized["shop_type"].astype(str).str.strip().str.title()
    invalid_types = sorted(set(normalized.loc[~normalized["shop_type"].isin(SHOP_TYPES), "shop_type"]))
    if invalid_types:
        errors.append("Unknown shop types: " + ", ".join(invalid_types))

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if normalized[column].isna().any():
            errors.append(f"{column} contains blank or non-numeric values.")
        if (normalized[column].dropna() < 0).any():
            errors.append(f"{column} cannot contain negative values.")

    for column in ["bay_count", "technician_count"]:
        if (normalized[column].dropna() <= 0).any():
            errors.append(f"{column} must be greater than zero.")

    duplicate_columns = ["reporting_month", "province", "shop_type"] + present_optional
    duplicates = normalized.duplicated(subset=duplicate_columns).sum()
    if duplicates:
        warnings.append(f"{duplicates} possible duplicate reporting row(s) were found.")
    if normalized["hours_sold"].sum() == 0:
        warnings.append("Total hours sold is zero; confirm the reporting period is complete.")

    return ValidationResult(normalized if not errors else None, errors, warnings)
