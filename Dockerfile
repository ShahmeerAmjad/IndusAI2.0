# MRO Platform Backend - Python/FastAPI
# Multi-stage build for optimized production image

# Stage 1: Dependencies
FROM python:3.12-slim AS base

WORKDIR /app

# System deps for asyncpg and other compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Application
FROM python:3.12-slim AS production

WORKDIR /app

# Runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 wget && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from base
COPY --from=base /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Copy application code
COPY main.py .
COPY models/ models/
COPY services/ services/
COPY routes/ routes/
COPY metrics/ metrics/
COPY templates/ templates/

# Non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
