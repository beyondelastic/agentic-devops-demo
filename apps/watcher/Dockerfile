FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY apps/watcher/pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip && \
    pip install \
      "httpx==0.27.2" \
      "pydantic==2.9.2" \
      "redis==5.2.0" \
      "opentelemetry-api==1.28.2" \
      "opentelemetry-sdk==1.28.2" \
      "azure-monitor-opentelemetry==1.6.4"

COPY apps/watcher/src /app/src

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "watcher.main"]
