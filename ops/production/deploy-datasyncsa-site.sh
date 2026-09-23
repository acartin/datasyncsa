#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_TAG="${1:-main}"

export DATASYNCSA_IMAGE_TAG="$IMAGE_TAG"

cd "$SCRIPT_DIR"

echo "Deploying datasyncsa-site:$IMAGE_TAG"
docker compose pull datasyncsa-site
docker compose up -d --remove-orphans --wait --wait-timeout 90

curl --fail --silent --show-error \
  --retry 5 --retry-delay 2 --retry-all-errors \
  --output /dev/null \
  https://datasyncsa.com/

docker compose ps
echo "Deployment completed: https://datasyncsa.com"
