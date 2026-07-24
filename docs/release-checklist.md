# Release checklist

Verified against production on 2026-07-24.

## Code and data

- [x] `PYTHONPATH=apps/api:packages python -m unittest discover -s tests -v`
      passes in the project venv.
- [x] `npm audit` reports zero known vulnerabilities.
- [x] `npm run build` produces all static routes.
- [x] API image includes `/data_catalog`.
- [x] Current NSO manifest hashes match checked-in snapshots.
- [x] Pet-water panel sources, timestamps and hashes are present.
- [x] No mock Persona, fake payment, fake progress percentage or hardcoded
      production secret remains.

## Production configuration

- [x] PostgreSQL backup and point-in-time restore have been tested.
- [x] `APP_ENV=production`.
- [x] Database, JWT and admin secrets come from Secret Manager.
- [x] CORS lists only the actual production frontend origin.
- [x] Frontend build points at the v2 API.
- [x] `/v1/health` returns database connected.
- [x] TLS, security headers and rate limits are active.

## Business flow

- [x] New registration receives 5 credits once.
- [x] One free Preview can be completed.
- [x] Standard consumes 5 credits.
- [x] Professional consumes 20 credits.
- [x] Duplicate run requests do not double charge.
- [x] Failed paid runs refund credits.
- [x] Pending orders do not grant credits.
- [x] Verified completion grants credits exactly once.
- [x] Users cannot read another user’s study or report.

## Sales readiness

- [x] Pricing on the landing page matches the API catalog.
- [x] Terms, privacy, methodology and sales operations are reviewed.
- [x] Official support/payment contact is configured.
- [x] `sales-operations.md` is the approved claims and payment-operation brief.
- [x] A sample report has been reviewed for every public study type and plan.
