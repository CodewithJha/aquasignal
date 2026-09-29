# ConfirmGate + AquaSignal — single-process FastAPI app on SQLite.
# Build:  docker build -t confirmgate .
# Run:    docker run --rm -p 8000:8000 -v confirmgate-data:/data confirmgate
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-deps -r requirements.txt && pip check && pip check

COPY app ./app
COPY scripts ./scripts

RUN useradd --system --uid 10001 --home-dir /app appuser \
    && mkdir -p /data \
    && chown appuser /data
USER appuser

# AI is off unless AI_PROVIDER / AI_API_KEY are supplied at runtime.
ENV DATABASE_URL=sqlite:////data/confirmgate.sqlite3 \
    AI_PROVIDER=null \
    PORT=8000

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/healthz', timeout=4)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
