"""Build compact Thailand boundary assets from geoBoundaries gbOpen data.

The generated catalog is used to place synthetic display samples inside their
assigned province. The TypeScript asset renders the same real ADM0/ADM1
geometry in reports without a runtime map-service dependency.
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
ADM0_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
    "releaseData/gbOpen/THA/ADM0/"
    "geoBoundaries-THA-ADM0_simplified.geojson"
)
ADM1_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
    "releaseData/gbOpen/THA/ADM1/"
    "geoBoundaries-THA-ADM1_simplified.geojson"
)
BOUNDS = (97.2, 5.5, 105.8, 20.6)
VIEWBOX = (360.0, 560.0)
PADDING = 12.0


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CMAI-boundary-refresh/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def distance_to_segment(point, start, end) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    ratio = max(
        0.0,
        min(1.0, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)),
    )
    return math.hypot(px - (sx + ratio * dx), py - (sy + ratio * dy))


def simplify_open(points: Sequence[Sequence[float]], tolerance: float):
    if len(points) <= 2:
        return [list(point) for point in points]
    start, end = points[0], points[-1]
    max_distance = -1.0
    split_index = 0
    for index, point in enumerate(points[1:-1], start=1):
        distance = distance_to_segment(point, start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index
    if max_distance <= tolerance:
        return [list(start), list(end)]
    left = simplify_open(points[: split_index + 1], tolerance)
    right = simplify_open(points[split_index:], tolerance)
    return left[:-1] + right


def simplify_ring(ring: Sequence[Sequence[float]], tolerance: float):
    points = [list(point) for point in ring]
    if points and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 4:
        return []
    anchor = min(range(len(points)), key=lambda i: (points[i][0], points[i][1]))
    rotated = points[anchor:] + points[:anchor] + [points[anchor]]
    simplified = simplify_open(rotated, tolerance)
    if len(simplified) < 4:
        return []
    simplified[-1] = simplified[0]
    return [
        [round(float(longitude), 4), round(float(latitude), 4)]
        for longitude, latitude in simplified
    ]


def signed_area(ring: Sequence[Sequence[float]]) -> float:
    return 0.5 * sum(
        ring[index][0] * ring[index + 1][1]
        - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    )


def centroid(ring: Sequence[Sequence[float]]):
    area_factor = sum(
        ring[index][0] * ring[index + 1][1]
        - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    )
    if abs(area_factor) < 1e-12:
        return [
            round(sum(point[0] for point in ring[:-1]) / (len(ring) - 1), 4),
            round(sum(point[1] for point in ring[:-1]) / (len(ring) - 1), 4),
        ]
    cx = sum(
        (ring[index][0] + ring[index + 1][0])
        * (
            ring[index][0] * ring[index + 1][1]
            - ring[index + 1][0] * ring[index][1]
        )
        for index in range(len(ring) - 1)
    )
    cy = sum(
        (ring[index][1] + ring[index + 1][1])
        * (
            ring[index][0] * ring[index + 1][1]
            - ring[index + 1][0] * ring[index][1]
        )
        for index in range(len(ring) - 1)
    )
    return [
        round(cx / (3.0 * area_factor), 4),
        round(cy / (3.0 * area_factor), 4),
    ]


def exterior_rings(geometry: dict) -> Iterable[Sequence[Sequence[float]]]:
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"][0]
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield polygon[0]


def project(longitude: float, latitude: float):
    min_lng, min_lat, max_lng, max_lat = BOUNDS
    width, height = VIEWBOX
    usable_width = width - PADDING * 2
    usable_height = height - PADDING * 2
    x = PADDING + (longitude - min_lng) / (max_lng - min_lng) * usable_width
    y = PADDING + (max_lat - latitude) / (max_lat - min_lat) * usable_height
    return round(x, 2), round(y, 2)


def path_for_rings(rings: Sequence[Sequence[Sequence[float]]]) -> str:
    commands = []
    for ring in rings:
        projected = [project(point[0], point[1]) for point in ring]
        if len(projected) < 4:
            continue
        commands.append(
            "M"
            + "L".join(f"{x:g},{y:g}" for x, y in projected)
            + "Z"
        )
    return "".join(commands)


def main() -> None:
    adm0 = fetch_json(ADM0_URL)
    adm1 = fetch_json(ADM1_URL)

    country_rings = []
    for raw_ring in exterior_rings(adm0["features"][0]["geometry"]):
        ring = simplify_ring(raw_ring, 0.018)
        if ring and abs(signed_area(ring)) >= 0.002:
            country_rings.append(ring)

    provinces = []
    province_paths = []
    for feature in adm1["features"]:
        rings = []
        for raw_ring in exterior_rings(feature["geometry"]):
            ring = simplify_ring(raw_ring, 0.012)
            if ring and abs(signed_area(ring)) >= 0.0008:
                rings.append(ring)
        if not rings:
            continue
        primary_ring = max(rings, key=lambda item: abs(signed_area(item)))
        longitude_values = [point[0] for point in primary_ring]
        latitude_values = [point[1] for point in primary_ring]
        name = feature["properties"]["shapeName"].removesuffix(
            " Province"
        )
        provinces.append(
            {
                "name": name,
                "iso": feature["properties"].get("shapeISO"),
                "centroid": centroid(primary_ring),
                "bbox": [
                    round(min(longitude_values), 4),
                    round(min(latitude_values), 4),
                    round(max(longitude_values), 4),
                    round(max(latitude_values), 4),
                ],
                "rings": rings,
            }
        )
        province_paths.append(path_for_rings(rings))

    catalog = {
        "version": "TH-GEOBOUNDARIES-ADM1-2026.07.1",
        "boundary_year": "2017",
        "source": "geoBoundaries gbOpen THA ADM0/ADM1",
        "source_url": "https://www.geoboundaries.org/api/current/gbOpen/THA/ADM1/",
        "source_data": "OpenStreetMap, Wambacher",
        "license": "Open Data Commons Open Database License 1.0",
        "bounds": list(BOUNDS),
        "country_rings": country_rings,
        "provinces": sorted(provinces, key=lambda item: item["name"]),
    }
    catalog_path = (
        ROOT / "data_catalog" / "geo" / "thailand_adm1_boundaries_v1.json"
    )
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    country_path = path_for_rings(country_rings)
    province_path = "".join(province_paths)
    typescript = (
        "// Generated by scripts/build_thailand_boundaries.py from "
        "geoBoundaries gbOpen THA ADM0/ADM1.\n"
        f"export const THAILAND_BOUNDARY_VERSION = {json.dumps(catalog['version'])};\n"
        f"export const THAILAND_BOUNDARY_SOURCE = {json.dumps(catalog['source'])};\n"
        f"export const THAILAND_MAP_BOUNDS = {json.dumps(list(BOUNDS))} as const;\n"
        f"export const THAILAND_COUNTRY_PATH = {json.dumps(country_path)};\n"
        f"export const THAILAND_PROVINCE_PATH = {json.dumps(province_path)};\n"
    )
    frontend_path = ROOT / "apps" / "web" / "lib" / "thailand-boundary.ts"
    frontend_path.write_text(typescript, encoding="utf-8")

    print(
        f"Wrote {len(provinces)} provinces, "
        f"{len(country_rings)} country rings."
    )


if __name__ == "__main__":
    main()
