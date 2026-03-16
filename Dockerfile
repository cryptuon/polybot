# =============================================================================
# PolyBot Dockerfile
# Multi-stage build for optimized production image
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build frontend (if exists)
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Check if frontend exists and build
COPY frontend/package*.json ./
RUN if [ -f package.json ]; then npm ci --no-audit; fi

COPY frontend/ ./
RUN if [ -f package.json ]; then npm run build; else mkdir -p dist; fi

# -----------------------------------------------------------------------------
# Stage 2: Build Python dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS python-builder

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies (without dev dependencies)
RUN uv sync --frozen --no-dev --no-editable || uv sync --no-dev --no-editable

# -----------------------------------------------------------------------------
# Stage 3: Production image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS production

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash polybot

WORKDIR /app

# Copy virtual environment from builder
COPY --from=python-builder /app/.venv /app/.venv

# Copy application source
COPY src/ ./src/
COPY config/ ./config/ 2>/dev/null || true

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist/ 2>/dev/null || true

# Create data directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R polybot:polybot /app

# Set environment variables
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SQLITE_PATH=/app/data/polybot.db \
    DUCKDB_PATH=/app/data/analytics.duckdb \
    STRATEGY_LOGS_PATH=/app/data/strategy_logs.duckdb \
    LOG_FORMAT=json \
    LOG_LEVEL=INFO \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Switch to non-root user
USER polybot

# Default command - start API server
CMD ["python", "-m", "polybot", "api"]
