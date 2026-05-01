# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install all deps into /app/.venv
RUN uv sync --no-dev

# ── Stage 2 (final): FastAPI runtime ─────────────────────────────────────────
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

EXPOSE 8000

# Run database migrations then start the FastAPI server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
