import pandas as pd
import pytest

from aia_portal.dataset_validation import (
    DATASET_PERFORMANCE,
    DATASET_SEGMENT,
    PERFORMANCE_COLUMNS,
    SEGMENT_COLUMNS,
    dataset_template_bytes,
    read_dataset_csv,
    validate_dataset,
    validate_dataset_slug,
)
from aia_portal.repository import DemoRepository


@pytest.mark.parametrize(
    ("dataset_type", "expected_columns"),
    [
        (DATASET_SEGMENT, SEGMENT_COLUMNS),
        (DATASET_PERFORMANCE, PERFORMANCE_COLUMNS),
    ],
)
def test_downloadable_templates_pass_their_data_contract(dataset_type, expected_columns):
    payload = dataset_template_bytes(dataset_type)
    frame = read_dataset_csv(payload)
    result = validate_dataset(frame, dataset_type)

    assert result.valid, result.errors
    assert list(result.data.columns) == expected_columns
    assert len(result.data) == 1


def test_segment_validation_normalizes_values_and_optional_blanks():
    frame = read_dataset_csv(dataset_template_bytes(DATASET_SEGMENT))
    frame.loc[0, "segment"] = "mechanical"
    frame.loc[0, "geography_type"] = "REGION"
    frame["source_page"] = None

    result = validate_dataset(frame, DATASET_SEGMENT)

    assert result.valid, result.errors
    assert result.data.loc[0, "segment"] == "Mechanical"
    assert result.data.loc[0, "geography_type"] == "region"
    assert pd.isna(result.data.loc[0, "source_page"])
    assert result.warnings == ["1 row(s) have no source page."]


def test_segment_validation_rejects_bad_percent_and_duplicate_keys():
    frame = read_dataset_csv(dataset_template_bytes(DATASET_SEGMENT))
    frame.loc[0, "percentage_with_apprentices"] = 101
    frame = pd.concat([frame, frame], ignore_index=True)

    result = validate_dataset(frame, DATASET_SEGMENT)

    assert not result.valid
    assert "percentage_with_apprentices must be between 0 and 100." in result.errors
    assert "1 duplicate segment/geography row(s) were found." in result.errors


def test_performance_validation_rejects_invalid_metric_unit_and_formula_text():
    frame = read_dataset_csv(dataset_template_bytes(DATASET_PERFORMANCE))
    frame.loc[0, "metric_code"] = "Hours Sold"
    frame.loc[0, "unit"] = "dollars"
    frame.loc[0, "metric_label"] = "=HYPERLINK(\"https://example.ca\")"

    result = validate_dataset(frame, DATASET_PERFORMANCE)

    assert not result.valid
    assert any("metric_code must use" in error for error in result.errors)
    assert "Unsupported unit(s): dollars" in result.errors
    assert any("formula-like" in error for error in result.errors)


def test_dataset_validation_rejects_missing_and_unexpected_columns():
    frame = read_dataset_csv(dataset_template_bytes(DATASET_PERFORMANCE))
    frame = frame.drop(columns=["unit"])
    frame["notes"] = "not part of the contract"

    result = validate_dataset(frame, DATASET_PERFORMANCE)

    assert not result.valid
    assert "Missing required columns: unit" in result.errors
    assert "Unexpected columns: notes" in result.errors


@pytest.mark.parametrize("slug", ["My Dataset", "my_dataset", "-dataset", "dataset-"])
def test_dataset_slug_validation_rejects_noncanonical_values(slug):
    with pytest.raises(ValueError):
        validate_dataset_slug(slug)


def test_demo_repository_revalidates_and_records_dataset_type():
    repo = DemoRepository({})
    record = repo.stage_dataset(
        title="2026 Ontario benchmarks",
        slug="2026-ontario-benchmarks",
        data_year=2026,
        dataset_type=DATASET_SEGMENT,
        description="Illustrative test dataset.",
        filename="ontario.csv",
        payload=dataset_template_bytes(DATASET_SEGMENT),
        created_by="demo-admin",
    )

    assert record["dataset_type"] == DATASET_SEGMENT
    assert record["status"] == "draft"
    assert record["row_count"] == 1


def test_demo_repository_rejects_invalid_dataset_payload():
    repo = DemoRepository({})
    with pytest.raises(ValueError, match="Dataset validation failed"):
        repo.stage_dataset(
            title="Invalid",
            slug="invalid-dataset",
            data_year=2026,
            dataset_type=DATASET_PERFORMANCE,
            description="Invalid test dataset.",
            filename="invalid.csv",
            payload=b"wrong,column\n1,2\n",
            created_by="demo-admin",
        )
