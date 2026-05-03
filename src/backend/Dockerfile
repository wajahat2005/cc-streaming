# Multi-arch base image: works on both amd64 (local) and arm64 (Oracle Cloud VM).
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download TextBlob corpora
RUN python -m textblob.download_corpora

# Copy application code
COPY . .

# Environment defaults
ENV LUCENE_URL=http://lucene:4567
ENV KAFKA_BROKER=kafka:9092
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]