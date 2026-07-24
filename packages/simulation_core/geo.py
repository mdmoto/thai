"""Traceable geographic and venue-operation analysis.

The module deliberately separates observed POI evidence from modelled demand.
It does not label public listings or radial catchments as measured footfall.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


OFFLINE_TYPES = {
    "VENUE_STUDY",
    "SITE_COMPARISON",
    "RESTAURANT",
    "CAFE",
    "BAR",
    "RETAIL",
    "OPERATING_SCENARIO",
}

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


def _catalog_root() -> Path:
    configured = os.environ.get("DATA_CATALOG_ROOT")
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data_catalog"
        if candidate.exists():
            return candidate
    return Path("/data_catalog")


def _load_catalog() -> Dict[str, Any]:
    path = _catalog_root() / "geo" / "chiang_mai_market_context_v1.json"
    if not path.exists():
        return {"dataset_id": "unavailable", "sources": [], "zones": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


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


def _venue_competitor_count(venue_type: str, observed: Mapping[str, Any]) -> int:
    key = {
        "RESTAURANT": "restaurants",
        "CAFE": "cafes",
        "BAR": "bars_pubs",
        "RETAIL": "shops",
    }.get(venue_type, "restaurants")
    return int(observed.get(key, 0) or 0)


def _score_location(
    venue_type: str,
    observed: Mapping[str, Any],
    priors: Mapping[str, Any],
    supplied: Mapping[str, Any],
) -> Dict[str, float]:
    audience = _as_float(supplied.get("target_audience_index"))
    if audience is None:
        if venue_type == "BAR":
            audience = float(priors.get("tourism_index", 55))
        elif venue_type == "CAFE":
            audience = (
                float(priors.get("office_student_index", 55)) * 0.65
                + float(priors.get("tourism_index", 55)) * 0.35
            )
        else:
            audience = float(priors.get("resident_demand_index", 55))
    tourism = _as_float(supplied.get("tourism_index"))
    if tourism is None:
        tourism = float(priors.get("tourism_index", 50))
    access = _as_float(supplied.get("transit_access_index"))
    if access is None:
        access = float(priors.get("transit_access_index", 55))
    parking = _as_float(supplied.get("parking_score"))
    if parking is None:
        parking = min(100.0, 35.0 + math.log1p(float(observed.get("parking", 0))) * 12.0)
    competitors = _venue_competitor_count(venue_type, observed)
    activity = min(
        100.0,
        22.0
        + math.log1p(sum(float(value or 0) for value in observed.values())) * 11.0,
    )
    saturation = min(100.0, math.log1p(competitors) * 17.0)
    score = (
        audience * 0.30
        + access * 0.19
        + tourism * (0.19 if venue_type == "BAR" else 0.11)
        + parking * 0.10
        + activity * 0.22
        - saturation * 0.12
    )
    return {
        "target_audience_index": round(audience, 1),
        "tourism_index": round(tourism, 1),
        "access_index": round(access, 1),
        "parking_index": round(parking, 1),
        "market_activity_index": round(activity, 1),
        "competition_saturation_index": round(saturation, 1),
        "site_score": round(max(0.0, min(100.0, score)), 1),
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


def _operating_profile(
    venue_type: str,
    site_score: float,
    capacity: int,
    average_check: float,
) -> Dict[str, Any]:
    profile = HOURLY_PRIORS.get(venue_type, HOURLY_PRIORS["RESTAURANT"])
    weights = profile["weights"]
    total_weight = float(sum(weights))
    daily_visits = max(
        8,
        int(round(capacity * float(profile["turnover"]) * (0.55 + site_score / 130))),
    )
    hourly = []
    peak_utilization = 0.0
    for hour, weight in zip(profile["hours"], weights):
        visits = daily_visits * float(weight) / total_weight
        concurrent = visits * float(profile["service_minutes"]) / 60.0
        utilization = concurrent / max(1, capacity)
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
        "queue_risk": (
            "high" if peak_utilization >= 0.95
            else "medium" if peak_utilization >= 0.72
            else "low"
        ),
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
) -> Optional[Dict[str, Any]]:
    normalized_type = study_type.upper()
    normalized_venue = venue_type.upper()
    if normalized_type not in OFFLINE_TYPES and normalized_venue not in HOURLY_PRIORS:
        return None

    catalog = _load_catalog()
    zones = catalog.get("zones", [])
    candidates = _candidate_records(inputs)
    locations = []
    for index, candidate in enumerate(candidates):
        label = str(candidate.get("label") or candidate.get("name") or f"Candidate {index + 1}")
        zone = _match_zone(label, zones)
        observed = dict(zone.get("observed_poi", {})) if zone else {}
        priors = dict(zone.get("model_priors", {})) if zone else {}
        latitude = _as_float(candidate.get("latitude"))
        longitude = _as_float(candidate.get("longitude"))
        if latitude is None and zone:
            latitude = float(zone["latitude"])
        if longitude is None and zone:
            longitude = float(zone["longitude"])
        scores = _score_location(normalized_venue, observed, priors, candidate)
        locations.append(
            {
                "id": str(candidate.get("id") or zone.get("zone_id") if zone else f"site_{index + 1}"),
                "name": label,
                "matched_zone": zone.get("name") if zone else None,
                "latitude": latitude,
                "longitude": longitude,
                "coordinate_status": "resolved" if latitude is not None and longitude is not None else "missing",
                "observed_poi": observed,
                "observed_poi_status": "public_snapshot" if observed else "not_observed",
                **scores,
            }
        )
    locations.sort(key=lambda item: item["site_score"], reverse=True)
    for rank, item in enumerate(locations, start=1):
        item["rank"] = rank

    primary_score = float(locations[0]["site_score"]) if locations else 50.0
    venue_capacity = max(1, int(capacity or 50))
    check = max(1.0, float(average_check or 250.0))
    operations = _operating_profile(
        normalized_venue if normalized_venue in HOURLY_PRIORS else "RESTAURANT",
        primary_score,
        venue_capacity,
        check,
    )
    return {
        "schema_version": "1",
        "dataset_id": catalog.get("dataset_id"),
        "venue_type": normalized_venue,
        "locations": locations,
        "heatmap": _heatmap(locations),
        "catchments": [
            {
                "minutes": minutes,
                "radius_km": round(minutes * 0.08, 2),
                "mode": "walking_radial_proxy",
                "data_class": "model_inference",
            }
            for minutes in (5, 10, 15)
        ],
        "operations": operations,
        "legend": [
            {"key": "observed", "label": "真实观测", "color": "#4f8cff"},
            {"key": "external", "label": "外部市场数据", "color": "#9b8cff"},
            {"key": "model_inference", "label": "模型推算", "color": "#ff9f43"},
            {"key": "missing", "label": "数据不足", "color": "#64748b"},
        ],
        "sources": catalog.get("sources", []),
        "warnings": [
            "需求热力图和小时客流是模型推算，不是手机信令、门店探针或真实到店记录。",
            "5/10/15 分钟范围当前为步行半径代理，不是道路网络等时圈。",
            "OSM POI 数量代表公开地图记录，不代表交易量、评价质量或实际客流。",
        ],
    }
