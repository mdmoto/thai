# Market Simulation Methodology v2

## What changed

The quantitative path is now:

```text
official macro margins + versioned behavior priors
  -> synthetic micro-population
  -> study-specific choice model
  -> focal offer + competitors + outside option
  -> bounded LLM weak-label adjustment
  -> prior-predictive Monte Carlo
  -> price/scenario/diffusion outputs
  -> report lineage and limitations
```

LLM output is not averaged into purchase rate. If the LLM provider is
unavailable, the response contains no invented personas and its quantitative
weight is zero.

## Calibration status

The default consumer-products profile is
`data_catalog/thailand_consumer_products_macro_v1.json`. It is marked
`official_macro_calibrated_choice_prior`.

The following dimensions are observed public aggregates:

- 2025 registered population by province and binary sex;
- 2023 household-income bands by NSO region;
- 2023 province household income and expenditure;
- 2024 average household size by province.

Each source has an official dataset URL, license, retrieval time, record count,
SHA-256, and compressed raw snapshot under `data_catalog/raw/nso/`.

The following dimensions remain priors rather than observed evidence:

- adult age distribution;
- psychographics and brand preference;
- category penetration and purchase frequency;
- all choice coefficients, WTP, conversion and repeat behavior.

## First category: pet water fountains

The first versioned category profile is
`data_catalog/category_profiles/pet_water_fountain_v1.json`. It restricts the
choice set to synthetic pet-owning households and combines pet-spend intensity
with online-shopping engagement. Both category eligibility and engagement are
explicit priors until a Thailand pet-ownership or category-penetration source
is acquired.

The public offer panel is
`data_catalog/categories/pet_water_fountain_th_v1.json`. It contains
robots-permitted product pages from three Thailand retailers, page hashes,
point-in-time THB offer prices, seller or brand feature claims, and a
price-stratified five-offer choice set. Missing awareness, brand strength and
social-proof fields remain disclosed model assumptions. Review counts are
never converted into sales.

The older `data_catalog/thailand_market_priors_v1.json` remains the explicit
engineering-prior base from which the official aggregate profile is built.

The profile may be replaced or overridden by observed data. Enterprise and
Deep plans expose this path, while lower plans ignore customer coefficient
overrides and disclose that fact.

## Choice model

Each study type selects a distinct coefficient profile. The engine evaluates a
multinomial choice set:

- the focal offer;
- zero or more supplied competitors;
- an outside/no-purchase option.

Price, affordability, quality, trust, reviews, novelty, convenience, social
influence, category engagement, localization, and—where relevant—distance
enter utility separately. Deep and Enterprise add random taste heterogeneity.

## Fitting observed choices

`packages/simulation_core/estimation.py` fits a conditional multinomial logit
model from long-format observed choices. Each choice set must have at least two
alternatives and exactly one chosen row. Suitable evidence includes:

- conjoint or forced-choice survey tasks;
- historical transactions with an explicit choice set;
- controlled price or creative A/B tests;
- customer CRM and order data joined to offer exposure.

LLM-generated choices must not be labelled as observed data.

## Uncertainty

Until historical backtesting exists, P10–P90 is named a
`prior_predictive_p10_p90` interval. It includes coefficient-prior uncertainty,
population heterogeneity, and plan-dependent taste heterogeneity. It is not
called a validated confidence interval.

## Required next evidence

Before production forecasting claims:

1. obtain an observed Thailand pet-ownership/category-penetration margin;
2. add permitted marketplace or licensed sell-through evidence;
3. run a real forced-choice/conjoint panel or controlled market experiment;
4. fit category coefficients to those observed choices;
5. maintain holdout and time-based backtests;
6. report calibration error by study type and region;
7. version competitor, model, prompt, data and random-seed inputs.

## Public-data refresh

`packages/data_pipeline/nso.py` fetches only fixed official public endpoints
and fails closed on schema drift, record-count regressions, invalid JSON or
oversized responses. `packages/data_pipeline/consumer_products.py` transforms
those snapshots into the profile without altering choice coefficients.

`packages/data_pipeline/product_pages.py` is a conservative product-page
metadata collector. It checks robots.txt, rate-limits requests, accepts HTTPS
HTML only, and extracts Product JSON-LD or supported open graph fields. Its
records explicitly state that they are not transaction or conversion data.
