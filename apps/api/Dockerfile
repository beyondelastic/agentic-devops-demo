FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY apps/api/pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip && \
    pip install \
      "fastapi==0.115.4" \
      "uvicorn[standard]==0.32.0" \
      "gunicorn==23.0.0" \
      "pydantic==2.9.2" \
      "pydantic-settings==2.6.0" \
      "azure-ai-projects==2.1.0" \
      "azure-identity==1.19.0" \
      "openai==2.32.0" \
      "httpx==0.27.2" \
      "opentelemetry-api==1.28.2" \
      "opentelemetry-sdk==1.28.2" \
      "opentelemetry-instrumentation-fastapi==0.49b2" \
      "azure-monitor-opentelemetry==1.6.4"

COPY apps/api/src /app/src

ARG GIT_SHA=dev
ARG BUILT_AT=unknown
ENV GIT_SHA=${GIT_SHA} \
    BUILT_AT=${BUILT_AT} \
    PYTHONPATH=/app/src \
    PORT=8000

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)" || exit 1

CMD ["gunicorn", "api.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
