# Production release evidence

Release verification date: 2026-07-24 (Asia/Bangkok)

## Live services

- Customer site: `https://ai.lazzor.com`
- Production API:
  `https://market-twin-api-100282158973.asia-southeast1.run.app`
- Cloud Run revision: `market-twin-api-00004-cbn`, serving 100% of traffic
- Cloud SQL instance: `market-twin-db`, PostgreSQL 16, regional high
  availability, deletion protection enabled
- Secret Manager: database URL, JWT signing key and admin key are injected only
  into the production service

## Automated verification

- 26 Python tests passed.
- Frontend production build generated all 16 static pages.
- Full `npm audit` reported zero known vulnerabilities.
- Production browser journey passed: register, receive credits, create and
  confirm a pet-water-fountain study, run Standard, open the report, inspect
  every report section, create an order and confirm the official WhatsApp
  payment handoff.
- Production API acceptance passed for Product Validation and Pricing Study on
  Preview, Standard and Professional.
- Run idempotency, cross-account isolation, pending-payment behavior and
  one-time verified credit granting passed.

Acceptance report IDs:

- Product Validation Preview: `rpt_f1bd27d7`
- Product Validation Standard: `rpt_e2d481ef`
- Product Validation Professional: `rpt_7facf2ef`
- Pricing Study Preview: `rpt_a0b2bcdc`
- Pricing Study Standard: `rpt_8ced5249`
- Pricing Study Professional: `rpt_bcd56a14`

## Recovery verification

- Automated Cloud SQL backup `1784901647730` completed successfully.
- Point-in-time clone operation
  `0cdca17b-1826-42fe-9d1b-144a00000031` completed successfully.
- The restored copy contained the production `market_twin` database, database
  users and all six business tables. Restored row counts were checked through
  the Cloud SQL connector.
- The temporary restore instance, query job and temporary secret were deleted
  after verification. The production database was not modified.

## Monitoring

- Public site and API health are checked every minute from Google Cloud
  Monitoring.
- Alert policies cover public-site outage, API outage, Cloud Run 5xx rate,
  Cloud Run p95 latency, Cloud SQL availability, disk utilization, connection
  saturation and transaction-log archive failure.
- Alerts are attached to the authorized production email notification channel.
