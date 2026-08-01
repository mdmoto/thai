#!/usr/bin/env bash
set -euo pipefail

audit_output_dir="${1:-docs/image-audits}"
mkdir -p "${audit_output_dir}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to build and inspect compute images" >&2
  exit 2
fi
if ! command -v syft >/dev/null 2>&1; then
  echo "syft is required to generate SPDX SBOM and license records" >&2
  exit 2
fi

while IFS="|" read -r image_name dockerfile; do
  image_tag="market-twin-audit-${image_name}:local"
  docker build --file "${dockerfile}" --tag "${image_tag}" .
  docker image inspect "${image_tag}" \
    --format '{"image":"{{.RepoTags}}","size_bytes":{{.Size}}}' \
    > "${audit_output_dir}/${image_name}-image.json"
  syft "${image_tag}" \
    --output "spdx-json=${audit_output_dir}/${image_name}-sbom.spdx.json"
done <<'EOF'
api|Dockerfile.api
native-runner|Dockerfile.runner
choice-job|Dockerfile.choice
population-job|Dockerfile.population
tinytroupe-job|Dockerfile.tinytroupe
EOF
