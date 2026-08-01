# Upgrade Phase 1 report — Choice-Learn validation

Date: 2026-07-30  
Production default changed: no  
Production deployment: not performed

## Outcome

The optional Choice-Learn Conditional Logit backend is implemented behind the
existing choice-model adapter. It uses lazy imports, an isolated dependency
lock and a dedicated validation image. The API and native runner do not install
TensorFlow or Choice-Learn.

Choice-Learn passed the functional validation gate but did not demonstrate a
material prediction improvement over the native estimator. The production
recommendation is therefore **retain the native default**.

This decision is based on effect quality, not speed or cost. The candidate was
not rejected because it was slower; it was not promoted because its holdout
prediction was statistically indistinguishable from the existing estimator.

## Compatibility finding

The original `tensorflow==2.20.0` candidate deadlocked or crashed during arm64
initialization across protobuf 7.x, 6.31.1 and 5.28.3 trials. The validation
image was reduced to a true compute-only dependency set and successfully
validated with:

- `choice-learn==1.3.2`
- `tensorflow==2.19.1`
- `tf-keras==2.19.0`
- `protobuf==5.29.6`
- `numpy==2.0.2`

These versions are fully resolved in the hash-locked Choice job dependency
file. None enters the API lock.

## Adapter behavior

The backend now supports:

- long-format grouped choice data;
- focal, competitor and outside alternatives;
- conditional-logit fitting with shared coefficients;
- probability prediction on holdout sets;
- deterministic TensorFlow seeding;
- coefficient, standard-error, covariance and gradient diagnostics;
- per-choice-set probability-sum checks;
- explicit outside-option coverage diagnostics;
- immutable coefficient artifacts containing training-data hash, feature
  mapping, backend/dependency versions, seed, fit diagnostics and validation
  status.

Choice-Learn averages its training loss while the native estimator uses a
summed likelihood. Its L2 regularization is therefore divided by the number of
choice sets so both backends optimize the same statistical objective. Without
that scale correction, the candidate coefficients were incorrectly shrunk
toward zero; the validation caught and fixed this before any production use.

## Deidentification improvement

Observed choice rows still replace customer choice-set IDs and alternative
names with neutral IDs. A non-identifying `is_outside_option` boolean is now
preserved or derived before names are removed. This lets reports verify that
every choice set contains a no-purchase/no-choice alternative without retaining
customer or SKU identity.

## Holdout validation

The checked-in validation uses three deterministic synthetic recovery datasets:

- 600 choice sets per seed;
- 480 training and 120 holdout choice sets;
- three alternatives per set;
- price, quality and brand-trust features;
- known negative price and positive quality coefficients.

Results:

| Seed | Native holdout log loss | Choice-Learn holdout log loss | Improvement |
| --- | ---: | ---: | ---: |
| 20260730 | 1.100671261 | 1.100670351 | +0.000000909 |
| 20260731 | 1.025668505 | 1.025668582 | -0.000000077 |
| 20260732 | 1.055481496 | 1.055481219 | +0.000000277 |

Mean Choice-Learn log-loss improvement: **0.000000370**.

All three runs:

- converged;
- recovered a negative price coefficient;
- recovered a positive quality coefficient;
- included one outside option per choice set;
- produced probabilities summing to 1 within numerical tolerance.

The first Choice-Learn fit incurred TensorFlow initialization and took about
4.60 seconds versus 0.10 seconds for native. Warm fits took about 0.46 seconds.
This cost difference did not determine the gate result.

A same-seed rerun reproduced the Choice-Learn coefficients exactly and produced
the same artifact SHA-256:

`c433a9f06434d23ff173d6563756ee806c1260e0857637eded72d35f28559278`

## Gate decision

Choice-Learn is retained as a validated optional research backend and as the
foundation for later nested or latent-class experiments. It must not become the
production Conditional Logit default based on this result.

Promotion remains possible only after customer observed-choice data is
available and Choice-Learn improves both holdout and time-based validation.
Synthetic recovery tests prove implementation correctness; they are not
customer-market evidence.
