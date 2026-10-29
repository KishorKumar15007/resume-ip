FROM python:3.14.2-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /build

RUN python -m venv /opt/venv

COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt

FROM python:3.14.2-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R 10001:10001 /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 app ./app

USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 CMD ["python", "-c", "import os; from urllib.request import urlopen; response = urlopen(f\"http://127.0.0.1:{os.environ['PORT']}/health\", timeout=2); assert response.status == 200"]

FROM runtime AS worker

CMD ["sh", "-c", "exec uvicorn app.worker:app --host 0.0.0.0 --port \"${PORT}\""]

FROM runtime AS api

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT}\""]
