from aia_portal.statcan import match_metrics, parse_sdmx_json, province_for_geography


def sample_payload():
    return {
        "dataSets": [{
            "series": {
                "0:0:0:0:0": {"observations": {"0": [16_000_000]}},
                "0:0:0:1:0": {"observations": {"0": [15_000_000]}},
            }
        }],
        "structure": {
            "dimensions": {
                "series": [
                    {"id": "FREQ", "values": [{"id": "A5", "name": "Every five years"}]},
                    {"id": "GEO", "values": [{"id": "2021A000235", "name": "Ontario"}]},
                    {"id": "GENDER", "values": [{"id": "1", "name": "Total"}]},
                    {"id": "CHARACTERISTIC", "values": [
                        {"id": "1", "name": "Population, 2021"},
                        {"id": "2", "name": "Population, 2016"},
                    ]},
                    {"id": "STATISTIC", "values": [{"id": "1", "name": "Count"}]},
                ]
            }
        },
    }


def test_sdmx_series_are_normalized():
    rows = parse_sdmx_json(sample_payload())
    assert len(rows) == 2
    assert rows[0]["geography_code"] == "2021A000235"
    assert rows[0]["characteristic_name"] == "Population, 2021"
    assert rows[0]["value"] == 16_000_000


def test_supported_metric_names_are_matched():
    rows = parse_sdmx_json(sample_payload())
    metrics = match_metrics(rows)
    assert metrics["population_2021"]["characteristic_code"] == "1"
    assert metrics["population_2016"]["reference_period"] == "2016"


def test_geography_province_codes_cover_municipality_and_fsa():
    assert province_for_geography("DF_CSD", "2021A00053506008") == "ON"
    assert province_for_geography("DF_FSA", "2021A0011K1A") == "ON"
    assert province_for_geography("DF_FSA", "2021A0011X0A") == "NU"
