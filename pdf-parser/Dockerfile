# syntax=docker/dockerfile:1.6

# Single stage: Python 3.12 + OpenJDK 17 (default-jre on Bookworm).
# We avoid a multi-stage build because copying a uv-built venv between
# different distros breaks the in-venv python symlink. Keeping one base
# guarantees the venv's interpreter is the runtime's interpreter.

FROM python:3.12-slim-bookworm

# Java 17 (opendataloader-pdf shells out to `java -jar`), plus curl/CAs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-jre-headless \
        curl \
        ca-certificates \
        libxcb1 \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the uv binary from the official image (small, no Python install).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dependency layer first for cache reuse on app-only changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app.py entrypoint.sh ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}" \
    VIRTUAL_ENV="/app/.venv" \
    PYTHONUNBUFFERED=1

# huggingface / docling / easyocr 모델 캐시 (compose에서 볼륨 마운트).
RUN mkdir -p /cache
ENV HF_HOME=/cache \
    XDG_CACHE_HOME=/cache \
    EASYOCR_MODULE_PATH=/cache/easyocr

RUN chmod +x /app/entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
