#!/usr/bin/env python3
"""Build the compact Thailand population grid used by venue studies.

The source raster is WorldPop's 2025 constrained 100 m population grid. Runtime
code deliberately does not depend on GDAL/rasterio; this build step aggregates
the source into 500 m cells and stores the result as a compressed NumPy array.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio


SOURCE_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/"
    "R2025A/2025/THA/v1/100m/constrained/"
    "tha_pop_2025_CN_100m_R2025A_v1.tif"
)
SOURCE_ITEM = "tha_pop_2025_CN_100m_R2025A_v1"
SOURCE_DOI = "10.5258/SOTON/WP00839"
AGGREGATION_FACTOR = 5


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 100_000_000:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    temporary.replace(destination)


def build(source: Path, output: Path, metadata_output: Path) -> None:
    with rasterio.open(source) as dataset:
        if dataset.crs is None or dataset.crs.to_epsg() != 4326:
            raise ValueError(f"Expected EPSG:4326, received {dataset.crs}")
        source_data = dataset.read(1, masked=True).filled(0).astype(np.float32)
        source_data[~np.isfinite(source_data)] = 0
        source_data[source_data < 0] = 0
        transform = dataset.transform
        source_height, source_width = source_data.shape

    factor = AGGREGATION_FACTOR
    target_height = math.ceil(source_height / factor)
    target_width = math.ceil(source_width / factor)
    padded = np.zeros((target_height * factor, target_width * factor), dtype=np.float32)
    padded[:source_height, :source_width] = source_data
    aggregated = padded.reshape(
        target_height,
        factor,
        target_width,
        factor,
    ).sum(axis=(1, 3), dtype=np.float64).astype(np.float32)

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        population=aggregated,
        west=np.float64(transform.c),
        north=np.float64(transform.f),
        pixel_width_degrees=np.float64(transform.a * factor),
        pixel_height_degrees=np.float64(abs(transform.e) * factor),
    )

    metadata = {
        "dataset_id": "worldpop_tha_2025_500m_v1",
        "title": "Thailand 2025 residential population grid, 500 m runtime aggregate",
        "source_item_id": SOURCE_ITEM,
        "source_url": SOURCE_URL,
        "source_catalog_url": (
            "https://api.stac.worldpop.org/collections/THA/items/"
            f"{SOURCE_ITEM}"
        ),
        "source_doi": SOURCE_DOI,
        "publisher": "WorldPop, University of Southampton",
        "license": "CC-BY-4.0",
        "source_resolution": "3 arc-second (~100 m)",
        "runtime_resolution": "15 arc-second (~500 m)",
        "aggregation": "sum of 5 x 5 source pixels; cell-center polygon inclusion at runtime",
        "population_definition": "estimated residential population, people per grid cell",
        "model_method": "Random Forest-based dasymetric redistribution, constrained grid",
        "source_sha256": _sha256(source),
        "runtime_sha256": _sha256(output),
        "source_shape": [source_height, source_width],
        "runtime_shape": list(aggregated.shape),
        "worldpop_population_total": round(float(aggregated.sum(dtype=np.float64)), 2),
        "national_benchmark": {
            "publisher": "Thailand National Statistical Office",
            "dataset": "Early results, 2025 Population and Housing Census",
            "resident_population": 70_300_000,
            "households": 26_300_000,
            "url": "https://www.nso.go.th/nsoweb/main/summano/aE?set_lang=en",
            "usage": "national reasonableness benchmark only; not used to invent a finer spatial distribution",
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "limitations": [
            "This is a modeled residential population surface, not daytime population.",
            "It is not mobile-device footfall, a mall turnstile count, or payment activity.",
            "The production grid is aggregated to approximately 500 m and uses cell centers for catchment inclusion.",
        ],
    }
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/tmp/tha_pop_2025_CN_100m_R2025A_v1.tif"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data_catalog/geo/worldpop_tha_2025_500m_v1.npz"),
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=Path("data_catalog/geo/worldpop_tha_2025_500m_v1.json"),
    )
    args = parser.parse_args()
    _download(SOURCE_URL, args.source)
    build(args.source, args.output, args.metadata_output)


if __name__ == "__main__":
    main()
