# Thailand Market Twin Web

The production customer site and workspace for Thailand Market Twin.

Canonical production endpoints are declared in
`deployment/production.json`. Every production build runs a configuration check
that rejects the retired API service, wildcard Cloud Run access, and unknown
API origins.

## Local development

```bash
npm install
npm run dev
```

Use `.env.local` only for local overrides:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

## Validation

```bash
npm run build
npm run build:sites
```

The supported public frontend is `https://ai.lazzor.com`.
