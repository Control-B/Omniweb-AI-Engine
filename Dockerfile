# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install all deps into /app/.venv
RUN uv sync --no-dev

# ── Stage 2: FastAPI runtime ──────────────────────────────────────────────────
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

# ── Stage 3: LiveKit Agent Worker ─────────────────────────────────────────────
FROM python:3.12-slim AS agent-worker

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# Copy agent worker + supporting service code (prompt engine, industry config)
COPY agent/ ./agent/
COPY app/services/prompt_engine.py ./app/services/prompt_engine.py
COPY app/services/industry_config.py ./app/services/industry_config.py

# Download Silero VAD model files at build time
RUN python agent/worker.py download-files 2>/dev/null || true

# The agent worker connects outbound to LiveKit Cloud — no ports to expose
CMD ["python", "agent/worker.py", "start"]
