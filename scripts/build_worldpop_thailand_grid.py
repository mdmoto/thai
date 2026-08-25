#!/usr/bin/env python3
"""Build compact Thailand or Malaysia WorldPop grids used by venue studies.

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
try:
    import rasterio
except ImportError:  # pragma: no cover - exercised in lightweight build images
    rasterio = None
from PIL import Image


COUNTRY_SPECS = {
    "TH": {
        "iso3": "THA",
        "file_stem": "tha_pop_2025_CN_100m_R2025A_v1",
        "output_stem": "worldpop_tha_2025_500m_v1",
        "country_name": "Thailand",
        "national_benchmark": {
            "publisher": "Thailand National Statistical Office",
            "dataset": "Early results, 2025 Population and Housing Census",
            "resident_population": 70_300_000,
            "households": 26_300_000,
            "url": "https://www.nso.go.th/nsoweb/main/summano/aE?set_lang=en",
            "usage": "national reasonableness benchmark only; not used to invent a finer spatial distribution",
        },
    },
    "MY": {
        "iso3": "MYS",
        "file_stem": "mys_pop_2025_CN_100m_R2025A_v1",
        "output_stem": "worldpop_mys_2025_500m_v1",
        "country_name": "Malaysia",
        "national_benchmark": {
            "publisher": "Department of Statistics Malaysia (DOSM)",
            "dataset": "Population Table: States, 2026",
            "resident_population": 34_389_300,
            "url": "https://data.gov.my/data-catalogue/population_state",
            "usage": "national reasonableness benchmark only; not used to invent a finer spatial distribution",
        },
    },
}
SOURCE_DOI = "10.5258/SOTON/WP00839"
AGGREGATION_FACTOR = 5


def _source_url(spec: dict[str, object]) -> str:
    return (
        "https://data.worldpop.org/GIS/Population/Global_2015_2030/"
        f"R2025A/2025/{spec['iso3']}/v1/100m/constrained/"
        f"{spec['file_stem']}.tif"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 1_000_000:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    temporary.replace(destination)


def _aggregate_source_rows(
    read_rows,
    source_width: int,
    source_height: int,
    factor: int,
) -> np.ndarray:
    """Aggregate a large raster a few source rows at a time.

    Malaysia spans a much wider raster extent than Thailand. Streaming five
    source rows at once keeps this build step below the memory budget while
    preserving exact count sums within each runtime cell.
    """
    target_height = math.ceil(source_height / factor)
    target_width = math.ceil(source_width / factor)
    aggregated = np.zeros((target_height, target_width), dtype=np.float32)
    padded_width = target_width * factor
    for target_row, top in enumerate(range(0, source_height, factor)):
        bottom = min(source_height, top + factor)
        source_rows = np.asarray(read_rows(top, bottom), dtype=np.float32).copy()
        source_rows[~np.isfinite(source_rows)] = 0
        source_rows[source_rows < 0] = 0
        padded = np.zeros((factor, padded_width), dtype=np.float32)
        padded[: bottom - top, :source_width] = source_rows
        aggregated[target_row] = padded.reshape(
            factor,
            target_width,
            factor,
        ).sum(axis=(0, 2), dtype=np.float64).astype(np.float32)
    return aggregated


def build(
    source: Path,
    output: Path,
    metadata_output: Path,
    country_code: str,
) -> None:
    spec = COUNTRY_SPECS[country_code]
    source_url = _source_url(spec)
    if rasterio is not None:
        with rasterio.open(source) as dataset:
            if dataset.crs is None or dataset.crs.to_epsg() != 4326:
                raise ValueError(f"Expected EPSG:4326, received {dataset.crs}")
            transform_a = float(dataset.transform.a)
            transform_c = float(dataset.transform.c)
            transform_e = float(abs(dataset.transform.e))
            transform_f = float(dataset.transform.f)
            source_height, source_width = dataset.height, dataset.width
            aggregated = _aggregate_source_rows(
                lambda top, bottom: dataset.read(
                    1,
                    window=rasterio.windows.Window(
                        0,
                        top,
                        source_width,
                        bottom - top,
                    ),
                    masked=True,
                ).filled(0),
                source_width,
                source_height,
                AGGREGATION_FACTOR,
            )
    else:
        # WorldPop GeoTIFFs carry the geographic WGS84 transform in standard
        # GeoTIFF ModelPixelScale and ModelTiepoint tags.  Pillow keeps this
        # one-off build step dependency-free in the lightweight runtime image.
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(source) as dataset:
            pixel_scale = dataset.tag_v2.get(33550)
            tiepoint = dataset.tag_v2.get(33922)
            if not pixel_scale or not tiepoint or len(tiepoint) < 6:
                raise ValueError("WorldPop GeoTIFF lacks an expected geotransform")
            transform_a = float(pixel_scale[0])
            transform_c = float(tiepoint[3])
            transform_e = float(abs(pixel_scale[1]))
            transform_f = float(tiepoint[4])
            source_width, source_height = dataset.size
            aggregated = _aggregate_source_rows(
                lambda top, bottom: dataset.crop(
                    (0, top, source_width, bottom)
                ),
                source_width,
                source_height,
                AGGREGATION_FACTOR,
            )
    factor = AGGREGATION_FACTOR
    target_height, target_width = aggregated.shape

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        population=aggregated,
        west=np.float64(transform_c),
        north=np.float64(transform_f),
        pixel_width_degrees=np.float64(transform_a * factor),
        pixel_height_degrees=np.float64(transform_e * factor),
    )

    worldpop_total = float(aggregated.sum(dtype=np.float64))
    benchmark_population = float(spec["national_benchmark"]["resident_population"])
    national_adjustment_factor = benchmark_population / worldpop_total
    metadata = {
        "dataset_id": spec["output_stem"],
        "title": f"{spec['country_name']} 2025 residential population grid, 500 m runtime aggregate",
        "source_item_id": spec["file_stem"],
        "source_url": source_url,
        "source_catalog_url": (
            f"https://api.stac.worldpop.org/collections/{spec['iso3']}/items/"
            f"{spec['file_stem']}"
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
        "worldpop_population_total": round(worldpop_total, 2),
        "national_benchmark": spec["national_benchmark"],
        "national_adjustment": {
            "factor": national_adjustment_factor,
            "method": "uniform_national_scaling_to_official_benchmark",
            "calibrated_population_total": int(round(benchmark_population)),
            "reason": (
                "The WorldPop 2025 spatial surface is retained for local "
                "distribution, then uniformly scaled to the latest official "
                "national benchmark when one is configured."
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "limitations": [
            "This is a modeled residential population surface, not daytime population.",
            "A uniform national adjustment may align the grid total to a newer official benchmark, but it does not create district-level census counts.",
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
    parser.add_argument("--country", choices=sorted(COUNTRY_SPECS), default="TH")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    spec = COUNTRY_SPECS[args.country]
    source = args.source or Path(f"/tmp/{spec['file_stem']}.tif")
    output = args.output or Path(
        f"data_catalog/geo/{spec['output_stem']}.npz"
    )
    metadata_output = args.metadata_output or Path(
        f"data_catalog/geo/{spec['output_stem']}.json"
    )
    _download(_source_url(spec), source)
    build(source, output, metadata_output, args.country)


if __name__ == "__main__":
    main()
