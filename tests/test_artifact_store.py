import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_artifacts.base import ArtifactWriteRequest
from model_artifacts.budgets import budget_for_component
from model_artifacts.factory import artifact_store_from_environment
from model_artifacts.gcs import GCSArtifactStore
from model_artifacts.local import LocalArtifactStore
from model_artifacts.manifest import FrozenInputManifest


def _request(payload: bytes = b"population") -> ArtifactWriteRequest:
    return ArtifactWriteRequest(
        component_run_id="component_run_123",
        artifact_type="synthetic_population",
        payload=payload,
        media_type="application/vnd.apache.parquet",
        schema_version="population-v1",
        suffix=".parquet",
        metadata={"backend": "population_sim"},
    )


class LocalArtifactStoreTests(unittest.TestCase):
    def test_writes_content_addressed_artifact_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalArtifactStore(directory)
            descriptor = store.put(_request())

            path = Path(descriptor.uri.removeprefix("file://"))
            self.assertEqual(path.read_bytes(), b"population")
            self.assertEqual(descriptor.size_bytes, len(b"population"))
            self.assertIn(descriptor.sha256, descriptor.object_path)
            metadata = json.loads(
                path.with_name(
                    f"{path.name}.metadata.json"
                ).read_text("utf-8")
            )
            self.assertEqual(metadata["sha256"], descriptor.sha256)
            self.assertEqual(
                metadata["schema_version"],
                "population-v1",
            )

    def test_identical_retry_reuses_same_immutable_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalArtifactStore(directory)
            first = store.put(_request())
            second = store.put(_request())

            self.assertEqual(first.uri, second.uri)
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first.created_at, second.created_at)

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalArtifactStore(directory)
            unsafe = ArtifactWriteRequest(
                component_run_id="../escape",
                artifact_type="population",
                payload=b"x",
                media_type="application/octet-stream",
                schema_version="v1",
            )
            with self.assertRaises(ValueError):
                store.put(unsafe)


class _FakeBlob:
    def __init__(self, name: str) -> None:
        self.name = name
        self.metadata = {}
        self.payload = None
        self.upload_kwargs = {}

    def upload_from_string(self, payload, **kwargs) -> None:
        self.payload = payload
        self.upload_kwargs = kwargs

    def reload(self) -> None:
        return None


class _FakeBucket:
    def __init__(self) -> None:
        self.blobs = {}

    def blob(self, name: str) -> _FakeBlob:
        return self.blobs.setdefault(name, _FakeBlob(name))


class _FakeClient:
    def __init__(self) -> None:
        self.buckets = {}

    def bucket(self, name: str) -> _FakeBucket:
        return self.buckets.setdefault(name, _FakeBucket())


class GCSArtifactStoreTests(unittest.TestCase):
    def test_uses_private_gs_uri_and_create_only_precondition(self) -> None:
        client = _FakeClient()
        store = GCSArtifactStore(
            "private-model-bucket",
            "artifacts",
            client=client,
        )
        descriptor = store.put(_request())
        blob = client.bucket("private-model-bucket").blobs[
            descriptor.object_path
        ]

        self.assertTrue(descriptor.uri.startswith("gs://"))
        self.assertFalse(descriptor.uri.startswith("https://"))
        self.assertEqual(
            blob.upload_kwargs["if_generation_match"],
            0,
        )
        self.assertEqual(blob.metadata["sha256"], descriptor.sha256)


