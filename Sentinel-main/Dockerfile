FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Install the sentinel package in development mode
RUN pip install -e .

EXPOSE 8000

# Default command — can be overridden in docker-compose
CMD ["uvicorn", "sentinel.gateway:api", "--host", "0.0.0.0", "--port", "8000", "--reload"]
