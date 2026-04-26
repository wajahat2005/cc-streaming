#!/bin/bash
# Setup script for AI-Powered Customer Support Chatbot

set -e

echo "=========================================="
echo "Chatbot Project Setup"
echo "=========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker Desktop."
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not available."
    exit 1
fi

echo "✓ Docker and Docker Compose are available"

# Create necessary directories
echo "Creating required directories..."
mkdir -p results
mkdir -p src/backend/logs
mkdir -p src/backend/data/models

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ Created .env from .env.example"
    fi
fi

# Build and start all services
echo ""
echo "=========================================="
echo "Building and starting services..."
echo "=========================================="

docker compose up --build -d

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Services available at:"
echo "  - Frontend:    http://localhost:3000"
echo "  - Backend:     http://localhost:8000"
echo "  - API Docs:    http://localhost:8000/docs"
echo "  - Lucene API:  http://localhost:4567"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop:      ./scripts/cleanup.sh"
echo ""

