"""Live, traceable geospatial evidence for Thailand venue studies.

Google Maps calls use the Cloud Run service account through Application Default
Credentials. Failures are returned as explicit lineage warnings so an offline
study can still complete with catalog fallbacks.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import google.auth
from google.auth.transport.requests import Request
import httpx

from simulation_core.population_grid import estimate_population_for_geojson
from world_model.thailand_geo import point_in_thailand


GEOCODING_URL = "https://geocode.googleapis.com/v4/geocode/address"
AREA_INSIGHTS_URL = "https://areainsights.googleapis.com/v1:computeInsights"
ISOCHRONE_URL = "https://isochrones.googleapis.com/v1/isochrones:generate"

POI_GROUPS: Dict[str, Sequence[str]] = {
    "restaurants": ("restaurant",),
    "cafes": ("cafe",),
    "bars_pubs": ("bar",),
    "shops": ("shopping_mall", "supermarket", "convenience_store"),
    "parking": ("parking",),
    "transit": ("transit_station", "train_station", "subway_station", "bus_station"),
    "tourism_lodging": ("tourist_attraction", "hotel"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _label_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _candidate_rows(study: Mapping[str, Any]) -> List[Dict[str, Any]]:
    facts = study.get("facts") or {}
    inputs = study.get("inputs") or {}
    raw = facts.get("candidate_locations") or inputs.get("candidate_locations") or []
    rows = [dict(item) for item in raw if isinstance(item, Mapping)]
    if not rows:
        location = facts.get("location") or inputs.get("location")
        if isinstance(location, Mapping):
            rows = [dict(location)]
    return rows[:10]


def _history_locations(study: Mapping[str, Any]) -> List[Dict[str, Any]]:
    inputs = study.get("inputs") or {}
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in inputs.get("venue_history") or []:
        if not isinstance(row, Mapping):
            continue
        label = str(row.get("location_label") or "").strip()
        visits = row.get("average_daily_visits")
        if not label or visits is None:
            continue
        try:
            visits_value = float(visits)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(visits_value) or visits_value <= 0:
            continue
        grouped[_label_key(label)] = {
            "label": label,
            "average_daily_visits": visits_value,
        }
    return list(grouped.values())[:20]


def _polygon_area_km2(geojson: Mapping[str, Any]) -> Optional[float]:
    geometry = geojson.get("geometry") if geojson.get("type") == "Feature" else geojson
    if not isinstance(geometry, Mapping):
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return None
    polygons = coordinates if geometry.get("type") == "MultiPolygon" else [coordinates]
    total = 0.0
    for polygon in polygons:
        if not polygon:
            continue
        for ring_index, ring in enumerate(polygon):
            if not isinstance(ring, list) or len(ring) < 3:
                continue
            mean_lat = sum(float(point[1]) for point in ring) / len(ring)
            scale_x = 111.320 * math.cos(math.radians(mean_lat))
            scale_y = 110.574
            area = 0.0
            for index, point in enumerate(ring):
                next_point = ring[(index + 1) % len(ring)]
                area += (
                    float(point[0]) * scale_x * float(next_point[1]) * scale_y
                    - float(next_point[0]) * scale_x * float(point[1]) * scale_y
                )
            signed = abs(area) / 2.0
            total += signed if ring_index == 0 else -signed
    return round(max(0.0, total), 4) if total > 0 else None


class GoogleGeospatialResearch:
    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        flag = os.environ.get("GEO_RESEARCH_ENABLED", "false").lower()
        self.enabled = enabled if enabled is not None else flag in {"1", "true", "yes"}
        self._client = client
        self._credentials = None
        self._project_id: Optional[str] = None
        self._auth_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(
            max(1, min(4, int(os.environ.get("GEO_RESEARCH_CONCURRENCY", "2"))))
        )

    async def _headers(self) -> Dict[str, str]:
        async with self._auth_lock:
            if self._credentials is None:
                credentials, project_id = await asyncio.to_thread(
                    google.auth.default,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                self._credentials = credentials
                self._project_id = project_id
            if not self._credentials.valid or self._credentials.expired:
                await asyncio.to_thread(self._credentials.refresh, Request())
            return {
                "Authorization": f"Bearer {self._credentials.token}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": (
                    os.environ.get("GOOGLE_CLOUD_PROJECT")
                    or self._project_id
                    or ""
                ),
            }

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = await self._headers()
        async with self._semaphore:
            if self._client is not None:
                response = await self._client.request(
                    method, url, headers=headers, json=json_body
                )
            else:
                async with httpx.AsyncClient(timeout=24.0) as client:
                    response = await client.request(
                        method, url, headers=headers, json=json_body
                    )
        response.raise_for_status()
        return response.json()

    async def _geocode(self, row: Mapping[str, Any]) -> Dict[str, Any]:
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        if latitude is not None and longitude is not None:
            lat, lng = float(latitude), float(longitude)
            if not point_in_thailand(lng, lat):
                raise ValueError("coordinates_outside_thailand")
            return {
                "latitude": lat,
                "longitude": lng,
                "formatted_address": str(row.get("label") or ""),
                "granularity": "user_supplied",
                "coordinate_source": "user_supplied",
            }
        label = str(row.get("label") or row.get("name") or "").strip()
        if not label:
            raise ValueError("missing_location_label")
        encoded = urllib.parse.quote(label, safe="")
        data = await self._request_json(
            "GET",
            f"{GEOCODING_URL}/{encoded}?regionCode=th&languageCode=th",
        )
        results = data.get("results") or []
        if not results:
            raise ValueError("geocoding_no_result")
        result = results[0]
        location = result.get("location") or {}
        lat = float(location["latitude"])
        lng = float(location["longitude"])
        if not point_in_thailand(lng, lat):
            raise ValueError("geocoding_result_outside_thailand")
        return {
            "latitude": lat,
            "longitude": lng,
            "formatted_address": result.get("formattedAddress") or label,
            "place_id": result.get("placeId"),
            "granularity": result.get("granularity"),
            "coordinate_source": "google_geocoding_v4",
        }

    async def _poi_count(
        self,
        latitude: float,
        longitude: float,
        place_types: Sequence[str],
    ) -> int:
        body = {
            "insights": ["INSIGHT_COUNT"],
            "filter": {
                "locationFilter": {
                    "circle": {
                        "latLng": {
                            "latitude": latitude,
                            "longitude": longitude,
                        },
                        "radius": 1000,
                    }
                },
                "typeFilter": {"includedTypes": list(place_types)},
                "operatingStatus": ["OPERATING_STATUS_OPERATIONAL"],
            },
        }
        data = await self._request_json("POST", AREA_INSIGHTS_URL, json_body=body)
        return int(data.get("count") or 0)

    async def _isochrone(
        self,
        latitude: float,
        longitude: float,
        minutes: int,
    ) -> Dict[str, Any]:
        body = {
            "location": {"latitude": latitude, "longitude": longitude},
            "travelDuration": f"{minutes * 60}s",
            "travelMode": "WALK",
            "routingPreference": "TRAFFIC_UNAWARE",
            "travelDirection": "TO",
            "enableSmoothing": True,
            "polygonFidelity": "HIGH",
        }
        data = await self._request_json("POST", ISOCHRONE_URL, json_body=body)
        raw_geojson = (data.get("isochrone") or {}).get("geoJson")
        if isinstance(raw_geojson, str):
            geojson = json.loads(raw_geojson)
        elif isinstance(raw_geojson, Mapping):
            geojson = dict(raw_geojson)
        else:
            geojson = {}
        area_km2 = _polygon_area_km2(geojson)
        population = estimate_population_for_geojson(geojson) or {
            "population_status": "population_grid_unavailable",
        }
        population_estimate = population.get("estimated_resident_population")
        density = (
            round(float(population_estimate) / area_km2, 1)
            if population_estimate is not None and area_km2
            else None
        )
        return {
            "minutes": minutes,
            "mode": "walking_network_isochrone",
            "data_class": "external_market_data",
            "area_km2": area_km2,
            "source": "google_isochrones",
            **population,
            "estimated_resident_density_per_km2": density,
        }

    async def _collect_location(
        self,
        row: Mapping[str, Any],
        *,
        include_isochrones: bool,
    ) -> Dict[str, Any]:
        label = str(row.get("label") or row.get("name") or "").strip()
        resolved = await self._geocode(row)
        latitude = float(resolved["latitude"])
        longitude = float(resolved["longitude"])

        poi_tasks = {
            key: asyncio.create_task(
                self._poi_count(latitude, longitude, place_types)
            )
            for key, place_types in POI_GROUPS.items()
        }
        catchment_tasks = (
            [
                asyncio.create_task(self._isochrone(latitude, longitude, minutes))
                for minutes in (5, 10, 15)
            ]
            if include_isochrones
            else []
        )
        observed_poi: Dict[str, int] = {}
        poi_errors: List[str] = []
        for key, task in poi_tasks.items():
            try:
                observed_poi[key] = await task
            except Exception as error:
                poi_errors.append(f"{key}:{type(error).__name__}")
        catchments: List[Dict[str, Any]] = []
        for task in catchment_tasks:
            try:
                catchments.append(await task)
            except Exception as error:
                poi_errors.append(f"isochrone:{type(error).__name__}")
        return {
            "label": label,
            **resolved,
            "observed_poi": observed_poi,
            "observed_poi_status": (
                "google_places_aggregate_live"
                if len(observed_poi) >= 4
                else "partial_external_observation"
            ),
            "catchments": sorted(catchments, key=lambda item: item["minutes"]),
            "data_source": "google_maps_platform",
            "collected_at": _utc_now(),
            "errors": poi_errors,
        }

    async def collect(self, study: Mapping[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "status": "disabled",
                "locations": {},
                "historical_locations": {},
                "warnings": ["实时地理采集未启用，使用版本化公开快照或明确的数据不足状态。"],
            }
        candidates = _candidate_rows(study)
        history = _history_locations(study)
        locations: Dict[str, Any] = {}
        historical_locations: Dict[str, Any] = {}
        warnings: List[str] = []

        for row in candidates:
            label = str(row.get("label") or row.get("name") or "").strip()
            try:
                locations[_label_key(label)] = await self._collect_location(
                    row, include_isochrones=True
                )
            except Exception as error:
                warnings.append(f"{label or '候选点'}：实时地理采集失败（{type(error).__name__}）。")
        for row in history:
            label = row["label"]
            try:
                evidence = await self._collect_location(
                    row, include_isochrones=False
                )
                evidence["average_daily_visits"] = row["average_daily_visits"]
                historical_locations[_label_key(label)] = evidence
            except Exception as error:
                warnings.append(f"{label}：历史门店地理特征采集失败（{type(error).__name__}）。")

        return {
            "status": (
                "observed"
                if len(locations) == len(candidates) and candidates
                else "partial"
                if locations
                else "unavailable"
            ),
            "version": "google-geospatial-worldpop-v2",
            "locations": locations,
            "historical_locations": historical_locations,
            "sources": [
                {
                    "name": "Google Geocoding API v4",
                    "role": "地址解析",
                    "data_class": "external_market_data",
                },
                {
                    "name": "Google Places Aggregate API",
                    "role": "候选点周边 1 公里营业中地点数量",
                    "data_class": "external_market_data",
                },
                {
                    "name": "Google Isochrones API",
                    "role": "5/10/15 分钟真实步行路网可达范围",
                    "data_class": "external_market_data",
                },
                {
                    "name": "WorldPop Thailand 2025 constrained population grid",
                    "role": "步行商圈常住人口估算（100 米源数据，生产环境聚合至约 500 米）",
                    "data_class": "external_modeled_population",
                    "license": "CC BY 4.0",
                    "doi": "10.5258/SOTON/WP00839",
                },
                {
                    "name": "Thailand NSO 2025 Population and Housing Census (early results)",
                    "role": "全国人口与家庭总量合理性参照，不用于虚构街区分布",
                    "data_class": "official_national_benchmark",
                },
            ],
            "warnings": warnings,
            "collected_at": _utc_now(),
        }
