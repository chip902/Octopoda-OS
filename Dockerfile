FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata first (better caching)
COPY pyproject.toml README.md /app/

# Copy source packages
COPY octopoda/ /app/octopoda/
COPY synrix/ /app/synrix/
COPY synrix_runtime/ /app/synrix_runtime/

# Install the package with server + AI extras
RUN pip install --no-cache-dir ".[server,ai]"

# watchfiles (a uvicorn[standard] dep) can land with null-byte-corrupted .py
# files under build pressure, which makes `import uvicorn` raise SyntaxError
# and kills the Cloud API at startup. Force a clean reinstall as a guard.
RUN pip install --force-reinstall --no-deps --no-cache-dir uvloop websockets watchfiles httptools python-dotenv

# Expose API port
EXPOSE 8443

# Environment
ENV SYNRIX_BACKEND=postgres
ENV SYNRIX_API_PORT=8000
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD curl -f http://localhost:8000/health || exit 1

# Start API server
CMD ["python", "-m", "synrix_runtime.start", "--api-port", "8000", "--no-browser"]
