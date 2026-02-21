# Use a slim Python image for the build stage
FROM python:3.13-slim AS builder

WORKDIR /app

# Install system dependencies and Poetry
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies without creating a virtualenv (easier in Docker)
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

# Final Stage
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY src/ ./src/
COPY .env ./

# Ensure the app runs as a non-root user for security
RUN useradd -m makouser
USER makouser

# Default command to run the listener (can be overridden)
CMD ["python", "src/listener/twitch_ws.py"]