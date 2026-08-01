"""Phase 0 backend-contract and frozen-report regression tests."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd

from agents.backends.base import RepresentativeResearchRequest
from agents.backends.gemini import GeminiRepresentativeResearchBackend
from scripts.freeze_phase0_baselines import CASES, _canonicalize, _run_case
from simulation_core.choice_backends.base import ChoiceFitRequest
from simulation_core.choice_backends.native import (
    NativeChoiceModelBackend,
    get_choice_model_backend,
)
from simulation_core.social_backends.base import SocialSimulationRequest
from simulation_core.social_backends.prior import (
    PriorSocialSimulationBackend,
    get_social_simulation_backend,
)
from simulation_core.social_backends.oasis import (
    OASIS_STATUS,
    OasisSocialSimulationBackend,
)
from world_model.backends.base import PopulationSynthesisRequest
from world_model.backends.native import (
    NativePopulationSynthesisBackend,
    get_population_backend,
)
from simulation_core.calibration import load_calibration_profile


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_ROOT = REPO_ROOT / "docs" / "baselines" / "phase0"


class NativeBackendContractTests(unittest.TestCase):
    def test_unknown_backends_fail_closed(self):
        with self.assertRaises(ValueError):
            get_population_backend("unknown")
        with self.assertRaises(ValueError):
            get_choice_model_backend("unknown")
        with self.assertRaises(ValueError):
            get_social_simulation_backend("unknown")

    def test_native_population_backend_is_reproducible_and_weighted(self):
        backend = NativePopulationSynthesisBackend()
        request = PopulationSynthesisRequest(
            population_size=250,
            study_type="PRODUCT_VALIDATION",
            category="GENERIC_CONSUMER_PRODUCT",
            seed=19,
            calibration_profile=load_calibration_profile(),
        )
        first = backend.generate(request)
        second = backend.generate(request)
        pd.testing.assert_frame_equal(first.population, second.population)
        self.assertEqual(first.backend_id, "native")
        self.assertEqual(
            first.diagnostics["synthetic_population_rows"],
            250,
        )
        self.assertEqual(
            first.diagnostics["represented_population_weight"],
            250.0,
        )
        sampled = backend.stratified_sample(first, 40, seed=19)
        self.assertEqual(len(sampled), 40)
        self.assertAlmostEqual(
            sampled["expansion_weight"].sum(),
            250.0,
        )

    def test_native_choice_backend_preserves_expected_directions(self):
        rng = np.random.default_rng(71)
        rows = []
        for choice_set_id in range(500):
            features = np.array(
                [rng.uniform(0.6, 1.4), rng.uniform(0.2, 1.0)]
            )
            utilities = np.array(
                [0.0, float(features @ np.array([-1.3, 0.9]))]
            )
            probabilities = np.exp(utilities - utilities.max())
            probabilities /= probabilities.sum()
            chosen = int(rng.choice([0, 1], p=probabilities))
            rows.extend(
                [
                    {
                        "choice_set_id": choice_set_id,
                        "price_log_ratio": 0.0,
                        "quality_fit": 0.0,
                        "chosen": int(chosen == 0),
                    },
                    {
                        "choice_set_id": choice_set_id,
                        "price_log_ratio": features[0],
                        "quality_fit": features[1],
                        "chosen": int(chosen == 1),
                    },
                ]
            )
        backend = NativeChoiceModelBackend()
        result = backend.fit(
            ChoiceFitRequest(
                frame=pd.DataFrame(rows),
                feature_columns=["price_log_ratio", "quality_fit"],
                study_type="PRODUCT_VALIDATION",
                seed=71,
            )
        )
        self.assertTrue(result.fit.converged)
        self.assertLess(result.fit.coefficients["price_log_ratio"], 0)
        self.assertGreater(result.fit.coefficients["quality_fit"], 0)
        self.assertEqual(result.backend_id, "native")
        self.assertIsNotNone(result.artifact_payload)
        self.assertEqual(
            result.artifact_metadata["schema_version"],
            "choice-fit-v1",
        )
        prediction = backend.predict(
            result,
            pd.DataFrame(rows),
            ["price_log_ratio", "quality_fit"],
        )
        self.assertLess(
            prediction.diagnostics[
                "choice_set_probability_sum_max_error"
            ],
            1e-12,
        )

    def test_prior_social_backend_delegates_without_relabeling(self):
        expected = [
            {
                "scenario_id": "baseline",
                "status": "uncalibrated_social_propagation_prior",
            }
        ]
        result = PriorSocialSimulationBackend().simulate(
            SocialSimulationRequest(
                seed=42,
                plan_code="PREVIEW",
                frozen_inputs={},
                native_runner=lambda: expected,
            )
        )
        self.assertEqual(list(result.events), expected)
        self.assertEqual(
            result.status,
            "uncalibrated_social_propagation_prior",
        )

    def test_oasis_requires_explicit_enablement_and_a_job_runner(self):
        with unittest.mock.patch.dict(
            os.environ,
            {
                "SOCIAL_SIMULATION_BACKEND": "oasis",
                "ENABLE_OASIS": "false",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                get_social_simulation_backend()

        request = SocialSimulationRequest(
            seed=42,
            plan_code="PROFESSIONAL",
            frozen_inputs={
                "oasis_experiment": {
                    "agent_count": 8,
                    "activation_probability": 0.2,
                    "time_steps": 3,
                    "maximum_input_tokens": 20_000,
                    "maximum_output_tokens": 4_000,
                    "maximum_cost_minor": 5_000,
                    "maximum_wall_time_seconds": 300,
                }
            },
            native_runner=lambda: [],
        )
        with self.assertRaisesRegex(RuntimeError, "isolated social"):
            OasisSocialSimulationBackend().simulate(request)

    def test_oasis_only_emits_simulated_social_metrics(self):
        request = SocialSimulationRequest(
            seed=42,
            plan_code="PROFESSIONAL",
            frozen_inputs={
                "oasis_experiment": {
                    "agent_count": 8,
                    "activation_probability": 0.2,
                    "time_steps": 3,
                    "maximum_input_tokens": 20_000,
                    "maximum_output_tokens": 4_000,
                    "maximum_cost_minor": 5_000,
                    "maximum_wall_time_seconds": 300,
                }
            },
            native_runner=lambda: [],
        )
        backend = OasisSocialSimulationBackend(
            runner=lambda _limits, _request: [
                {
                    "time_step": 1,
                    "metric": "simulated_social_diffusion",
                    "value": 0.38,
                    "scenario_id": "creator_seed",
                }
            ]
        )
        result = backend.simulate(request)
        self.assertEqual(result.status, OASIS_STATUS)
        self.assertEqual(result.events[0]["status"], OASIS_STATUS)
        self.assertNotIn("purchase_rate", result.events[0])


class RepresentativeBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_adapter_preserves_gateway_payload(self):
        payload = {
            "status": "unavailable",
            "responses": [],
            "sample_size_completed": 0,
        }
        gateway = AsyncMock()
        gateway.generate_research_signals.return_value = payload
        backend = GeminiRepresentativeResearchBackend(gateway=gateway)
        result = await backend.research(
            RepresentativeResearchRequest(
                product_info={},
                business_questions=[],
                representatives=[],
                plan_code="PREVIEW",
                seed=42,
            )
        )
        self.assertEqual(result.payload, payload)
        self.assertEqual(result.status, "unavailable")
        gateway.generate_research_signals.assert_awaited_once()


class FrozenPhase0ReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_frozen_reports_are_unchanged(self):
        environment = {
            "MARKET_RESEARCH_ENABLED": "false",
            "GEO_RESEARCH_ENABLED": "false",
            "GEMINI_API_KEY_PRIMARY": "",
            "GEMINI_API_KEY_SECONDARY": "",
            "GEMINI_API_KEY": "",
            "GEMINI_VERTEX_FALLBACK": "false",
            "POPULATION_BACKEND": "native",
            "CHOICE_MODEL_BACKEND": "native",
            "REPRESENTATIVE_AGENT_BACKEND": "gemini",
            "SOCIAL_SIMULATION_BACKEND": "prior",
        }
        with unittest.mock.patch.dict(os.environ, environment):
            for case_id, case in CASES.items():
                with self.subTest(case_id=case_id):
                    expected = json.loads(
                        (
                            BASELINE_ROOT
                            / f"{case_id}.report.json"
                        ).read_text(encoding="utf-8")
                    )
                    actual = _canonicalize(await _run_case(case))
                    self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
