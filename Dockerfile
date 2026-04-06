FROM python:3.10-slim

# Install system dependencies required for hosting bots
RUN apt-get update && apt-get install -y \
    git \
    procps \
    screen \
    curl \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up work directory
WORKDIR /app

# Persistence volume instructions for Railway
# Railway users must add a Volume at /app/data in the Project Settings UI
# VOLUME /app/data  <-- REMOVED due to Railway Build Error

# Install Python Requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Project Files
COPY . .

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Start command
CMD ["python", "main.py"]
