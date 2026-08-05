import pandas as pd

from aia_portal.validation import REQUIRED_COLUMNS, validate_shop_upload


def valid_frame():
    return pd.DataFrame([{
        "reporting_month": "2026-01",
        "province": "ON",
        "shop_type": "Mechanical",
        "bay_count": 5,
        "technician_count": 4,
        "repair_orders": 220,
        "hours_sold": 420,
        "labour_sales_cad": 52500,
        "parts_sales_cad": 76000,
        "tire_sales_cad": 0,
    }])


def test_valid_upload_is_normalized():
    result = validate_shop_upload(valid_frame())
    assert result.valid
    assert list(result.data.columns) == REQUIRED_COLUMNS
    assert result.data.loc[0, "reporting_month"] == "2026-01"


def test_pii_columns_are_rejected():
    frame = valid_frame()
    frame["customer_email"] = "person@example.com"
    result = validate_shop_upload(frame)
    assert not result.valid
    assert any("identifiers" in error for error in result.errors)


def test_negative_values_are_rejected():
    frame = valid_frame()
    frame.loc[0, "repair_orders"] = -1
    result = validate_shop_upload(frame)
    assert not result.valid
    assert any("negative" in error for error in result.errors)
