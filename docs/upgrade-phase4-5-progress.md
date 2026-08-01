# Phase 4 execution progress and frozen Phase 5 preflight

## Purpose

This record describes the execution-safety work added after the baseline,
ChoiceLearn, PopulationSim, and TinyTroupe adapters.  It is deliberately
conservative: a component that has not been validated or provisioned remains
disabled rather than silently becoming part of a paid customer report.

Sequence note: Phase 4 entered production on 2026-08-01. Phase 5 subsequently
completed one isolated OASIS provider experiment and prior-diffusion
comparison. It did not enter production; the final findings and current
decision are recorded in `docs/upgrade-phase5-report.md`.

## Phase 4: durable runs and artifacts

Implemented for native self-service execution:

- A paid run freezes its confirmed study input and fact snapshot before it is
  queued or executed.  The stored SHA-256 identifies that exact snapshot.
- Each run records a `model_component_run` for the native simulation,
  including backend, config version, seed, status, input hash and output
  hash.  The report exposes this safe lineage under `model_components`.
- Input and output manifests can be written as immutable, content-addressed
  JSON objects when all of the following are set:

  ```dotenv
  ENABLE_MODEL_ARTIFACT_PERSISTENCE=true
  MODEL_ARTIFACT_STORE=gcs
  MODEL_ARTIFACT_BUCKET=<private-versioned-bucket>
  ```

  The persisted manifests intentionally exclude raw study input, customer
  facts, Persona transcripts, and report bodies.  The application records
  only object URI, content hash, byte size, media type, and schema version.
- Until a private artifact bucket is provisioned, persistence remains off.
  Reports truthfully say `artifact_persistence: not_configured`; no public or
  fabricated URI is produced.
- A customer can cancel a queued or running run.  Its reservation is returned
  exactly once and the worker checks durable cancellation state before a
  report can be committed.  The API also requests cancellation of the actual
  Cloud Run Job Execution when its provider reference is available.  The study
  returns to `READY` for a later new run.
- A transient failure stores a hash-only checkpoint and exits non-zero so the
  configured Cloud Run retry re-executes the same run.  The retry uses the
  same frozen input digest, component manifest, backend version, config
  version, and seed.  It does not create a second billing reservation.  Only
  a second failure closes the run and refunds the original reservation.
- The full professional native-compute benchmark now covers 100, 5,000,
  20,000, 100,000, and 300,000 people at 220 Monte Carlo rounds, five
  competitors, and fourteen evaluated variants.  Raw measurements are in
  `docs/benchmarks/phase4-native-local-2026-08-01.json`.

## Frozen Phase 5 preflight: isolated OASIS technical verification

OASIS is research-only and remains disabled in every production execution
path:

```dotenv
SOCIAL_SIMULATION_BACKEND=prior
ENABLE_OASIS=false
```

The isolated `Dockerfile.oasis` uses Python 3.11, a hash-locked dependency
set, CAMEL AI 0.2.78, MCP 1.9.4, and the commit-pinned OASIS 0.2.5 source
archive.  The API and the native runner do not import OASIS, CAMEL, torch, or
its Python-3.11-only dependency set.

Technical verification command:

```bash
PYTHONPATH=packages python scripts/validate_oasis_backend.py \
  --output /tmp/oasis-technical-validation.json --agent-count 8
```

The verified protocol uses eight synthetic Thai profiles and manual platform
actions only.  It made zero LLM calls and zero external-platform calls, and
created a local OASIS event trace plus recommendation records.  Its four
output metrics are strictly named as simulated exposure, interaction,
diffusion, and sentiment.  They must never be presented as observed reach,
customer behaviour, purchase probability, sales, revenue, or forecast
accuracy.

## Gate status after Phase 5 audit

1. The private, versioned GCS artifact bucket is provisioned with public
   access prevention, uniform access, soft delete, and least-privilege runtime
   object access. Production artifact persistence is enabled for hash-only
   manifests.
2. Two isolated 300,000-person Cloud Run staging runs completed, including
   retry, cancellation, billable-time, memory, evidence and artifact checks.
3. OASIS failed its dependency-security production gate. Its Gemini secret
   mount and secret-access permission were removed; it remains available only
   for zero-LLM technical validation while a minimal safe image is pending.
4. The non-OASIS API, Runner, Choice-Learn, PopulationSim and TinyTroupe locks
   were upgraded and rescanned with no known vulnerabilities. Details and
   candidate image digests are in `docs/upgrade-security-hardening-report.md`.
5. `ENABLE_OASIS=false` remains mandatory until a later audit explicitly
   passes every OASIS production release gate.
