"""Malaysia DOSM/data.gov.my public aggregate collector and profile builder."""

from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import httpx

from simulation_core.calibration import validate_profile


DEFAULT_USER_AGENT = "SoutheastAsiaMarketTwin/3.0 (+data-provenance)"


class DosmDataSourceError(RuntimeError):
    """Raised when a DOSM dataset cannot be accepted safely."""


@dataclass(frozen=True)
class DosmSource:
    source_id: str
    dataset_id: str
    documentation: str
    csv_url: str
    title: str
    required_fields: tuple[str, ...]
    minimum_filtered_records: int


SOURCES: Dict[str, DosmSource] = {
    "population_state": DosmSource(
        source_id="DOSM_POPULATION_STATE",
        dataset_id="population_state",
        documentation="https://data.gov.my/data-catalogue/population_state",
        csv_url="https://storage.dosm.gov.my/population/population_state.csv",
        title="Malaysia population by state, age and sex",
        required_fields=("state", "date", "sex", "age", "ethnicity", "population"),
        minimum_filtered_records=500,
    ),
    "population_district": DosmSource(
        source_id="DOSM_POPULATION_DISTRICT",
        dataset_id="population_district",
        documentation="https://data.gov.my/data-catalogue/population_district",
        csv_url="https://storage.dosm.gov.my/population/population_district.csv",
        title="Malaysia population by administrative district, age and sex",
        required_fields=(
            "state",
            "district",
            "date",
            "sex",
            "age",
            "ethnicity",
            "population",
        ),
        minimum_filtered_records=5_000,
    ),
    "income_state_percentile": DosmSource(
        source_id="DOSM_HIES_STATE_PERCENTILE",
        dataset_id="hies_state_percentile",
        documentation="https://data.gov.my/data-catalogue/hies_state_percentile",
        csv_url="https://storage.dosm.gov.my/hies/hies_state_percentile.csv",
        title="Malaysia household income by state and percentile",
        required_fields=("date", "state", "percentile", "variable", "income"),
        minimum_filtered_records=1_500,
    ),
    "hies_state": DosmSource(
        source_id="DOSM_HIES_STATE",
        dataset_id="hies_state",
        documentation="https://data.gov.my/data-catalogue/hies_state",
        csv_url="https://storage.dosm.gov.my/hies/hies_state.csv",
        title="Malaysia household income and expenditure by state",
        required_fields=(
            "date",
            "state",
            "income_mean",
            "income_median",
            "expenditure_mean",
            "gini",
            "poverty",
        ),
        minimum_filtered_records=16,
    ),
    "hies_district": DosmSource(
        source_id="DOSM_HIES_DISTRICT",
        dataset_id="hies_district",
        documentation="https://data.gov.my/data-catalogue/hies_district",
        csv_url="https://storage.dosm.gov.my/hies/hies_district.csv",
        title="Malaysia household income and expenditure by administrative district",
        required_fields=(
            "date",
            "state",
            "district",
            "income_mean",
            "income_median",
            "expenditure_mean",
            "gini",
            "poverty",
        ),
        minimum_filtered_records=150,
    ),
    "labour_district": DosmSource(
        source_id="DOSM_LFS_DISTRICT",
        dataset_id="lfs_district",
        documentation="https://data.gov.my/data-catalogue/lfs_district",
        csv_url="https://storage.dosm.gov.my/labour/lfs_district.csv",
        title="Malaysia labour-force statistics by administrative district",
        required_fields=(
            "state",
            "district",
            "date",
            "p_rate",
            "u_rate",
            "ep_ratio",
        ),
        minimum_filtered_records=150,
    ),
    "households_state": DosmSource(
        source_id="DOSM_HOUSEHOLDS_STATE",
        dataset_id="hh_profile_state",
        documentation="https://data.gov.my/data-catalogue/hh_profile_state",
        csv_url="https://storage.dosm.gov.my/demography/hh_lq_state.csv",
        title="Malaysia households and living quarters by state",
        required_fields=("state", "date", "households", "living_quarters"),
        minimum_filtered_records=16,
    ),
    "cpi_state": DosmSource(
        source_id="DOSM_CPI_STATE",
        dataset_id="cpi_state",
        documentation="https://data.gov.my/data-catalogue/cpi_state",
        csv_url="https://storage.dosm.gov.my/cpi/cpi_2d_state.csv",
        title="Malaysia monthly CPI by state and division",
        required_fields=("state", "date", "division", "index"),
        minimum_filtered_records=300,
    ),
}


