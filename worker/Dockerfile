# syntax=docker/dockerfile:1

# ---- Stage 1: build ---------------------------------------------------------
# Installs dependencies into a virtualenv. Build tools and uv itself stay in
# this stage and never reach the final image.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first: this layer is cached until uv.lock changes, so editing
# app code doesn't trigger a full reinstall.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev

COPY app ./app

# The template geometry lives in print/geometry/, outside this build context (worker/).
# It comes in as a *named build context*: an extra folder handed to the build, so the
# JSON isn't copied into worker/ and the rest of the repo isn't sent to Docker.
# Build with:  docker build --build-context geometry=../print/geometry -t fitfinder-worker .
# Without that flag, Docker treats "geometry" as an image name and fails to pull it.
COPY --from=geometry *.json ./geometry/

# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

# Unprivileged user: if the app is ever compromised, the attacker isn't root.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

# OPENCV_IO_MAX_IMAGE_PIXELS: OpenCV refuses to decode images over 50 MP, a backstop
# against decompression bombs (#29; the worker also checks the size before decoding).
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    TEMPLATE_GEOMETRY_DIR=/app/geometry \
    OPENCV_IO_MAX_IMAGE_PIXELS=50000000

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=2)"]

# Default: the HTTP app (/health). Cloud Run injects $PORT; shell form so it's expanded.
# The queue worker runs from the same image as a Cloud Run *Job* with the command
# overridden (ADR 0003, deployed in #33):  python -m app.jobs.drain
CMD exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
