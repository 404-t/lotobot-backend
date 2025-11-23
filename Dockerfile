FROM python:3.13-slim AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app_dir
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
COPY src/ ./src/

# Устанавливаем PATH для использования uv
ENV PATH="/app_dir/.venv/bin:$PATH"

# Запускаем приложение через uvicorn
# Для Docker всегда используем 0.0.0.0 (слушает на всех интерфейсах)
# Порт берем из переменной окружения APP_PORT или используем 8000 по умолчанию
CMD ["sh", "-c", "uv run uvicorn src.main:app --host 0.0.0.0 --port ${APP_PORT:-8000}"]