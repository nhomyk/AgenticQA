# AgenticQA — AI Agent Security Scanner
# Multi-stage build for minimal production image

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency definitions first (layer caching)
COPY pyproject.toml setup.py setup.cfg* ./
COPY src/ src/

# Install package + dependencies
RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="AgenticQA"
LABEL org.opencontainers.image.description="AI Agent Security Scanner — 13 scanners, EU AI Act compliance, prompt injection detection"
LABEL org.opencontainers.image.source="https://github.com/nhomyk/AgenticQA"
LABEL org.opencontainers.image.vendor="AgenticQA"

# Non-root user
RUN groupadd -r agenticqa && useradd -r -g agenticqa -m agenticqa

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
WORKDIR /app
COPY agent_api.py .
COPY scripts/ scripts/
COPY src/ src/
COPY public/ public/
COPY dashboard/ dashboard/

# Create data directories
RUN mkdir -p /home/agenticqa/.agenticqa && \
    chown -R agenticqa:agenticqa /app /home/agenticqa/.agenticqa

# Environment defaults
ENV PYTHONPATH="/app/src:/app" \
    PYTHONUNBUFFERED=1 \
    AGENTICQA_AUTH_DISABLE=0 \
    PORT=8000

# Switch to non-root
USER agenticqa

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default: run API server
CMD ["python", "-m", "uvicorn", "agent_api:app", "--host", "0.0.0.0", "--port", "8000"]
