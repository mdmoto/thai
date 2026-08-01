# Upgrade Phase 0.5 report

Date: 2026-07-30  
Scope: independent compute environments and immutable artifact foundations  
Production deployment: not performed

## Outcome

Phase 0.5 code and configuration gates are implemented. The existing public
API, native simulation runner, Choice-Learn validation job, and PopulationSim
job now have independent Dockerfiles and fully resolved, hash-locked Python
dependency files.

The API and native runner remain on `numpy==2.0.2`. The PopulationSim job is
isolated on `numpy==1.26.4` with `populationsim==0.10.0`. Choice-Learn and
TensorFlow appear only in the Choice job lock and are not installed in the API
image.

## Compute image boundaries

| Image | Dockerfile | Dependency lock | Status |
| --- | --- | --- | --- |
| Public API | `Dockerfile.api` | `requirements-api.lock` | configured |
| Native runner | `Dockerfile.runner` | `requirements-runner-native.lock` | configured |
| Choice validation | `Dockerfile.choice` | `requirements-choice-job.lock` | configured, not deployed |
| Population synthesis | `Dockerfile.population` | `requirements-population-job.lock` | configured, not deployed |

`cloudbuild.yaml` now builds separate API and native-runner images and deploys
the existing simulation job from the runner image. Choice and Population
images are intentionally not added to the production deployment pipeline
until their validation phases pass.

All four lock files were resolved for Python 3.12 on Linux x86-64 and include
package hashes. `pip --dry-run --require-hashes` completed for all four locks.

## Artifact storage

The `model_artifacts` package now provides:

- a common immutable artifact-store contract;
- a content-addressed local store for development and tests;
- a private Google Cloud Storage implementation using `gs://` object URIs;
- create-only GCS generation preconditions to prevent silent overwrites;
- SHA-256, byte size, media type, schema version, object path and metadata on
  every artifact descriptor;
- path traversal rejection and atomic local writes;
- fail-closed production configuration when the bucket is absent or local
  storage is selected.

The code never creates a public or signed URL. It also does not write artifact
payloads to PostgreSQL. Database references and retention policy remain part
of Phase 4.

## Retry identity and resource budgets

`FrozenInputManifest` creates a deterministic manifest ID from component,
backend version, configuration version, seed and canonical input payload.
Retries using the same frozen inputs therefore reuse the same identity and
content bytes.

Initial hard ceilings are recorded for:

- native simulation;
- choice fitting;
- population synthesis;
- representative-consumer research;
- social simulation.

These are safety ceilings, not promises to consume the entire allowance.
Job-level enforcement and cost metering will be connected when each optional
backend becomes executable.

## Verification

- Backend tests: **96/96 passed**.
- Phase 0 frozen reports: exact canonical JSON comparison passed.
- Frontend production build: passed, 18 static pages generated.
- Four dependency locks: hash-verified installation dry-run passed.
- YAML and patch whitespace checks: passed.

The repository includes `scripts/audit_compute_images.sh` to build each image
and record image size plus an SPDX SBOM/license inventory. Docker is not
installed on the current workstation, so this image-build audit has not been
run locally. It must run in a build-only environment before either optional
job image is deployed. The existing deployment pipeline was not invoked
because it would change production.

## Phase gate

Phase 1 may begin as a validation experiment. Choice-Learn must remain behind
a feature flag and may only replace the native estimator if it passes the
documented holdout, direction, stability and runtime comparisons.

PopulationSim remains isolated for the subsequent Phase 2 proof of concept;
it must not be imported into the API or native-runner environment.
