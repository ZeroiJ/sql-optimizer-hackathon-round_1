#!/bin/bash
set -e

echo "Building SQL Query Optimizer Docker image..."
docker build -t sql-optimizer-env .

echo ""
echo "Starting container on port 8000..."

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "WARNING: Port 8000 is already in use."
    echo "Stopping existing process..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Also stop any existing Docker container on port 8000
docker stop sql-optimizer-env 2>/dev/null || true
docker rm sql-optimizer-env 2>/dev/null || true

echo "NOTE: In a separate terminal, run:"
echo "  uv run python scripts/test_hardcoded.py"
echo ""

docker run --rm --name sql-optimizer-env -p 8000:8000 sql-optimizer-env
