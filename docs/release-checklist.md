# Release checklist

## Code and data

- [ ] `python -m unittest discover -s tests -v` passes in the project venv.
- [ ] `npm audit` reports zero known vulnerabilities.
- [ ] `npm run build` produces all static routes.
- [ ] API image includes `/data_catalog`.
- [ ] Current NSO manifest hashes match checked-in snapshots.
- [ ] Pet-water panel sources, timestamps and hashes are present.
- [ ] No mock Persona, fake payment, fake progress percentage or hardcoded
      production secret remains.

## Production configuration

- [ ] PostgreSQL backup and restore have been tested.
- [ ] `APP_ENV=production`.
- [ ] Database, JWT and admin secrets come from Secret Manager.
- [ ] CORS lists only the actual production frontend origin.
- [ ] Frontend build points at the v2 API.
- [ ] `/healthz` returns database connected.
- [ ] TLS, security headers and rate limits are active.

## Business flow

- [ ] New registration receives 5 credits once.
- [ ] One free Preview can be completed.
- [ ] Standard consumes 5 credits.
- [ ] Professional consumes 20 credits.
- [ ] Duplicate run requests do not double charge.
- [ ] Failed paid runs refund credits.
- [ ] Pending orders do not grant credits.
- [ ] Verified completion grants credits exactly once.
- [ ] Users cannot read another user’s study or report.

## Sales readiness

- [ ] Pricing on the landing page matches the API catalog.
- [ ] Terms, privacy, methodology and sales operations are reviewed.
- [ ] Official support/payment contact is configured.
- [ ] Sales staff use the approved claims in `sales-operations.md`.
- [ ] A sample report has been reviewed for every public study type and plan.
