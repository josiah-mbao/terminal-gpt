# =============================================================================
# Terminal GPT - Production Dockerfile
# Multi-stage build for optimized production image
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# Install dependencies and build wheels
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel build

# Copy dependency files first (for better layer caching)
COPY pyproject.toml requirements.txt ./

# Copy source code
COPY src/ ./src/

# Build the package
RUN python -m build --wheel

# Create wheels directory and extract the wheel
RUN mkdir -p /wheels && \
    cp dist/*.whl /wheels/ && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /wheels /wheels/*.whl

# -----------------------------------------------------------------------------
# Stage 2: Production
# Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.11-slim as production

LABEL maintainer="Terminal GPT Team"
LABEL description="Terminal & Web-Ready LLM Chat System"
LABEL version="0.1.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    APP_USER=terminalgpt

# Create non-root user for security
RUN groupadd --gid 1000 ${APP_USER} && \
    useradd --uid 1000 --gid ${APP_USER} --shell /bin/bash --create-home ${APP_USER}

# Set working directory
WORKDIR ${APP_HOME}

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Add any runtime system dependencies here if needed
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Install the application
RUN pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Switch to non-root user
USER ${APP_USER}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from terminal_gpt.main import app; print('Health check passed')" || exit 1

# Expose port for API server
EXPOSE 8000

# Default command
CMD ["python", "-m", "terminal_gpt", "--help"]

# -----------------------------------------------------------------------------
# Stage 3: Development (optional)
# For local development with hot reload
# -----------------------------------------------------------------------------
FROM python:3.11-slim as development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml requirements.txt ./

# Install all dependencies including dev
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source code
COPY src/ ./src/

# Expose port for development server
EXPOSE 8000

# Default command for development (with reload)
CMD ["uvicorn", "terminal_gpt.api.routes:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]