"""Thailand boundary helpers for synthetic visualization coordinates."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple


def _catalog_path() -> Path:
    configured = os.environ.get("DATA_CATALOG_ROOT")
    if configured:
        return (
            Path(configured)
            / "geo"
            / "thailand_adm1_boundaries_v1.json"
        )
    return (
        Path(__file__).resolve().parents[2]
        / "data_catalog"
        / "geo"
        / "thailand_adm1_boundaries_v1.json"
    )


def _normalize(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]",
        "",
        value.lower().replace("province", ""),
    )


PROVINCE_ALIASES = {
    "ayutthaya": "phranakhonsiayutthaya",
}


@lru_cache(maxsize=1)
def load_thailand_boundaries() -> Dict[str, Any]:
    with _catalog_path().open("r", encoding="utf-8") as handle:
        catalog = json.load(handle)
    provinces = {
        _normalize(item["name"]): item
        for item in catalog["provinces"]
    }
    catalog["_province_lookup"] = provinces
    return catalog


def _point_in_ring(
    longitude: float,
    latitude: float,
    ring: Sequence[Sequence[float]],
) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses:
            boundary_x = (
                (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            )
            if longitude < boundary_x:
                inside = not inside
        previous = current
    return inside


def province_boundary(province_name: str) -> Mapping[str, Any] | None:
    key = _normalize(province_name)
    key = PROVINCE_ALIASES.get(key, key)
    return load_thailand_boundaries()["_province_lookup"].get(key)


def point_in_province(
    longitude: float,
    latitude: float,
    province_name: str,
) -> bool:
    province = province_boundary(province_name)
    if not province:
        return False
    return any(
        _point_in_ring(longitude, latitude, ring)
        for ring in province["rings"]
    )


def point_in_thailand(longitude: float, latitude: float) -> bool:
    return any(
        _point_in_ring(longitude, latitude, ring)
        for ring in load_thailand_boundaries()["country_rings"]
    )


def province_for_point(
    longitude: float,
    latitude: float,
) -> Mapping[str, Any] | None:
    """Return the ADM1 record containing a point, if it is in Thailand."""
    for province in load_thailand_boundaries()["provinces"]:
        if any(
            _point_in_ring(longitude, latitude, ring)
            for ring in province["rings"]
        ):
            return province
    return None


def sample_point_in_province(
    province_name: str,
    rng: Any,
) -> Tuple[float, float]:
    """Return a deterministic RNG-driven point inside the assigned province."""
    province = province_boundary(province_name)
    if not province:
        raise KeyError(f"Unknown Thailand province: {province_name}")

    primary_ring = max(
        province["rings"],
        key=lambda ring: abs(
            sum(
                ring[index][0] * ring[index + 1][1]
                - ring[index + 1][0] * ring[index][1]
                for index in range(len(ring) - 1)
            )
        ),
    )
    min_lng, min_lat, max_lng, max_lat = province["bbox"]
    center_lng, center_lat = province["centroid"]
    lng_sd = max((max_lng - min_lng) / 3.2, 0.015)
    lat_sd = max((max_lat - min_lat) / 3.2, 0.015)

    for _ in range(50):
        longitude = float(rng.normal(center_lng, lng_sd))
        latitude = float(rng.normal(center_lat, lat_sd))
        if _point_in_ring(longitude, latitude, primary_ring):
            return latitude, longitude

    for _ in range(100):
        longitude = float(rng.uniform(min_lng, max_lng))
        latitude = float(rng.uniform(min_lat, max_lat))
        if _point_in_ring(longitude, latitude, primary_ring):
            return latitude, longitude

    return float(center_lat), float(center_lng)
