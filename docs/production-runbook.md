# Production runbook

## Required services

1. PostgreSQL 15+ with automated backups and encrypted transport.
2. Google Secret Manager secrets:
   - `market-twin-database-url`
   - `market-twin-jwt-secret`
   - `market-twin-admin-api-key`
3. Artifact Registry repository `market-twin` in `asia-southeast1`.
4. Runtime service account `market-twin-api` with only Secret Manager access
   and Cloud SQL Client permissions.
5. Cloud Run service `market-twin-api`, attached to the Cloud SQL instance.
6. Static frontend with `NEXT_PUBLIC_API_URL` fixed to the deployed API URL at
   build time.

Use independent random values of at least 32 bytes for JWT and admin keys.
Never put these values in Git, browser variables or Cloud Build substitutions.

## First deployment

```bash
gcloud artifacts repositories create market-twin \
  --repository-format=docker \
  --location=asia-southeast1

gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions='^|^_CORS_ORIGINS=https://ai.lazzor.com,https://YOUR-PREVIEW-DOMAIN'
```

The database secret must use the Cloud SQL Unix socket form:

```text
postgresql+psycopg://USER:PASSWORD@/DATABASE?host=/cloudsql/PROJECT:asia-southeast1:market-twin-db
```

Before the build, grant `roles/cloudsql.client` and
`roles/secretmanager.secretAccessor` to the dedicated runtime service account.
Grant the Cloud Build service account permission to deploy Cloud Run, use the
runtime service account and read the image repository. Do not grant those
roles to public users or to the frontend.

The checked-in deployment keeps one warm API instance, uses second-generation
Cloud Run execution, applies startup and liveness checks against `/healthz`,
and caps scale-out at five instances to protect the database.

`Base.metadata.create_all` creates a new schema. Startup also performs the
limited pre-v2 compatibility migration needed for existing users,
transactions and reports. Back up an existing production database before the
first v2 rollout.

## Frontend build

Set before the static build:

```bash
NEXT_PUBLIC_API_URL=https://YOUR_CLOUD_RUN_URL \
NEXT_PUBLIC_SITE_URL=https://ai.lazzor.com \
NEXT_PUBLIC_SALES_URL=https://lazzor.com \
npm --prefix apps/web run build
```

Upload `apps/web/out/` to the production static host. Do not deploy a build
whose API URL is localhost or the retired v1 service.

## Release verification

```bash
curl -fsS https://YOUR_CLOUD_RUN_URL/healthz
curl -fsS https://YOUR_CLOUD_RUN_URL/v1/catalog
```

Run the checked-in acceptance script. It creates isolated `example.invalid`
accounts and does not expose their access tokens:

```bash
MARKET_TWIN_API_URL=https://YOUR_CLOUD_RUN_URL \
MARKET_TWIN_ADMIN_API_KEY=YOUR_ADMIN_KEY \
python3 scripts/smoke_test.py
```

The script verifies health and database connectivity, signup credits, Preview,
Standard charging, run idempotency, report ownership isolation, pending-order
behavior, protected payment completion and one-time credit granting.

## Monitoring

- Alert on `/healthz` non-200 for two consecutive checks.
- Alert on Cloud Run 5xx rate and latency.
- Alert on PostgreSQL storage, connection saturation and backup failure.
- Review `FAILED_RECOVERABLE` studies and refund transactions daily.
- Retain request IDs in application logs; never log tokens or full project
  inputs.

## Rollback

1. Route Cloud Run traffic to the previous healthy revision.
2. Keep the database online; application rollback does not delete data.
3. If a schema problem is suspected, stop writes and restore a verified backup
   to a new database rather than editing the only production copy.
4. Point the frontend back only after `/healthz`, auth and one report read pass.

## Key rotation

Rotating `ADMIN_API_KEY` is immediate. Rotating `JWT_SECRET_KEY` signs out all
users and requires a new login. Update Secret Manager, deploy a new revision,
verify health, then disable the old secret version.