REGION_STATES = {
    "Central": ("Selangor", "W.P. Kuala Lumpur", "W.P. Putrajaya"),
    "Northern": ("Kedah", "Perak", "Perlis", "Pulau Pinang"),
    "Southern": ("Johor", "Melaka", "Negeri Sembilan"),
    "East Coast": ("Kelantan", "Pahang", "Terengganu"),
    "East Malaysia": ("Sabah", "Sarawak", "W.P. Labuan"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _number(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise DosmDataSourceError(f"Invalid numeric value: {value!r}") from error
    if result != result or result in (float("inf"), float("-inf")):
        raise DosmDataSourceError(f"Invalid numeric value: {value!r}")
    return result


def _district_lookup_key(state: Any, district: Any) -> str:
    """Make official releases with minor spelling changes join safely."""
    normalized = "|".join(
        re.sub(
            r"[^a-z0-9]",
            "",
            str(value or "")
            .casefold()
            .replace("highlands", "highland")
            .replace("dan", ""),
        )
        for value in (state, district)
    )
    aliases = {
        "terengganu|huluterengganu": "terengganu|hulu",
    }
    return aliases.get(normalized, normalized)


class DosmCollector:
    def __init__(
        self,
        timeout_seconds: float = 90.0,
        attempts: int = 3,
        client: Optional[httpx.Client] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.attempts = max(1, attempts)
        self._client = client

    def _download(self, source: DosmSource) -> bytes:
        client = self._client or httpx.Client(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        should_close = self._client is None
        last_error: Optional[Exception] = None
        try:
            for attempt in range(self.attempts):
                try:
                    response = client.get(source.csv_url)
                    response.raise_for_status()
                    if len(response.content) > 80_000_000:
                        raise DosmDataSourceError(
                            f"{source.source_id} exceeded the 80 MB safety limit"
                        )
                    return response.content
                except httpx.HTTPError as error:
                    last_error = error
                    if attempt + 1 < self.attempts:
                        time.sleep(0.5 * (2**attempt))
        finally:
            if should_close:
                client.close()
        raise DosmDataSourceError(
            f"Unable to fetch {source.source_id}: {last_error}"
        )

    @staticmethod
    def _parse(source: DosmSource, content: bytes) -> List[Dict[str, Any]]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DosmDataSourceError(
                f"{source.source_id} returned invalid UTF-8"
            ) from error
        reader = csv.DictReader(io.StringIO(text))
        fields = tuple(reader.fieldnames or ())
        missing = sorted(set(source.required_fields) - set(fields))
        if missing:
            raise DosmDataSourceError(
                f"{source.source_id} is missing expected fields: {missing}"
            )
        return [dict(row) for row in reader]

    @staticmethod
    def _filter(source_name: str, rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        latest_date = max(str(row.get("date") or "") for row in rows)
        if source_name == "population_state":
            dates = sorted({str(row.get("date")) for row in rows})[-3:]
            return [
                dict(row)
                for row in rows
                if str(row.get("date")) in dates
                and str(row.get("ethnicity")) == "overall"
            ]
        if source_name == "population_district":
            return [
                dict(row)
                for row in rows
                if str(row.get("date")) == latest_date
                and str(row.get("ethnicity")) == "overall"
            ]
        if source_name == "income_state_percentile":
            return [
                dict(row)
                for row in rows
                if str(row.get("date")) == latest_date
                and str(row.get("variable")) == "mean"
            ]
        if source_name in {
            "hies_state",
            "hies_district",
            "labour_district",
            "households_state",
        }:
            return [dict(row) for row in rows if str(row.get("date")) == latest_date]
        if source_name == "cpi_state":
            overall = [row for row in rows if str(row.get("division")) == "overall"]
            dates = sorted({str(row.get("date")) for row in overall})[-24:]
            return [dict(row) for row in overall if str(row.get("date")) in dates]
        return [dict(row) for row in rows]

    def fetch(self, source_name: str) -> Dict[str, Any]:
        if source_name not in SOURCES:
            raise KeyError(f"Unknown DOSM source: {source_name}")
        source = SOURCES[source_name]
        raw_content = self._download(source)
        filtered = self._filter(source_name, self._parse(source, raw_content))
        if len(filtered) < source.minimum_filtered_records:
            raise DosmDataSourceError(
                f"{source.source_id} returned {len(filtered)} filtered records; "
                f"expected at least {source.minimum_filtered_records}"
            )
        canonical = _canonical_json_bytes(filtered)
        return {
            "source": source,
            "rows": filtered,
            "manifest": {
                "source_id": source.source_id,
                "dataset_id": source.dataset_id,
                "dataset_page": source.documentation,
                "api_url": source.csv_url,
                "title": source.title,
                "license": "CC BY 4.0",
                "retrieval_method": "official_public_csv",
                "observed": True,
                "fetched_at": _utc_now(),
                "record_count": len(filtered),
                "raw_sha256": hashlib.sha256(raw_content).hexdigest(),
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "filter": "latest available period; CPI retains latest 24 months",
            },
        }

    @staticmethod
    def write_snapshot(result: Mapping[str, Any], snapshot_root: Path) -> Dict[str, Any]:
        source: DosmSource = result["source"]
        manifest = dict(result["manifest"])
        target_dir = snapshot_root / str(manifest["fetched_at"])[:10]
        target_dir.mkdir(parents=True, exist_ok=True)
        data_path = target_dir / f"{source.dataset_id}.json.gz"
        temporary_path = target_dir / f".{data_path.name}.tmp"
        temporary_path.write_bytes(
            gzip.compress(
                _canonical_json_bytes(result["rows"]),
                compresslevel=9,
                mtime=0,
            )
        )
        temporary_path.replace(data_path)
        try:
            manifest["snapshot_path"] = str(
                data_path.resolve().relative_to(Path.cwd().resolve())
            )
        except ValueError:
            manifest["snapshot_path"] = str(data_path)
        return manifest

    def refresh_all(self, snapshot_root: Path) -> Dict[str, Any]:
        rows: Dict[str, List[Dict[str, Any]]] = {}
        manifests: Dict[str, Dict[str, Any]] = {}
        for source_name in SOURCES:
            result = self.fetch(source_name)
            rows[source_name] = result["rows"]
            manifests[source_name] = self.write_snapshot(result, snapshot_root)
        generated_at = _utc_now()
        manifest = {
            "schema_version": "1",
            "pipeline": "malaysia_dosm_macro_profile",
            "generated_at": generated_at,
            "sources": manifests,
        }
        manifest_path = snapshot_root / generated_at[:10] / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"rows": rows, "manifest": manifest, "manifest_path": str(manifest_path)}


def _normalize(values: Mapping[str, float]) -> Dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        raise DosmDataSourceError("Cannot normalize an empty distribution")
    return {key: value / total for key, value in values.items()}


def _adult_age_weight(age: str) -> float:
    if age == "15-19":
        return 0.4
    if age in {"overall", "0-4", "5-9", "10-14"}:
        return 0.0
    return 1.0


def _age_bucket(age: str) -> Optional[str]:
    if age == "15-19":
        return "18-24"
    if age == "20-24":
        return "18-24"
    if age in {"25-29", "30-34"}:
        return "25-34"
    if age in {"35-39", "40-44"}:
        return "35-44"
    if age in {"45-49", "50-54"}:
        return "45-54"
    if age not in {"overall", "0-4", "5-9", "10-14"}:
        return "55+"
    return None


def build_malaysia_profile(
    base_profile: Mapping[str, Any],
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    profile = copy.deepcopy(dict(base_profile))
    population_rows = rows["population_state"]
    population_latest_date = max(str(row["date"]) for row in population_rows)
    current_population_rows = [
        row for row in population_rows if str(row["date"]) == population_latest_date
    ]
    state_totals = {
        str(row["state"]): _number(row["population"]) * 1_000
        for row in current_population_rows
        if row.get("sex") == "both" and row.get("age") == "overall"
    }
    if len(state_totals) != 16:
        raise DosmDataSourceError("Expected all 16 Malaysian state/territory totals")

    age_counts = {name: 0.0 for name in ("18-24", "25-34", "35-44", "45-54", "55+")}
    gender_counts = {"Female": 0.0, "Male": 0.0}
    for row in current_population_rows:
        age = str(row.get("age"))
        weight = _adult_age_weight(age)
        if weight <= 0:
            continue
        value = _number(row.get("population")) * weight
        if row.get("sex") == "both":
            bucket = _age_bucket(age)
            if bucket:
                age_counts[bucket] += value
        elif row.get("sex") == "female":
            gender_counts["Female"] += value
        elif row.get("sex") == "male":
            gender_counts["Male"] += value

    region_totals = {
        region: sum(state_totals[state] for state in states)
        for region, states in REGION_STATES.items()
    }
    province_by_region = {
        region: _normalize({state: state_totals[state] for state in states})
        for region, states in REGION_STATES.items()
    }

    hies_rows = {str(row["state"]): row for row in rows["hies_state"]}
    district_population_rows = rows["population_district"]
    district_population_latest_date = max(
        str(row["date"]) for row in district_population_rows
    )
    district_population = {
        f"{row['state']}|{row['district']}": _number(row["population"]) * 1_000
        for row in district_population_rows
        if str(row.get("date")) == district_population_latest_date
        and row.get("sex") == "both"
        and row.get("age") == "overall"
        and row.get("ethnicity") == "overall"
    }
    if len(district_population) < 150:
        raise DosmDataSourceError(
            "Expected at least 150 Malaysian administrative-district totals"
        )
    district_hies = {
        _district_lookup_key(row["state"], row["district"]): row
        for row in rows["hies_district"]
    }
    district_labour = {
        _district_lookup_key(row["state"], row["district"]): row
        for row in rows["labour_district"]
    }
    district_context = {}
    for district_key, population in district_population.items():
        state, district = district_key.split("|", maxsplit=1)
        lookup_key = _district_lookup_key(state, district)
        hies_row = district_hies.get(lookup_key) or hies_rows.get(state)
        if hies_row is None:
            raise DosmDataSourceError(
                f"Missing household-income context for {district_key}"
            )
        labour_row = district_labour.get(lookup_key)
        district_context[district_key] = {
            "population": int(round(population)),
            "income_mean_myr": _number(hies_row["income_mean"]),
            "income_median_myr": _number(hies_row["income_median"]),
            "expenditure_mean_myr": _number(hies_row["expenditure_mean"]),
            "gini": _number(hies_row["gini"]),
            "poverty_rate": _number(hies_row["poverty"]),
            "income_context_status": (
                "official_district_aggregate"
                if lookup_key in district_hies
                else "official_state_aggregate_fallback"
            ),
            "labour_participation_rate": (
                _number(labour_row["p_rate"]) if labour_row else None
            ),
            "unemployment_rate": (
                _number(labour_row["u_rate"]) if labour_row else None
            ),
            "employment_population_ratio": (
                _number(labour_row["ep_ratio"]) if labour_row else None
            ),
            "labour_context_status": (
                "official_district_aggregate"
                if labour_row
                else "not_available_for_district"
            ),
        }
    if len(district_context) != len(district_population):
        raise DosmDataSourceError("District context did not cover every district")
    household_rows = {
        str(row["state"]): row for row in rows["households_state"]
    }
    national_income = sum(
        state_totals[state] * _number(hies_rows[state]["income_mean"])
        for state in state_totals
    ) / sum(state_totals.values())
    region_income = {
        region: sum(
            state_totals[state] * _number(hies_rows[state]["income_mean"])
            for state in states
        )
        / sum(state_totals[state] for state in states)
        for region, states in REGION_STATES.items()
    }
    province_income_multiplier = {
        state: _number(hies_rows[state]["income_mean"])
        / region_income[region]
        for region, states in REGION_STATES.items()
        for state in states
    }

    income_percentiles = rows["income_state_percentile"]
    tier_ranges = {
        "LOW": range(1, 21),
        "MID_LOW": range(21, 41),
        "MID_HIGH": range(41, 61),
        "HIGH": range(61, 81),
        "LUXURY": range(81, 101),
    }
    tier_sums = {tier: 0.0 for tier in tier_ranges}
    tier_weights = {tier: 0.0 for tier in tier_ranges}
    for row in income_percentiles:
        percentile = int(row["percentile"])
        state = str(row["state"])
        for tier, percentile_range in tier_ranges.items():
            if percentile in percentile_range:
                weight = _number(household_rows[state]["households"])
                tier_sums[tier] += _number(row["income"]) * weight
                tier_weights[tier] += weight
                break
    income_midpoints = {
        tier: round(tier_sums[tier] / tier_weights[tier], 2)
        for tier in tier_ranges
    }

    household_reference_date = max(
        str(row["date"]) for row in rows["households_state"]
    )
    household_population_rows = [
        row
        for row in population_rows
        if str(row["date"]) == household_reference_date
    ]
    household_reference_population = {
        str(row["state"]): _number(row["population"]) * 1_000
        for row in household_population_rows
        if row.get("sex") == "both" and row.get("age") == "overall"
    }
    household_size = {
        state: round(
            household_reference_population[state]
            / _number(household_rows[state]["households"]),
            3,
        )
        for state in state_totals
    }
    disposable_share = {
        state: max(
            0.04,
            min(
                0.55,
                (
                    _number(hies_rows[state]["income_mean"])
                    - _number(hies_rows[state]["expenditure_mean"])
                )
                / _number(hies_rows[state]["income_mean"]),
            ),
        )
        for state in state_totals
    }

    cpi_rows = rows["cpi_state"]
    latest_cpi_date = max(str(row["date"]) for row in cpi_rows)
    cpi_by_state = {}
    for state in state_totals:
        state_rows = sorted(
            [row for row in cpi_rows if row["state"] == state],
            key=lambda row: str(row["date"]),
        )
        latest = state_rows[-1]
        year_ago = state_rows[-13] if len(state_rows) >= 13 else None
        cpi_by_state[state] = {
            "index": _number(latest["index"]),
            "yoy": (
                round(
                    (_number(latest["index"]) / _number(year_ago["index"]) - 1)
                    * 100,
                    3,
                )
                if year_ago
                else None
            ),
        }

    profile["version"] = "MY-CONSUMER-MACRO-2026.08.1"
    profile["country_code"] = "MY"
    profile["country_name"] = "Malaysia"
    profile["currency_code"] = "MYR"
    profile["currency_symbol"] = "RM"
    profile["status"] = "official_macro_calibrated_choice_prior"
    profile["claim"] = (
        "Malaysia adult age, binary sex, state population, state household income, "
        "income percentiles, expenditure and household-size margins are calibrated "
        "from DOSM/data.gov.my public aggregates. Administrative-district population, "
        "household income/expenditure and labour context are retained for geographic "
        "evidence. Behavioral traits and all choice coefficients remain unvalidated "
        "cross-market priors."
    )
    profile["sources"] = [
        {**dict(source), "source_type": "official_public_aggregate"}
        for source in manifest["sources"].values()
    ] + [
        {
            "source_id": "THAILAND_ENGINEERING_PRIOR_TRANSFER",
            "source_type": "cross_market_assumption",
            "observed": False,
            "note": (
                "Behavior and choice priors are inherited structurally from the "
                "Thailand development model and are not Malaysian estimates."
            ),
        }
    ]
    profile["limitations"] = [
        "DOSM inputs are aggregate margins, not linked household microdata; joint dependencies are synthesized.",
        "The population model excludes children; the 18-19 population is approximated as 40% of the DOSM 15-19 band.",
        "Household income and expenditure are not individual wages or disposable cash flow.",
        "Administrative-district population and household context use their own release dates and are not a substitute for enumeration-block microdata.",
        "Ethnicity is not used as a behavioral coefficient or targeting variable.",
        "Behavioral traits, category engagement, payment preferences and tourist shares remain unvalidated priors.",
        "Choice coefficients, WTP and conversion rates have not been fitted to Malaysian observed choices or sales.",
        "Forecast intervals remain prior-predictive and are not validated forecast intervals.",
    ]
    profile["population"] = {
        "registered_population_total": int(round(sum(state_totals.values()))),
        "population_reference_date": population_latest_date,
        "age_group": _normalize(age_counts),
        "gender": _normalize(gender_counts),
        "region": _normalize(region_totals),
        "province_by_region": province_by_region,
        "income_tier": {tier: 0.2 for tier in tier_ranges},
        "income_tier_by_region": {
            region: {tier: 0.2 for tier in tier_ranges}
            for region in REGION_STATES
        },
        "income_monthly_thb": income_midpoints,
        "income_monthly_local": income_midpoints,
        "income_currency": "MYR",
        "region_income_multiplier": {
            region: region_income[region] / national_income
            for region in REGION_STATES
        },
        "province_income_multiplier": province_income_multiplier,
        "official_state_household_income_myr": {
            state: _number(hies_rows[state]["income_mean"])
            for state in state_totals
        },
        "household_size_by_province": household_size,
        "province_disposable_income_share": disposable_share,
        "district_context": district_context,
        "tourist_share_by_region": {
            "Central": 0.08,
            "Northern": 0.05,
            "Southern": 0.04,
            "East Coast": 0.04,
            "East Malaysia": 0.06,
        },
        "latest_years": {
            "population": int(max(str(row["date"])[:4] for row in population_rows)),
            "income": int(max(str(row["date"])[:4] for row in rows["hies_state"])),
            "households": int(max(str(row["date"])[:4] for row in rows["households_state"])),
            "cpi": int(latest_cpi_date[:4]),
            "district_population": int(district_population_latest_date[:4]),
            "district_income": int(
                max(str(row["date"])[:4] for row in rows["hies_district"])
            ),
            "district_labour": int(
                max(str(row["date"])[:4] for row in rows["labour_district"])
            ),
        },
    }
    profile["behavior"]["disposable_income_share"] = {
        "mean": sum(
            disposable_share[state] * state_totals[state] for state in state_totals
        )
        / sum(state_totals.values()),
        "sd": 0.08,
    }
    profile["macro_context"] = {
        "status": "observed_official_context",
        "latest_cpi_date": latest_cpi_date,
        "source_count": 1,
        "national_cpi": {
            "year": int(latest_cpi_date[:4]),
            "month": int(latest_cpi_date[5:7]),
            "price_index": sum(
                cpi_by_state[state]["index"] * state_totals[state]
                for state in state_totals
            )
            / sum(state_totals.values()),
            "yoy": sum(
                float(cpi_by_state[state]["yoy"] or 0.0) * state_totals[state]
                for state in state_totals
            )
            / sum(state_totals.values()),
            "aggregation": "population_weighted_state_context_index",
        },
        "state_cpi": cpi_by_state,
        "district_context": {
            "status": "observed_official_aggregate_context",
            "district_count": len(district_context),
            "district_income_fallback_count": sum(
                1
                for item in district_context.values()
                if item["income_context_status"]
                == "official_state_aggregate_fallback"
            ),
            "district_labour_available_count": sum(
                1
                for item in district_context.values()
                if item["labour_context_status"]
                == "official_district_aggregate"
            ),
            "population_reference_date": district_population_latest_date,
            "income_reference_date": max(
                str(row["date"]) for row in rows["hies_district"]
            ),
            "labour_reference_date": max(
                str(row["date"]) for row in rows["labour_district"]
            ),
            "quantitative_effect": "location_context_only_until_geospatially_matched_and_backtested",
        },
        "quantitative_effect": "context_only_until_backtested",
    }
    profile["model_transfer"] = {
        "source_country": "TH",
        "target_country": "MY",
        "transferred_components": ["behavior_priors", "choice_coefficient_priors", "dynamics"],
        "status": "unvalidated_cross_market_prior",
    }
    validate_profile(profile)
    return profile


def write_profile(profile: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dict(profile), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
