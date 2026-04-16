# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install all deps into /app/.venv
RUN uv sync --no-dev

# ── Stage 2: Shopify microservice ────────────────────────────────────────────
FROM python:3.12-slim AS shopify

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY static/ ./static/

EXPOSE 8001

CMD ["uvicorn", "app.shopify_main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

# ── Stage 3 (final): FastAPI runtime ─────────────────────────────────────────
# This MUST be the last stage so DigitalOcean App Platform picks it up
# as the default build target.
FROM python:3.12-slim AS api

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY seed.py ./
COPY static/ ./static/

EXPOSE 8000

# Run database migrations (best-effort) then start the FastAPI server
CMD ["sh", "-c", "alembic upgrade head || echo 'WARNING: alembic migration failed, starting anyway'; uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
