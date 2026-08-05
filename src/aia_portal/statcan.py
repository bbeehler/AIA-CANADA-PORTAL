from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_ROOT = "https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest"
FLOW_LEVELS = {
    "DF_PR": "province",
    "DF_CSD": "municipality",
    "DF_FSA": "postal_region",
}

PROVINCE_ABBREVIATIONS = {
    "10": "NL", "11": "PE", "12": "NS", "13": "NB", "24": "QC", "35": "ON",
    "46": "MB", "47": "SK", "48": "AB", "59": "BC", "60": "YT", "61": "NT", "62": "NU",
}


@dataclass(frozen=True)
class MetricSpec:
    code: str
    source_names: tuple[str, ...]
    reference_period: str


METRIC_SPECS = (
    MetricSpec("population_2021", ("Population, 2021",), "2021"),
    MetricSpec("population_2016", ("Population, 2016",), "2016"),
    MetricSpec(
        "population_growth_2016_2021",
        ("Population percentage change, 2016 to 2021", "Population change, 2016 to 2021 (%)"),
        "2016-2021",
    ),
    MetricSpec("population_density", ("Population density per square kilometre",), "2021"),
    MetricSpec("total_private_dwellings", ("Total private dwellings",), "2021"),
    MetricSpec(
        "occupied_private_dwellings",
        ("Private dwellings occupied by usual residents",),
        "2021",
    ),
    MetricSpec("average_household_size", ("Average household size",), "2021"),
    MetricSpec("one_person_households", ("One-person households",), "2021"),
    MetricSpec("age_0_14", ("0 to 14 years",), "2021"),
    MetricSpec("age_15_64", ("15 to 64 years",), "2021"),
    MetricSpec("age_65_plus", ("65 years and over",), "2021"),
    MetricSpec("median_age", ("Median age of the population", "Median age"), "2021"),
    MetricSpec(
        "median_household_income",
        ("Median total income of household in 2020 ($)", "Median total income of households in 2020 ($)"),
        "2020",
    ),
    MetricSpec(
        "average_household_income",
        ("Average total income of household in 2020 ($)", "Average total income of households in 2020 ($)"),
        "2020",
    ),
    MetricSpec(
        "median_after_tax_household_income",
        (
            "Median after-tax income of household in 2020 ($)",
            "Median after-tax income of households in 2020 ($)",
        ),
        "2020",
    ),
    MetricSpec(
        "average_after_tax_household_income",
        (
            "Average after-tax income of household in 2020 ($)",
            "Average after-tax income of households in 2020 ($)",
        ),
        "2020",
    ),
    MetricSpec("participation_rate", ("Participation rate",), "2021"),
    MetricSpec("employment_rate", ("Employment rate",), "2021"),
    MetricSpec("unemployment_rate", ("Unemployment rate",), "2021"),
)


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _first_observation(series: dict[str, Any]) -> float | None:
    observations = series.get("observations") or {}
    if not observations:
        return None
    observation = next(iter(observations.values()))
    raw = observation[0] if isinstance(observation, list) else observation
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_sdmx_json(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the SDMX-JSON series returned by the Census Profile API."""
    document = payload.get("data", payload)
    structure = document.get("structure") or {}
    dimensions = ((structure.get("dimensions") or {}).get("series") or [])
    datasets = document.get("dataSets") or document.get("datasets") or []
    if not dimensions or not datasets:
        return []

    dimension_ids = [str(item.get("id", "")).upper() for item in dimensions]
    dimension_values = [item.get("values") or [] for item in dimensions]
    rows: list[dict[str, Any]] = []
    series_collection = datasets[0].get("series") or {}
    for series_key, series in series_collection.items():
        indexes = [int(value) for value in str(series_key).split(":")]
        resolved: dict[str, dict[str, Any]] = {}
        for position, value_index in enumerate(indexes):
            if position >= len(dimension_ids) or value_index >= len(dimension_values[position]):
                continue
            resolved[dimension_ids[position]] = dimension_values[position][value_index]

        geography = resolved.get("GEO") or resolved.get("GEOGRAPHY") or {}
        characteristic = resolved.get("CHARACTERISTIC") or resolved.get("CHAR") or {}
        value = _first_observation(series)
        if not geography or not characteristic or value is None:
            continue
        rows.append({
            "geography_code": str(geography.get("id", "")),
            "geography_name": str(geography.get("name") or geography.get("id") or ""),
            "characteristic_code": str(characteristic.get("id", "")),
            "characteristic_name": str(characteristic.get("name") or characteristic.get("id") or ""),
            "value": value,
        })
    return rows


def _geo_code(flow: str, geography_id: str) -> str:
    prefixes = {"DF_PR": "2021A0002", "DF_CSD": "2021A0005", "DF_FSA": "2021A0011"}
    prefix = prefixes[flow]
    return geography_id[len(prefix):] if geography_id.startswith(prefix) else geography_id


def _fsa_province(fsa: str) -> str:
    if fsa in {"X0A", "X0B", "X0C"}:
        return "NU"
    return {
        "A": "NL", "B": "NS", "C": "PE", "E": "NB", "G": "QC", "H": "QC", "J": "QC",
        "K": "ON", "L": "ON", "M": "ON", "N": "ON", "P": "ON", "R": "MB", "S": "SK",
        "T": "AB", "V": "BC", "X": "NT", "Y": "YT",
    }.get(fsa[:1], "")


def province_for_geography(flow: str, geography_id: str) -> str:
    code = _geo_code(flow, geography_id)
    if flow == "DF_PR":
        return PROVINCE_ABBREVIATIONS.get(code[-2:], "")
    if flow == "DF_CSD":
        return PROVINCE_ABBREVIATIONS.get(code[:2], "")
    return _fsa_province(code)


def match_metrics(characteristics: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    candidates = list(characteristics)
    matched: dict[str, dict[str, str]] = {}
    for spec in METRIC_SPECS:
        source_names = {_normalized(name) for name in spec.source_names}
        exact = next(
            (item for item in candidates if _normalized(item["characteristic_name"]) in source_names),
            None,
        )
        if exact is None:
            exact = next(
                (
                    item for item in candidates
                    if any(name in _normalized(item["characteristic_name"]) for name in source_names)
                ),
                None,
            )
        if exact:
            matched[spec.code] = {
                "characteristic_code": exact["characteristic_code"],
                "characteristic_name": exact["characteristic_name"],
                "reference_period": spec.reference_period,
            }
    return matched


class StatCanCensusClient:
    def __init__(self, *, timeout: int = 90, retries: int = 3):
        self.timeout = timeout
        self.retries = retries

    def _fetch(self, flow: str, key: str) -> tuple[dict[str, Any], str]:
        safe_key = quote(key, safe=".+")
        url = f"{API_ROOT}/data/STC_CP,{flow}/{safe_key}?detail=full&format=jsondata"
        request = Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "AIA-Canada-Data-Portal/1.0 (data@aiacanada.com)",
        })
        for attempt in range(self.retries):
            try:
                with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - fixed HTTPS host
                    return json.loads(response.read().decode("utf-8")), url
            except HTTPError as exc:
                if exc.code not in {409, 429, 500, 502, 503, 504} or attempt + 1 == self.retries:
                    raise RuntimeError(f"Statistics Canada returned HTTP {exc.code}") from exc
            except (URLError, TimeoutError) as exc:
                if attempt + 1 == self.retries:
                    raise RuntimeError("Statistics Canada could not be reached") from exc
            time.sleep(2 ** attempt)
        raise RuntimeError("Statistics Canada request failed")

    def geographies(self, flow: str) -> list[dict[str, str | int]]:
        if flow not in FLOW_LEVELS:
            raise ValueError(f"Unsupported Census Profile flow: {flow}")
        payload, _ = self._fetch(flow, "A5..1.1.1")
        rows = parse_sdmx_json(payload)
        seen: set[str] = set()
        geographies: list[dict[str, str | int]] = []
        for row in rows:
            uid = row["geography_code"]
            province_code = province_for_geography(flow, uid)
            if not uid or not province_code or uid in seen:
                continue
            seen.add(uid)
            geographies.append({
                "geo_uid": uid,
                "geo_level": FLOW_LEVELS[flow],
                "geo_code": _geo_code(flow, uid),
                "geo_name": row["geography_name"],
                "province_code": province_code,
                "census_year": 2021,
                "source_flow": flow,
            })
        return geographies

    def metric_map(self, flow: str, geography_id: str) -> dict[str, dict[str, str]]:
        payload, _ = self._fetch(flow, f"A5.{geography_id}.1..1")
        return match_metrics(parse_sdmx_json(payload))

    def observations(
        self,
        flow: str,
        geography_ids: list[str],
        metrics: dict[str, dict[str, str]],
    ) -> list[dict[str, Any]]:
        if not geography_ids or not metrics:
            return []
        source_by_characteristic = {
            item["characteristic_code"]: (metric_code, item)
            for metric_code, item in metrics.items()
        }
        key = (
            f"A5.{'+'.join(geography_ids)}.1."
            f"{'+'.join(source_by_characteristic)}.1"
        )
        payload, url = self._fetch(flow, key)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        observations: list[dict[str, Any]] = []
        for row in parse_sdmx_json(payload):
            source = source_by_characteristic.get(row["characteristic_code"])
            if not source:
                continue
            metric_code, metadata = source
            observations.append({
                "geography_id": row["geography_code"],
                "metric_code": metric_code,
                "reference_period": metadata["reference_period"],
                "value": row["value"],
                "source_characteristic_id": row["characteristic_code"],
                "source_characteristic_name": row["characteristic_name"],
                "source_flow": flow,
                "source_url": url,
                "retrieved_at": retrieved_at,
            })
        return observations


def batches(items: list[Any], size: int) -> Iterable[list[Any]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]
