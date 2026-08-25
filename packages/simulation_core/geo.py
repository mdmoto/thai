"""Traceable geographic and venue-operation analysis.

Observed geographic features, model assumptions and customer operating records
remain separate throughout the result. A score is never presented as measured
footfall, and missing evidence is never silently replaced with a city-wide
constant.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from simulation_core.population_grid import estimate_population_for_geojson
from world_model.country_geo import province_for_point


OFFLINE_TYPES = {
    "VENUE_STUDY",
    "SITE_COMPARISON",
    "RESTAURANT",
    "CAFE",
    "BAR",
    "RETAIL",
    "OPERATING_SCENARIO",
}

# These are explicit operating priors, used only when customer observations are
# unavailable. They are not Thai footfall measurements.
HOURLY_PRIORS = {
    "RESTAURANT": {
        "hours": list(range(10, 23)),
        "weights": [2, 4, 8, 12, 7, 4, 4, 6, 10, 14, 15, 10, 4],
        "service_minutes": 62,
        "turnover": 1.55,
    },
    "CAFE": {
        "hours": list(range(7, 21)),
        "weights": [5, 8, 10, 9, 7, 8, 10, 12, 13, 12, 10, 8, 6, 3],
        "service_minutes": 88,
        "turnover": 1.15,
    },
    "BAR": {
        "hours": [18, 19, 20, 21, 22, 23, 0, 1, 2],
        "weights": [3, 5, 8, 12, 16, 18, 17, 13, 8],
        "service_minutes": 105,
        "turnover": 0.95,
    },
    "RETAIL": {
        "hours": list(range(9, 22)),
        "weights": [3, 4, 5, 6, 8, 9, 9, 8, 9, 11, 12, 10, 6],
        "service_minutes": 24,
        "turnover": 2.6,
    },
}

SCORE_WEIGHTS = {
    "target_audience_index": 0.27,
    "access_index": 0.17,
    "tourism_index": 0.10,
    "parking_index": 0.08,
    "market_activity_index": 0.23,
    "province_income_context_index": 0.08,
    "competition_saturation_index": -0.13,
}


def _catalog_root() -> Path:
    configured = os.environ.get("DATA_CATALOG_ROOT")
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data_catalog"
        if candidate.exists():
            return candidate
    return Path("/data_catalog")


def _load_json(path: Path, fallback: Mapping[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(fallback)
    return json.loads(path.read_text(encoding="utf-8"))


def _load_catalog(country_code: str) -> Dict[str, Any]:
    if country_code != "TH":
        return {"dataset_id": "country_catalog_unavailable", "sources": [], "zones": []}
    return _load_json(
        _catalog_root() / "geo" / "chiang_mai_market_context_v1.json",
        {"dataset_id": "unavailable", "sources": [], "zones": []},
    )


def _load_macro_context(country_code: str) -> Dict[str, Any]:
    profile_name = (
        "malaysia_consumer_products_macro_v1.json"
        if country_code == "MY"
        else "thailand_consumer_products_macro_v1.json"
    )
    return _load_json(
        _catalog_root() / profile_name,
        {"calibration": {}},
    )


def _as_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _label_key(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _match_zone(label: str, zones: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    normalized = label.casefold()
    for zone in zones:
        terms = [zone.get("name", ""), *zone.get("aliases", [])]
        if any(str(term).casefold() in normalized for term in terms if term):
            return zone
    return None


def _candidate_records(inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw = inputs.get("candidate_locations") or []
    candidates = [dict(item) for item in raw if isinstance(item, Mapping)]
    if not candidates and isinstance(inputs.get("location"), Mapping):
        candidates = [dict(inputs["location"])]
    return candidates


def _count_index(value: float, reference: float) -> float:
    return min(100.0, max(0.0, 100.0 * (1.0 - math.exp(-max(0.0, value) / reference))))


def _radial_catchments_with_population(
    latitude: float,
    longitude: float,
    country_code: str,
) -> List[Dict[str, Any]]:
    """Return disclosed straight-line catchments when road isochrones are absent."""
    catchments: List[Dict[str, Any]] = []
    longitude_scale = max(
        0.001,
        111.320 * math.cos(math.radians(latitude)),
    )
    for minutes in (5, 10, 15):
        radius_km = minutes * 0.08
        ring = []
        for index in range(25):
            angle = math.tau * index / 24
            ring.append(
                [
                    longitude + radius_km * math.cos(angle) / longitude_scale,
                    latitude + radius_km * math.sin(angle) / 110.574,
                ]
            )
        population = estimate_population_for_geojson(
            {"type": "Polygon", "coordinates": [ring]},
            country_code=country_code,
        ) or {"population_status": "population_grid_unavailable"}
        catchments.append(
            {
                "minutes": minutes,
                "radius_km": round(radius_km, 2),
                "mode": "walking_radial_proxy",
                "data_class": "external_modeled_population",
                **population,
            }
        )
    return catchments


def _venue_competitor_count(venue_type: str, observed: Mapping[str, Any]) -> float:
    key = {
        "RESTAURANT": "restaurants",
        "CAFE": "cafes",
        "BAR": "bars_pubs",
        "RETAIL": "shops",
    }.get(venue_type, "restaurants")
    return float(observed.get(key, 0) or 0)


def _province_context(
    latitude: Optional[float],
    longitude: Optional[float],
    macro: Mapping[str, Any],
    country_code: str,
) -> Dict[str, Any]:
    if latitude is None or longitude is None:
        return {"province": None, "province_income_context_index": 50.0}
    province = province_for_point(country_code, longitude, latitude)
    if not province:
        return {"province": None, "province_income_context_index": 50.0}
    name = str(province.get("name") or "")
    calibration = macro.get("calibration") or {}
    income_multiplier = (
        calibration.get("province_income_multiplier") or {}
    ).get(name)
    if income_multiplier is None:
        return {"province": name, "province_income_context_index": 50.0}
    return {
        "province": name,
        "province_income_context_index": round(
            min(85.0, max(25.0, 50.0 * float(income_multiplier))),
            1,
        ),
    }


def _observed_feature_scores(
    venue_type: str,
    observed: Mapping[str, Any],
    supplied: Mapping[str, Any],
    province_income_index: float,
) -> Dict[str, float]:
    restaurants = float(observed.get("restaurants", 0) or 0)
    cafes = float(observed.get("cafes", 0) or 0)
    bars = float(observed.get("bars_pubs", 0) or 0)
    shops = float(observed.get("shops", 0) or 0)
    transit = float(observed.get("transit", 0) or 0)
    tourism = float(observed.get("tourism_lodging", 0) or 0)
    parking = float(observed.get("parking", 0) or 0)
    competitor = _venue_competitor_count(venue_type, observed)

    if venue_type == "CAFE":
        audience_count = transit * 4.0 + shops * 1.8 + tourism * 1.1 + restaurants * 0.35
    elif venue_type == "BAR":
        audience_count = tourism * 3.0 + bars * 0.7 + restaurants * 0.8 + transit * 2.2
    elif venue_type == "RETAIL":
        audience_count = shops * 1.5 + transit * 3.2 + tourism * 0.7
    else:
        audience_count = restaurants * 0.35 + shops * 1.2 + tourism * 1.7 + transit * 2.5

    total_activity = restaurants + cafes + bars + shops + tourism + transit
    scores = {
        "target_audience_index": _count_index(audience_count, 105.0),
        "tourism_index": _count_index(tourism, 24.0),
        "access_index": _count_index(transit, 12.0),
        "parking_index": _count_index(parking, 10.0),
        "market_activity_index": _count_index(total_activity, 170.0),
        "competition_saturation_index": _count_index(competitor, 55.0),
        "province_income_context_index": province_income_index,
    }
    supplied_fields = {
        "target_audience_index": "target_audience_index",
        "tourism_index": "tourism_index",
        "access_index": "transit_access_index",
        "parking_index": "parking_score",
    }
    for output_key, input_key in supplied_fields.items():
        value = _as_float(supplied.get(input_key))
        if value is not None:
            scores[output_key] = min(100.0, max(0.0, value))
    return {key: round(value, 1) for key, value in scores.items()}


def _legacy_prior_scores(
    venue_type: str,
    observed: Mapping[str, Any],
    priors: Mapping[str, Any],
    supplied: Mapping[str, Any],
    province_income_index: float,
) -> Dict[str, float]:
    audience = _as_float(supplied.get("target_audience_index"))
    if audience is None:
        if venue_type == "BAR":
            audience = float(priors.get("tourism_index", 50))
        elif venue_type == "CAFE":
            audience = (
                float(priors.get("office_student_index", 50)) * 0.65
                + float(priors.get("tourism_index", 50)) * 0.35
            )
        else:
            audience = float(priors.get("resident_demand_index", 50))
    return {
        "target_audience_index": round(audience, 1),
        "tourism_index": round(float(priors.get("tourism_index", 50)), 1),
        "access_index": round(float(priors.get("transit_access_index", 50)), 1),
        "parking_index": round(
            min(100.0, 35.0 + math.log1p(float(observed.get("parking", 0) or 0)) * 12.0),
            1,
        ),
        "market_activity_index": round(
            _count_index(sum(float(value or 0) for value in observed.values()), 170.0),
            1,
        ),
        "competition_saturation_index": round(
            _count_index(_venue_competitor_count(venue_type, observed), 55.0),
            1,
        ),
        "province_income_context_index": province_income_index,
    }


def _weighted_site_score(scores: Mapping[str, float]) -> float:
    raw = sum(float(scores[key]) * weight for key, weight in SCORE_WEIGHTS.items())
    # Negative competition weight lowers the maximum, so rescale the usable range.
    return round(min(100.0, max(0.0, (raw + 13.0) / 1.03)), 1)


def _catchment_population(
    catchments: Sequence[Mapping[str, Any]],
    minutes: int = 15,
) -> Optional[float]:
    exact = [
        item
        for item in catchments
        if int(item.get("minutes") or 0) == minutes
        and _as_float(item.get("estimated_resident_population")) is not None
    ]
    candidates = exact or [
        item
        for item in catchments
        if _as_float(item.get("estimated_resident_population")) is not None
    ]
    if not candidates:
        return None
    selected = max(candidates, key=lambda item: int(item.get("minutes") or 0))
    return _as_float(selected.get("estimated_resident_population"))


def _footfall_opportunity(
    feature_scores: Mapping[str, float],
    resident_population_index: Optional[float],
) -> Dict[str, Any]:
    if resident_population_index is None:
        return {
            "footfall_opportunity_index": None,
            "footfall_opportunity_status": "insufficient_population_evidence",
        }
    value = (
        resident_population_index * 0.35
        + float(feature_scores["access_index"]) * 0.20
        + float(feature_scores["market_activity_index"]) * 0.20
        + float(feature_scores["tourism_index"]) * 0.10
        + float(feature_scores["target_audience_index"]) * 0.15
    )
    return {
        "footfall_opportunity_index": round(min(100.0, max(0.0, value)), 1),
        "footfall_opportunity_status": "modeled_opportunity_not_measured_footfall",
    }


def _calibrated_site_scores(
    locations: Sequence[Mapping[str, Any]],
    history_evidence: Mapping[str, Any],
    venue_type: str,
) -> Optional[Dict[str, Any]]:
    feature_names = list(SCORE_WEIGHTS)
    x_rows: List[List[float]] = []
    y_rows: List[float] = []
    for evidence in history_evidence.values():
        observed = evidence.get("observed_poi") or {}
        visits = _as_float(evidence.get("average_daily_visits"))
        if visits is None or not observed:
            continue
        scores = _observed_feature_scores(
            venue_type, observed, {}, 50.0
        )
        x_rows.append([float(scores[name]) for name in feature_names])
        y_rows.append(math.log1p(visits))
    if len(x_rows) < 4 or len(locations) < 1:
        return None
    matrix = np.asarray(x_rows, dtype=float)
    target = np.asarray(y_rows, dtype=float)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales < 1e-6] = 1.0
    standardized = (matrix - means) / scales
    design = np.column_stack([np.ones(len(standardized)), standardized])
    penalty = np.eye(design.shape[1]) * 2.0
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        design.T @ design + penalty,
        design.T @ target,
    )
    predictions: Dict[str, float] = {}
    for location in locations:
        row = np.asarray(
            [float(location[name]) for name in feature_names],
            dtype=float,
        )
        prediction = float(
            coefficients[0]
            + ((row - means) / scales) @ coefficients[1:]
        )
        predictions[str(location["id"])] = prediction
    values = list(predictions.values())
    low, high = min(values), max(values)
    if high - low < 1e-9:
        normalized = {key: 50.0 for key in predictions}
    else:
        normalized = {
            key: round(35.0 + 60.0 * (value - low) / (high - low), 1)
            for key, value in predictions.items()
        }
    return {
        "scores": normalized,
        "sample_size": len(x_rows),
        "status": "customer_branch_traffic_fit_unvalidated",
        "method": "ridge_fit_on_log_average_daily_visits",
    }


def _heatmap(locations: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    resolved = [
        item for item in locations
        if item.get("latitude") is not None and item.get("longitude") is not None
    ]
    if not resolved:
        return []
    center_lat = sum(float(item["latitude"]) for item in resolved) / len(resolved)
    center_lng = sum(float(item["longitude"]) for item in resolved) / len(resolved)
    cells = []
    for row in range(-4, 5):
        for col in range(-4, 5):
            latitude = center_lat + row * 0.0045
            longitude = center_lng + col * 0.0045
            intensity = 0.0
            for item in resolved:
                distance_sq = (
                    ((latitude - float(item["latitude"])) / 0.009) ** 2
                    + ((longitude - float(item["longitude"])) / 0.009) ** 2
                )
                intensity += float(item["site_score"]) * math.exp(-distance_sq / 2)
            cells.append(
                {
                    "latitude": round(latitude, 6),
                    "longitude": round(longitude, 6),
                    "intensity": round(min(100.0, intensity), 1),
                    "data_class": "model_inference",
                }
            )
    return cells


def _history_operating_profile(
    venue_history: Sequence[Mapping[str, Any]],
    capacity: int,
    average_check: float,
) -> Optional[Dict[str, Any]]:
    hourly_totals: Dict[int, float] = {}
    hourly_rows = 0
    dates = set()
    service_values: List[float] = []
    daily_values: List[float] = []
    for row in venue_history:
        hour = _as_float(row.get("hour"))
        visits = _as_float(row.get("visits"))
        if hour is not None and visits is not None and 0 <= hour <= 23 and visits >= 0:
            hourly_totals[int(hour)] = hourly_totals.get(int(hour), 0.0) + visits
            hourly_rows += 1
            if row.get("date"):
                dates.add(str(row["date"]))
        service = _as_float(row.get("service_minutes"))
        if service is not None and 3 <= service <= 360:
            service_values.append(service)
        daily = _as_float(row.get("average_daily_visits"))
        if daily is not None and daily > 0:
            daily_values.append(daily)
    if len(hourly_totals) < 4 or (hourly_rows < 14 and sum(hourly_totals.values()) < 100):
        return None
    divisor = max(1, len(dates))
    daily_visits = (
        statistics.median(daily_values)
        if daily_values
        else sum(hourly_totals.values()) / divisor
    )
    service_minutes = statistics.median(service_values) if service_values else 60.0
    hourly = []
    peak_utilization = 0.0
    for hour in sorted(hourly_totals):
        visits_value = hourly_totals[hour] / divisor
        utilization = visits_value * service_minutes / 60.0 / max(1, capacity)
        peak_utilization = max(peak_utilization, utilization)
        hourly.append(
            {
                "hour": f"{hour:02d}:00",
                "visits": round(visits_value, 1),
                "capacity_utilization": round(utilization, 3),
                "data_class": "customer_observation",
            }
        )
    return {
        "daily_visit_prior": round(daily_visits, 1),
        "daily_revenue_index_thb": round(daily_visits * average_check, 0),
        "peak_capacity_utilization": round(peak_utilization, 3),
        "queue_risk": "high" if peak_utilization >= 0.95 else "medium" if peak_utilization >= 0.72 else "low",
        "service_minutes_prior": round(service_minutes, 1),
        "hourly_demand": hourly,
        "status": "customer_operations_calibrated_unvalidated",
        "calibration_rows": hourly_rows,
        "calibration_days": len(dates),
    }


def _operating_profile(
    venue_type: str,
    site_score: float,
    capacity: int,
    average_check: float,
    venue_history: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    calibrated = _history_operating_profile(venue_history, capacity, average_check)
    if calibrated:
        return calibrated
    profile = HOURLY_PRIORS.get(venue_type, HOURLY_PRIORS["RESTAURANT"])
    total_weight = float(sum(profile["weights"]))
    daily_visits = max(
        8,
        int(round(capacity * float(profile["turnover"]) * (0.55 + site_score / 130))),
    )
    hourly = []
    peak_utilization = 0.0
    for hour, weight in zip(profile["hours"], profile["weights"]):
        visits = daily_visits * float(weight) / total_weight
        utilization = visits * float(profile["service_minutes"]) / 60.0 / max(1, capacity)
        peak_utilization = max(peak_utilization, utilization)
        hourly.append(
            {
                "hour": f"{hour:02d}:00",
                "visits": round(visits, 1),
                "capacity_utilization": round(utilization, 3),
                "data_class": "model_inference",
            }
        )
    return {
        "daily_visit_prior": daily_visits,
        "daily_revenue_index_thb": round(daily_visits * average_check, 0),
        "peak_capacity_utilization": round(peak_utilization, 3),
        "queue_risk": "high" if peak_utilization >= 0.95 else "medium" if peak_utilization >= 0.72 else "low",
        "service_minutes_prior": profile["service_minutes"],
        "hourly_demand": hourly,
        "status": "operating_prior_not_observed",
    }


def build_geo_analysis(
    *,
    study_type: str,
    venue_type: str,
    inputs: Mapping[str, Any],
    capacity: Optional[int],
    average_check: Optional[float],
    external_evidence: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    normalized_type = study_type.upper()
    normalized_venue = venue_type.upper()
    if normalized_type not in OFFLINE_TYPES and normalized_venue not in HOURLY_PRIORS:
        return None

    country_code = str(inputs.get("country_code") or "TH").upper()
    catalog = _load_catalog(country_code)
    macro = _load_macro_context(country_code)
    zones = catalog.get("zones", [])
    candidates = _candidate_records(inputs)
    live = external_evidence or {}
    live_locations = live.get("locations") or {}
    locations: List[Dict[str, Any]] = []
    catchments: List[Dict[str, Any]] = []

    for index, candidate in enumerate(candidates):
        label = str(candidate.get("label") or candidate.get("name") or f"Candidate {index + 1}")
        evidence = live_locations.get(_label_key(label)) or {}
        zone = _match_zone(label, zones)
        observed = dict(evidence.get("observed_poi") or {})
        observed_status = evidence.get("observed_poi_status")
        if not observed and zone and zone.get("observed_poi"):
            observed = dict(zone.get("observed_poi") or {})
            observed_status = "osm_versioned_snapshot"
        priors = dict(zone.get("model_priors", {})) if zone else {}
        latitude = _as_float(evidence.get("latitude"))
        longitude = _as_float(evidence.get("longitude"))
        if latitude is None:
            latitude = _as_float(candidate.get("latitude"))
        if longitude is None:
            longitude = _as_float(candidate.get("longitude"))
        if latitude is None and zone:
            latitude = float(zone["latitude"])
        if longitude is None and zone:
            longitude = float(zone["longitude"])
        province_context = _province_context(
            latitude,
            longitude,
            macro,
            country_code,
        )
        evidence_catchments = [
            dict(item)
            for item in evidence.get("catchments") or []
            if isinstance(item, Mapping)
        ]
        if not evidence_catchments and latitude is not None and longitude is not None:
            evidence_catchments = _radial_catchments_with_population(
                latitude,
                longitude,
                country_code,
            )
        resident_population = _catchment_population(evidence_catchments)
        resident_population_index = (
            round(_count_index(resident_population, 20_000.0), 1)
            if resident_population is not None
            else None
        )

        if observed:
            feature_scores = _observed_feature_scores(
                normalized_venue,
                observed,
                candidate,
                province_context["province_income_context_index"],
            )
            if resident_population_index is not None:
                feature_scores["target_audience_index"] = round(
                    feature_scores["target_audience_index"] * 0.60
                    + resident_population_index * 0.40,
                    1,
                )
                score_status = (
                    "observed_geospatial_population_features_with_unvalidated_weights"
                )
            else:
                score_status = "observed_geospatial_features_with_unvalidated_weights"
        elif priors:
            feature_scores = _legacy_prior_scores(
                normalized_venue,
                observed,
                priors,
                candidate,
                province_context["province_income_context_index"],
            )
            if resident_population_index is not None:
                feature_scores["target_audience_index"] = round(
                    feature_scores["target_audience_index"] * 0.60
                    + resident_population_index * 0.40,
                    1,
                )
                score_status = "population_grid_with_legacy_prior_unvalidated"
            else:
                score_status = "legacy_engineering_prior_unvalidated"
        elif resident_population_index is not None:
            feature_scores = {
                "target_audience_index": round(
                    50.0 * 0.60 + resident_population_index * 0.40,
                    1,
                ),
                "tourism_index": 50.0,
                "access_index": 50.0,
                "parking_index": 50.0,
                "market_activity_index": 50.0,
                "competition_saturation_index": 50.0,
                "province_income_context_index": province_context[
                    "province_income_context_index"
                ],
            }
            score_status = "population_only_geospatial_evidence_unvalidated"
        else:
            feature_scores = {
                "target_audience_index": 50.0,
                "tourism_index": 50.0,
                "access_index": 50.0,
                "parking_index": 50.0,
                "market_activity_index": 50.0,
                "competition_saturation_index": 50.0,
                "province_income_context_index": province_context[
                    "province_income_context_index"
                ],
            }
            score_status = "insufficient_geospatial_evidence"
        location_id = str(
            candidate.get("id")
            or (zone.get("zone_id") if zone else f"site_{index + 1}")
        )
        item = {
            "id": location_id,
            "name": label,
            "formatted_address": evidence.get("formatted_address"),
            "matched_zone": zone.get("name") if zone else None,
            "province": province_context["province"],
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_status": "resolved" if latitude is not None and longitude is not None else "missing",
            "coordinate_source": evidence.get("coordinate_source") or ("catalog_snapshot" if zone else None),
            "observed_poi": observed,
            "observed_poi_status": observed_status or "not_observed",
            "score_status": score_status,
            "score_weights": SCORE_WEIGHTS,
            "resident_catchment_population_15m": (
                int(round(resident_population))
                if resident_population is not None
                else None
            ),
            "resident_population_index": resident_population_index,
            **feature_scores,
        }
        item.update(_footfall_opportunity(feature_scores, resident_population_index))
        item["site_score"] = _weighted_site_score(feature_scores)
        locations.append(item)
        for catchment in evidence_catchments:
            catchments.append(
                {
                    **dict(catchment),
                    "location_id": location_id,
                    "location_name": label,
                }
            )

    calibrated = _calibrated_site_scores(
        locations,
        live.get("historical_locations") or {},
        normalized_venue,
    )
    if calibrated:
        for item in locations:
            item["site_score"] = calibrated["scores"][item["id"]]
            item["score_status"] = calibrated["status"]
            item["calibration_sample_size"] = calibrated["sample_size"]
    locations.sort(key=lambda item: item["site_score"], reverse=True)
    for rank, item in enumerate(locations, start=1):
        item["rank"] = rank

    if not catchments:
        for item in locations:
            for minutes in (5, 10, 15):
                catchments.append(
                    {
                        "location_id": item["id"],
                        "location_name": item["name"],
                        "minutes": minutes,
                        "radius_km": round(minutes * 0.08, 2),
                        "mode": "walking_radial_proxy",
                        "data_class": "model_inference",
                    }
                )

    primary_score = float(locations[0]["site_score"]) if locations else 50.0
    operations = _operating_profile(
        normalized_venue if normalized_venue in HOURLY_PRIORS else "RESTAURANT",
        primary_score,
        max(1, int(capacity or 50)),
        max(1.0, float(average_check or 250.0)),
        [
            row for row in inputs.get("venue_history") or []
            if isinstance(row, Mapping)
        ],
    )
    sources = [
        *(live.get("sources") or []),
        *catalog.get("sources", []),
        {
            "name": (
                "Malaysia DOSM public state aggregates"
                if country_code == "MY"
                else "Thailand NSO public macro aggregates"
            ),
            "role": "province income context",
            "data_class": "external_market_data",
        },
    ]
    warnings = [
        *(live.get("warnings") or []),
        "综合机会分使用地点特征加权公式；除标记为客户门店校准外，权重尚未用真实门店业绩验证。",
        "购买倾向来自消费者选择模型，地点层只提供有界的可达性与机会修正，不代表真实成交率。",
        "需求热力图是模型可视化，不是手机信令、门店探针或真实到店记录。",
        "到店机会指数结合步行商圈常住人口、交通、商业活跃和旅游设施；它不是实测客流，也不是白天流动人口。",
        (
            "小时访问曲线已使用客户经营记录校准，但仍需留店验证。"
            if operations["status"] == "customer_operations_calibrated_unvalidated"
            else "小时访问、服务时长和翻台率为未观测行业先验。"
        ),
    ]
    if any(item["mode"] == "walking_radial_proxy" for item in catchments):
        warnings.append("部分或全部步行范围为直线半径代理，不是道路网络等时圈。")
    if any(item["score_status"] == "insufficient_geospatial_evidence" for item in locations):
        warnings.append("至少一个候选点缺少可验证地理数据；该点仅显示中性占位，不应据此下最终选址结论。")

    return {
        "schema_version": "3",
        "dataset_id": live.get("version") or catalog.get("dataset_id"),
        "geospatial_status": live.get("status") or "catalog_fallback",
        "score_method": (
            calibrated["method"]
            if calibrated
            else (
                "observed_feature_population_weighting_unvalidated"
                if any(
                    item.get("resident_catchment_population_15m") is not None
                    for item in locations
                )
                else "observed_feature_weighting_unvalidated"
            )
        ),
        "score_calibration": calibrated,
        "venue_type": normalized_venue,
        "locations": locations,
        "heatmap": _heatmap(locations),
        "catchments": catchments,
        "operations": operations,
        "legend": [
            {"key": "observed", "label": "真实观测", "color": "#4f8cff"},
            {"key": "external", "label": "外部市场数据", "color": "#9b8cff"},
            {"key": "customer", "label": "客户经营数据", "color": "#5dd8c1"},
            {"key": "model_inference", "label": "模型推算", "color": "#ff9f43"},
            {"key": "missing", "label": "数据不足", "color": "#64748b"},
        ],
        "sources": sources,
        "warnings": warnings,
    }
