#!/bin/bash

# Clean rebuild and startup script for ZAP Docker environment

# Stop any running containers and clean up
echo "Stopping any existing containers..."
docker-compose down

# Rebuild with no cache
echo "Rebuilding containers with --no-cache..."
docker-compose build --no-cache

# Start containers in detached mode
echo "Starting containers in detached mode..."
docker-compose up -d

# Wait a moment for containers to initialize
echo "Waiting 5 seconds for containers to initialize..."
sleep 5

# Show ZAP container logs with follow
echo "Showing ZAP container logs (Ctrl+C to exit)..."
docker logs zap-scanner -f