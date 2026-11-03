#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:?Usage: update.sh IMAGE}"
REGISTRY="${IMAGE%%/*}"

echo "==> Logging in to ECR"
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Downloading $IMAGE"
docker pull --quiet "$IMAGE"

echo "==> Updating the database tables"
docker run --rm --env-file ~/.env "$IMAGE" alembic upgrade head

echo "==> Restarting the app"
docker rm -f jat >/dev/null 2>&1 || true
docker run -d --name jat --restart unless-stopped --env-file ~/.env \
  -e SENTRY_RELEASE="${IMAGE##*:}" \
  --network jat-net --ip 172.20.0.10 "$IMAGE" \
  fastapi run main.py --host 0.0.0.0 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips 172.20.0.2 >/dev/null

echo "==> Waiting for the app to report healthy"
for _ in $(seq 1 20); do
  if docker exec jat python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    echo "==> Healthy"
    docker image prune --all --force --filter "until=168h" >/dev/null
    exit 0
  fi
  sleep 3
done

echo "==> The app didn't become healthy. Last log lines:"
docker logs --tail 30 jat
exit 1
