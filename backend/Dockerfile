# Shared image for all mock EDI services and (later) the main API.
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code, pattern files, and eval scorecards
COPY app ./app
COPY synthetic ./synthetic
COPY evals ./evals

# Default command. Shell form so ${PORT} is expanded by the shell at runtime
# (Railway injects PORT). Falls back to 8000 locally where PORT is unset.
# docker-compose overrides this per-service with its own command.
CMD uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}


