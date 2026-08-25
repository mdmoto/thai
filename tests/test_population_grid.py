import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from simulation_core.population_grid import (
    _load_grid,
    estimate_population_for_geojson,
)


class PopulationGridTests(unittest.TestCase):
    def test_estimates_population_inside_polygon_without_runtime_gis_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            geo = root / "geo"
            geo.mkdir()
            np.savez_compressed(
                geo / "worldpop_tha_2025_500m_v1.npz",
                population=np.asarray([[10, 20], [30, 40]], dtype=np.float32),
                west=np.float64(100.0),
                north=np.float64(14.0),
                pixel_width_degrees=np.float64(0.01),
                pixel_height_degrees=np.float64(0.01),
            )
            (geo / "worldpop_tha_2025_500m_v1.json").write_text(
                json.dumps(
                    {
                        "dataset_id": "worldpop_tha_2025_500m_v1",
                        "source_resolution": "3 arc-second (~100 m)",
                        "runtime_resolution": "15 arc-second (~500 m)",
                        "license": "CC-BY-4.0",
                        "source_doi": "10.5258/SOTON/WP00839",
                    }
                ),
                encoding="utf-8",
            )
            polygon = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [100.0, 13.98],
                        [100.02, 13.98],
                        [100.02, 14.0],
                        [100.0, 14.0],
                        [100.0, 13.98],
                    ]
                ],
            }
            with patch.dict(os.environ, {"DATA_CATALOG_ROOT": str(root)}):
                _load_grid.cache_clear()
                result = estimate_population_for_geojson(polygon)
            _load_grid.cache_clear()

        self.assertEqual(result["estimated_resident_population"], 100)
        self.assertEqual(
            result["population_status"],
            "modeled_residential_population_grid",
        )
        self.assertEqual(result["population_license"], "CC-BY-4.0")

    def test_selects_the_malaysia_grid_and_applies_disclosed_benchmark_scaling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            geo = root / "geo"
            geo.mkdir()
            np.savez_compressed(
                geo / "worldpop_mys_2025_500m_v1.npz",
                population=np.asarray([[20, 40]], dtype=np.float32),
                west=np.float64(101.0),
                north=np.float64(3.1),
                pixel_width_degrees=np.float64(0.01),
                pixel_height_degrees=np.float64(0.01),
            )
            (geo / "worldpop_mys_2025_500m_v1.json").write_text(
                json.dumps(
                    {
                        "dataset_id": "worldpop_mys_2025_500m_v1",
                        "source_resolution": "3 arc-second (~100 m)",
                        "runtime_resolution": "15 arc-second (~500 m)",
                        "license": "CC-BY-4.0",
                        "source_doi": "10.5258/SOTON/WP00839",
                        "national_adjustment": {
                            "factor": 0.9,
                            "method": "uniform_national_scaling_to_official_benchmark",
                        },
                    }
                ),
                encoding="utf-8",
            )
            polygon = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [101.0, 3.08],
                        [101.02, 3.08],
                        [101.02, 3.1],
                        [101.0, 3.1],
                        [101.0, 3.08],
                    ]
                ],
            }
            with patch.dict(os.environ, {"DATA_CATALOG_ROOT": str(root)}):
                _load_grid.cache_clear()
                result = estimate_population_for_geojson(polygon, "MY")
            _load_grid.cache_clear()

        self.assertEqual(
            result["population_dataset_id"],
            "worldpop_mys_2025_500m_v1",
        )
        self.assertEqual(result["estimated_resident_population_unadjusted"], 60)
        self.assertEqual(result["estimated_resident_population"], 54)
        self.assertEqual(
            result["population_adjustment"],
            "uniform_national_scaling_to_official_benchmark",
        )


if __name__ == "__main__":
    unittest.main()
