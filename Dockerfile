# BUILD STAGE: installs the dependencies. Its tools don't end up in the final image.
FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

# Install dependencies first, so Docker can reuse this layer when only the app code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY . ./
RUN uv sync --locked --no-dev

# PRODUCTION STAGE: the image that actually runs.
FROM python:3.11-slim-bookworm

WORKDIR /app

# Run as a normal user, so a bug in the app can't act as root inside the container.
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# One worker keeps the in-memory login rate limits accurate.
# By default forwarded IP headers aren't trusted, because anyone could fake them to get
# around the rate limits. On AWS the app runs behind Caddy, and the run command replaces
# this line to trust only Caddy's address (see docs/deploy_aws.md, step 8).
CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
