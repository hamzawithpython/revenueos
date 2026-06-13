# Shared image for the main API (with mounted mocks) and, locally, the
# individual mock services (docker-compose overrides the command per service).
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code, pattern files, and eval scorecards
COPY app ./app
COPY synthetic ./synthetic
COPY evals ./evals
COPY run.py ./run.py

# Exec-form CMD running a Python entrypoint that reads PORT from the
# environment itself ? no shell expansion needed, so it works regardless of
# how the platform invokes the container. docker-compose overrides this
# per-service with its own command.
CMD ["python", "run.py"]
