#!/bin/bash
# Cleanup script for AI-Powered Customer Support Chatbot

set -e

echo "=========================================="
echo "Chatbot Project Cleanup"
echo "=========================================="

# Stop and remove all containers
echo "Stopping all services..."
docker compose down -v --remove-orphans

# Clean up logs (optional)
if [ "$1" = "--clean-logs" ]; then
    echo "Cleaning up log files..."
    rm -f src/backend/logs/*.jsonl
    rm -f results/*.json
    echo "✓ Log files removed"
fi

# Clean up Python cache
echo "Cleaning up cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true

# Clean up build artifacts
echo "Cleaning up build artifacts..."
rm -rf src/frontend/dist
rm -rf src/ai-chatbot/target

echo ""
echo "=========================================="
echo "Cleanup Complete!"
echo "=========================================="
echo ""
echo "To restart: ./scripts/setup.sh"
echo ""