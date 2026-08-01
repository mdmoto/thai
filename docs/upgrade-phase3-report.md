# Phase 3 — TinyTroupe qualitative research

Date: 2026-07-30

## Outcome

The optional TinyTroupe representative-consumer backend is implemented and
technically validated. It remains disabled in production. The current Gemini
backend remains the default.

TinyTroupe is restricted to structured qualitative evidence. Its output has an
explicit quantitative weight of zero and cannot change purchase probability,
market share, sales, or statistical confidence intervals.

## Implementation

- Unified representative-research interface with `off`, `gemini`, and
  `tinytroupe` backends.
- Independent Python 3.12 research image and hash-locked dependency set.
- TinyTroupe 0.7.0 pinned to commit
  `a6244b358a1fe1c71bf751f7ba0f8dfa368ec5a4` and archive SHA-256
  `f997a126be5d29273377baeee67a77b3f60f3f8d1efe21ffebd3668a85a48543`.
- Custom OpenAI-compatible client because TinyTroupe reads a base URL setting
  but its OpenAI client does not pass that URL to the SDK.
- Provider failover: primary Gemini key, secondary Gemini key, then the
  project's paid Vertex AI OpenAI-compatible endpoint after API-key 429s.
- Statistical Persona fields come only from stratified synthetic-population
  records. Passwords, payment data, tokens, email addresses, and unrelated
  customer fields are removed by an allowlist.
- Product and evidence text is treated as untrusted input to reduce prompt
  injection risk.
- Seeded A/B order, immutable Persona-set hash, content hash, Prompt version,
  model version, schema version, and experiment ID are recorded.
- Pydantic output validation, duplicate/unknown Persona rejection, wall-time
  limit, agent limit, model-call limit, token limit, usage accounting, and
  paid-list-price cost estimate.
- Human comparison schema and a weighted categorical distribution validator.
  It refuses any dataset not marked `observed_human_survey`.

## Validation

Technical and cold-start validation passed. The cold-start test installed the
complete lock file into an empty Python 3.12 environment, installed the pinned
TinyTroupe archive without transitive dependency drift, imported the package,
and ran the adapter contract checks.

Live compatibility and multi-Persona reliability passed using Gemini's
OpenAI-compatible endpoint:

- Model: `gemini-3.6-flash`
- Completed Personas: 8/8
- Structured schema-valid rate: 100%
- Persona ID coverage: 100%
- Duplicate or invalid responses: 0
- Model calls: 8
- Wall time: 150.38 seconds
- Input tokens: 49,727
- Visible output tokens: 3,309
- Total provider-reported tokens: 65,385
- Conservative billable output/thinking token estimate: 15,658
- Paid-list-price estimate: USD 0.192026
- Structured output: valid
- Quantitative signal weight: 0

The estimate uses the published standard paid price on the validation date
(USD 1.50/M input tokens and USD 7.50/M output tokens). Actual billing can be
lower or different because of free quota, contractual terms, cached tokens, or
future price changes.

At this observed rate, a sequential 96-Persona qualitative run is projected at
about 30.1 minutes, 784,620 total provider-reported tokens, and USD 2.30 at
the same paid list prices. This is a planning estimate, not a service-level
guarantee. The production guardrails now allow 1.2 million tokens, 320 model
calls, and USD 10 while still stopping abnormal retry loops.

The primary Gemini key returned 429 for minimal Gemini 2.5 and 2.0 requests.
The secondary key succeeded. This is recorded as a credential quota condition,
not a TinyTroupe compatibility failure.

Repeated testing later exhausted the secondary key's short-term rate quota and
also exposed one non-JSON model response. The runner now retries only the
missing Persona once, records the failed attempt, and preserves all previously
completed Personas if a later TinyTroupe action raises an exception.

The full fallback chain was then tested with two Personas. The primary key
returned 429, the adapter automatically switched to Vertex AI in project
`thai-503312`, and Vertex returned 2/2 valid structured responses in 27.57
seconds. No credential value or access token was written to the validation
artifact.

The configured runtime identity
`market-twin-api@thai-503312.iam.gserviceaccount.com` already has
`roles/aiplatform.user`, so no additional owner-side IAM action is currently
required for the Vertex path.

## Production gate

Production remains disabled because one live Persona proves compatibility, not
research validity. A real observed human survey is not currently available, so
the empirical validator was correctly not run. Another LLM was not used as a
substitute for human validation.

Before production promotion:

1. Run repeated reliability tests across the intended Persona counts.
2. Add a real anonymized Thai survey or controlled experiment using the
   `human-ai-response-comparison-v1` schema.
3. Review model quality, latency, paid cost, quota, and report usefulness.
4. Obtain an explicit owner decision to enable both the backend and feature
   flag.

No production service, environment variable, Cloud Run Job, or website was
changed during this phase.
