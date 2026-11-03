#!/usr/bin/env bash
# Updates the live app on the EC2 server to one image version.
#
# GitHub Actions runs it after every push to main:
#   ssh ec2-user@SERVER "bash -s -- IMAGE" < deploy/update.sh
# You can also run it by hand on the server:
#   bash update.sh ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/job-tracker:latest
#
# It expects the setup from docs/deploy_aws.md: ~/.env, the jat-net network and Caddy at 172.20.0.2.

set -euo pipefail

IMAGE="${1:?Usage: update.sh IMAGE}"
REGISTRY="${IMAGE%%/*}"

echo "==> Logging in to ECR"
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Downloading $IMAGE"
docker pull --quiet "$IMAGE"

# Update the tables before the new code starts. If this fails, the old version keeps running.
echo "==> Updating the database tables"
docker run --rm --env-file ~/.env "$IMAGE" alembic upgrade head

echo "==> Restarting the app"
docker rm -f jat >/dev/null 2>&1 || true
# The words after "$IMAGE" replace the Dockerfile's start command, so the app trusts only Caddy (172.20.0.2)
# to tell it each visitor's real IP.
# SENTRY_RELEASE tags each error with the commit that's running.
docker run -d --name jat --restart unless-stopped --env-file ~/.env \
  -e SENTRY_RELEASE="${IMAGE##*:}" \
  --network jat-net --ip 172.20.0.10 "$IMAGE" \
  fastapi run main.py --host 0.0.0.0 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips 172.20.0.2 >/dev/null

echo "==> Waiting for the app to report healthy"
for _ in $(seq 1 20); do
  if docker exec jat python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    echo "==> Healthy"
    # Remove app images that haven't been used for a week, so the disk doesn't fill up.
    docker image prune --all --force --filter "until=168h" >/dev/null
    exit 0
  fi
  sleep 3
done

echo "==> The app didn't become healthy. Last log lines:"
docker logs --tail 30 jat
exit 1