class ArtifactConfigurationTests(unittest.TestCase):
    def test_production_missing_bucket_fails_closed(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "MODEL_ARTIFACT_STORE": "gcs",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                artifact_store_from_environment()

    def test_production_rejects_local_store(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "MODEL_ARTIFACT_STORE": "local",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                artifact_store_from_environment()


class InputManifestTests(unittest.TestCase):
    def test_same_frozen_inputs_have_same_manifest_on_retry(self) -> None:
        arguments = {
            "component": "population_synthesis",
            "backend": "population_sim",
            "backend_version": "0.10.0",
            "config_version": "population-config-v1",
            "seed": 42,
            "payload": {"study_id": "study_1", "population": 300_000},
        }
        first = FrozenInputManifest.freeze(**arguments)
        second = FrozenInputManifest.freeze(**arguments)

        self.assertEqual(first.manifest_id, second.manifest_id)
        self.assertEqual(first.payload_sha256, second.payload_sha256)
        self.assertEqual(first.to_bytes(), second.to_bytes())

    def test_changed_input_changes_manifest(self) -> None:
        first = FrozenInputManifest.freeze(
            component="choice_fit",
            backend="native",
            backend_version="v1",
            config_version="choice-v1",
            seed=42,
            payload={"rows": 500},
        )
        second = FrozenInputManifest.freeze(
            component="choice_fit",
            backend="native",
            backend_version="v1",
            config_version="choice-v1",
            seed=42,
            payload={"rows": 501},
        )
        self.assertNotEqual(first.manifest_id, second.manifest_id)

    def test_every_component_has_a_hard_budget(self) -> None:
        for component in (
            "native_simulation",
            "choice_fit",
            "population_synthesis",
            "representative_research",
            "social_simulation",
        ):
            budget = budget_for_component(component)
            self.assertGreater(budget.maximum_seconds, 0)
            self.assertGreater(budget.maximum_memory_mib, 0)
            self.assertGreaterEqual(budget.maximum_cost_minor, 0)


class ComputeImageIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def _text(self, name: str) -> str:
        return (self.root / name).read_text("utf-8").lower()

    def test_api_image_excludes_optional_heavy_frameworks(self) -> None:
        requirements = self._text("apps/api/requirements-api.txt")
        for forbidden in (
            "tensorflow",
            "choice-learn",
            "populationsim",
            "tinytroupe",
            "camel-oasis",
        ):
            self.assertNotIn(forbidden, requirements)
        self.assertIn("numpy==2.0.2", requirements)

    def test_population_job_keeps_numpy_one_isolated(self) -> None:
        requirements = self._text(
            "apps/api/requirements-population-job.txt"
        )
        self.assertIn("numpy==1.26.4", requirements)
        self.assertIn("populationsim==0.10.0", requirements)
        self.assertNotIn("-r requirements-api.txt", requirements)
        for unrelated in (
            "fastapi",
            "google-cloud-storage",
            "sqlalchemy",
            "psycopg",
        ):
            self.assertNotIn(unrelated, requirements)

    def test_choice_job_dependencies_are_not_imported_by_api(self) -> None:
        requirements = self._text(
            "apps/api/requirements-choice-job.txt"
        )
        self.assertIn("choice-learn==1.3.2", requirements)
        self.assertIn("tensorflow==2.19.1", requirements)
        for unrelated in (
            "crawl4ai",
            "google-genai",
            "fastapi",
            "psycopg",
        ):
            self.assertNotIn(unrelated, requirements)
        api_dockerfile = self._text("dockerfile.api")
        self.assertNotIn("requirements-choice-job", api_dockerfile)
        self.assertIn("--require-hashes", api_dockerfile)

    def test_every_image_uses_an_independent_lock_file(self) -> None:
        expected = {
            "dockerfile.api": "requirements-api.lock",
            "dockerfile.runner": "requirements-runner-native.lock",
            "dockerfile.choice": "requirements-choice-job.lock",
            "dockerfile.population": "requirements-population-job.lock",
            "dockerfile.tinytroupe": "requirements-tinytroupe-job.lock",
            "dockerfile.oasis": "requirements-oasis-job.lock",
        }
        for dockerfile, lock_file in expected.items():
            content = self._text(dockerfile)
            self.assertIn(lock_file, content)
            self.assertIn("--require-hashes", content)

    def test_oasis_isolated_image_pins_compatible_research_runtime(self) -> None:
        requirements = self._text("apps/api/requirements-oasis-job.txt")
        dockerfile = self._text("dockerfile.oasis")
        api_requirements = self._text("apps/api/requirements-api.txt")
        validation = self._text("scripts/validate_oasis_backend.py")

        self.assertIn("camel-ai==0.2.78", requirements)
        self.assertIn("mcp==1.9.4", requirements)
        self.assertIn("from python:3.11", dockerfile)
        self.assertIn("camel-oasis @ https://github.com/camel-ai/oasis/archive/", dockerfile)
        self.assertNotIn("camel-oasis", api_requirements)
        self.assertIn("production_enabled\": false", validation)
        self.assertIn("manual_action_technical_validation", validation)
        self.assertIn("technical validation must not call an llm", validation)

    def test_image_audit_records_size_sbom_and_licenses(self) -> None:
        script = self._text("scripts/audit_compute_images.sh")
        self.assertIn("size_bytes", script)
        self.assertIn("spdx-json", script)
        self.assertIn("syft", script)

    def test_cloud_build_uses_distinct_api_and_runner_images(self) -> None:
        cloud_build = self._text("cloudbuild.yaml")
        self.assertIn("dockerfile.api", cloud_build)
        self.assertIn("dockerfile.runner", cloud_build)
        self.assertIn("market-twin-native-runner", cloud_build)


if __name__ == "__main__":
    unittest.main()
