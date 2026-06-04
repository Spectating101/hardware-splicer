FROM ghcr.io/cadquery/cadquery:latest
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.api.txt .
RUN python -m pip install --upgrade pip && pip install -r requirements.api.txt

# Install Prometheus client for metrics
RUN pip install prometheus-client

# Copy application code
COPY . .

# Create artifacts directory
RUN mkdir -p /app/artifacts

# Set production environment variables
ENV ARTIFACT_DIR=/app/artifacts
ENV MAX_ITERS=5
ENV ITER_TIMEOUT_S=30
ENV JOB_TIMEOUT_S=180
ENV MUST_PASS=fit,printability
ENV WEIGHTS='{"fit":2.0,"printability":2.0,"io":1.5,"drop_proxy":1.0,"thermal":0.5}'
ENV IDEMPOTENCY=on
ENV ENABLE_METRICS=true
ENV METRICS_PORT=9090
ENV PRUNE_INTERMEDIATE_STLS=true
ENV KEEP_FINAL_ARTIFACTS=true

# Expose ports
EXPOSE 8000
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
