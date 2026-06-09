FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/backups

# Set volume for persistent data
VOLUME ["/app/data", "/app/logs", "/app/backups"]

CMD ["python", "src/main.py"]
