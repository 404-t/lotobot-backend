FROM python:3.13-slim AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app_dir/src
RUN apt-get update && \
    apt-get install --yes --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app_dir

FROM base AS builder

RUN pip install --upgrade "uv>=0.6,<1.0" && rm -rf /root/.cache/*
ADD pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --verbose --no-progress

FROM base AS final

RUN pip install --upgrade "uv>=0.6,<1.0"
COPY --from=builder /app_dir/.venv ./.venv
ADD ../src/ ./src

CMD ["uv", "run", "src/main.py"]