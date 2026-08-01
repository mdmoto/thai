"""Adapter for the existing Thailand synthetic-population generator."""

from __future__ import annotations

import os

import pandas as pd

from world_model.backends.base import (
    PopulationSynthesisBackend,
    PopulationSynthesisRequest,
    PopulationSynthesisResult,
)
from world_model.generator import PopulationGenerator, WORLD_MODEL_VERSION


class NativePopulationSynthesisBackend:
    backend_id = "native"
    backend_version = WORLD_MODEL_VERSION

    def generate(
        self,
        request: PopulationSynthesisRequest,
    ) -> PopulationSynthesisResult:
        generator = PopulationGenerator(
            seed=request.seed,
            calibration_profile=request.calibration_profile,
        )
        population = generator.generate(
            size=request.population_size,
            study_type=request.study_type,
            category=request.category,
        )
        represented_population = float(
            population.get(
                "sample_weight",
                pd.Series(1.0, index=population.index),
            ).sum()
        )
        return PopulationSynthesisResult(
            population=population,
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            status=str(population["calibration_status"].iloc[0]),
            diagnostics={
                "synthetic_population_rows": len(population),
                "represented_population_weight": represented_population,
                "control_totals_version": request.control_totals_version,
                "seed_sample_version": request.seed_sample_version,
                "geography_level": request.geography_level,
                "output_schema_version": request.output_schema_version,
                "seed": request.seed,
            },
            runtime_context=generator,
        )

    def stratified_sample(
        self,
        result: PopulationSynthesisResult,
        sample_size: int,
        seed: int,
    ) -> pd.DataFrame:
        generator = result.runtime_context
        if not isinstance(generator, PopulationGenerator):
            raise RuntimeError(
                "Native population result is missing its sampling context"
            )
        return generator.stratified_sample(
            result.population,
            sample_size,
            seed=seed,
        )


def get_population_backend(
    backend_id: str | None = None,
) -> PopulationSynthesisBackend:
    selected = (
        backend_id
        or os.environ.get("POPULATION_BACKEND", "native")
    ).strip().lower()
    if selected in {"native", "native_generator"}:
        return NativePopulationSynthesisBackend()
    if selected in {"population_sim", "populationsim"}:
        from world_model.backends.population_sim import (
            PopulationSimSynthesisBackend,
        )

        return PopulationSimSynthesisBackend()
    raise ValueError(f"Unsupported population backend: {selected}")
