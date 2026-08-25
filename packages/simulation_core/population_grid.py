"""Population estimates for GeoJSON catchments without runtime GIS dependencies."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np


DATASET_STEMS = {
    "TH": "worldpop_tha_2025_500m_v1",
    "MY": "worldpop_mys_2025_500m_v1",
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


@lru_cache(maxsize=4)
def _load_grid(country_code: str = "TH") -> Optional[Dict[str, Any]]:
    normalized_country = str(country_code or "TH").upper()
    stem = DATASET_STEMS.get(normalized_country)
    if stem is None:
        return None
    directory = _catalog_root() / "geo"
    grid_path = directory / f"{stem}.npz"
    metadata_path = directory / f"{stem}.json"
    if not grid_path.exists() or not metadata_path.exists():
        return None
    with np.load(grid_path, allow_pickle=False) as archive:
        grid = {
            "population": archive["population"].astype(np.float32, copy=False),
            "west": float(archive["west"]),
            "north": float(archive["north"]),
            "pixel_width_degrees": float(archive["pixel_width_degrees"]),
            "pixel_height_degrees": float(archive["pixel_height_degrees"]),
        }
    grid["metadata"] = json.loads(metadata_path.read_text(encoding="utf-8"))
    return grid


def _geometry(geojson: Mapping[str, Any]) -> Mapping[str, Any]:
    if geojson.get("type") == "Feature":
        value = geojson.get("geometry")
        return value if isinstance(value, Mapping) else {}
    return geojson


def _polygons(geojson: Mapping[str, Any]) -> Iterable[Sequence[Any]]:
    geometry = _geometry(geojson)
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return []
    if geometry.get("type") == "Polygon":
        return [coordinates]
    if geometry.get("type") == "MultiPolygon":
        return coordinates
    return []


def _ring_mask(
    longitudes: np.ndarray,
    latitudes: np.ndarray,
    ring: Sequence[Any],
) -> np.ndarray:
    points = [
        (float(point[0]), float(point[1]))
        for point in ring
        if isinstance(point, Sequence) and len(point) >= 2
    ]
    if len(points) < 3:
        return np.zeros(longitudes.shape, dtype=bool)
    inside = np.zeros(
        np.broadcast_shapes(longitudes.shape, latitudes.shape),
        dtype=bool,
    )
    previous_x, previous_y = points[-1]
    for current_x, current_y in points:
        crosses = (current_y > latitudes) != (previous_y > latitudes)
        denominator = previous_y - current_y
        if abs(denominator) < 1e-15:
            denominator = 1e-15
        boundary_x = (
            (previous_x - current_x)
            * (latitudes - current_y)
            / denominator
            + current_x
        )
        inside ^= crosses & (longitudes < boundary_x)
        previous_x, previous_y = current_x, current_y
    return inside


def _polygon_bounds(polygons: Sequence[Sequence[Any]]) -> Optional[Tuple[float, float, float, float]]:
    points = []
    for polygon in polygons:
        for ring in polygon:
            for point in ring:
                if isinstance(point, Sequence) and len(point) >= 2:
                    points.append((float(point[0]), float(point[1])))
    if not points:
        return None
    longitudes, latitudes = zip(*points)
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def estimate_population_for_geojson(
    geojson: Mapping[str, Any],
    country_code: str = "TH",
) -> Optional[Dict[str, Any]]:
    """Estimate residential population whose runtime cell centers fall in a polygon."""

    loaded = _load_grid(country_code)
    polygons = list(_polygons(geojson))
    bounds = _polygon_bounds(polygons)
    if loaded is None or bounds is None:
        return None

    population = loaded["population"]
    west = loaded["west"]
    north = loaded["north"]
    pixel_width = loaded["pixel_width_degrees"]
    pixel_height = loaded["pixel_height_degrees"]
    min_lng, min_lat, max_lng, max_lat = bounds

    col_start = max(0, int(np.floor((min_lng - west) / pixel_width)))
    col_end = min(
        population.shape[1],
        int(np.ceil((max_lng - west) / pixel_width)),
    )
    row_start = max(0, int(np.floor((north - max_lat) / pixel_height)))
    row_end = min(
        population.shape[0],
        int(np.ceil((north - min_lat) / pixel_height)),
    )
    if row_end <= row_start or col_end <= col_start:
        return None

    row_indices = np.arange(row_start, row_end)
    col_indices = np.arange(col_start, col_end)
    latitudes = north - (row_indices[:, None] + 0.5) * pixel_height
    longitudes = west + (col_indices[None, :] + 0.5) * pixel_width
    selected = np.zeros(
        (row_end - row_start, col_end - col_start),
        dtype=bool,
    )
    for polygon in polygons:
        if not polygon:
            continue
        polygon_mask = _ring_mask(longitudes, latitudes, polygon[0])
        for hole in polygon[1:]:
            polygon_mask &= ~_ring_mask(longitudes, latitudes, hole)
        selected |= polygon_mask

    raw_estimate = float(
        population[row_start:row_end, col_start:col_end][selected].sum()
    )
    metadata = loaded["metadata"]
    adjustment = metadata.get("national_adjustment") or {}
    adjustment_factor = float(adjustment.get("factor") or 1.0)
    estimate = raw_estimate * adjustment_factor
    return {
        "estimated_resident_population": int(round(max(0.0, estimate))),
        "estimated_resident_population_unadjusted": int(
            round(max(0.0, raw_estimate))
        ),
        "population_status": "modeled_residential_population_grid",
        "population_dataset_id": metadata["dataset_id"],
        "population_source": "WorldPop 2025",
        "population_source_resolution": metadata["source_resolution"],
        "population_runtime_resolution": metadata["runtime_resolution"],
        "population_license": metadata["license"],
        "population_source_doi": metadata["source_doi"],
        "population_method": "500m_cell_center_in_network_isochrone",
        "population_adjustment": adjustment.get("method"),
        "population_adjustment_factor": adjustment_factor,
    }
