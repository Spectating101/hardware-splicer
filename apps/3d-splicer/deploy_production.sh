#!/bin/bash
# Production deployment script for 3D Splicer v0.1

set -e

echo "🚀 3D Splicer v0.1 Production Deployment"
echo "========================================"

# Configuration
IMAGE_NAME="3d-splicer-v01"
CONTAINER_NAME="3d-splicer-prod"
PORT=8000
METRICS_PORT=9090

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

print_status "Docker is running"

# Build the image
echo "🔨 Building production image..."
docker build -t $IMAGE_NAME .
print_status "Image built successfully"

# Stop and remove existing container if it exists
if docker ps -a --format 'table {{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
    echo "🛑 Stopping existing container..."
    docker stop $CONTAINER_NAME || true
    docker rm $CONTAINER_NAME || true
    print_status "Existing container removed"
fi

# Run the container
echo "🚀 Starting production container..."
docker run -d \
    --name $CONTAINER_NAME \
    -p $PORT:8000 \
    -p $METRICS_PORT:9090 \
    -v $(pwd)/artifacts:/app/artifacts \
    --restart unless-stopped \
    $IMAGE_NAME

print_status "Container started successfully"

# Wait for container to be ready
echo "⏳ Waiting for service to be ready..."
sleep 10

# Health checks
echo "🔍 Running health checks..."

# Basic health check
if curl -s http://localhost:$PORT/health | grep -q '"ok":true'; then
    print_status "Basic health check passed"
else
    print_error "Basic health check failed"
    docker logs $CONTAINER_NAME
    exit 1
fi

# Geometry health check
if curl -s http://localhost:$PORT/health/geom | grep -q '"ok":true'; then
    print_status "Geometry health check passed"
else
    print_error "Geometry health check failed"
    docker logs $CONTAINER_NAME
    exit 1
fi

# Evaluator health check
if curl -s http://localhost:$PORT/health/evaluator | grep -q '"ok":true'; then
    print_status "Evaluator health check passed"
else
    print_warning "Evaluator health check failed (non-critical)"
fi

# Metrics check
if curl -s http://localhost:$PORT/metrics | grep -q "splicer_optimization_requests_total"; then
    print_status "Metrics endpoint working"
else
    print_warning "Metrics endpoint not responding (non-critical)"
fi

# Run golden specs test
echo "🧪 Running golden specs test..."
if python test_golden_specs.py; then
    print_status "Golden specs test passed"
else
    print_error "Golden specs test failed"
    docker logs $CONTAINER_NAME
    exit 1
fi

# Final status
echo ""
echo "🎉 Production deployment successful!"
echo "=================================="
echo "Service URL: http://localhost:$PORT"
echo "Metrics URL: http://localhost:$PORT/metrics"
echo "Health URL: http://localhost:$PORT/health"
echo ""
echo "Container: $CONTAINER_NAME"
echo "Image: $IMAGE_NAME"
echo ""
echo "Useful commands:"
echo "  docker logs $CONTAINER_NAME          # View logs"
echo "  docker stats $CONTAINER_NAME         # View resource usage"
echo "  docker restart $CONTAINER_NAME       # Restart service"
echo "  docker stop $CONTAINER_NAME          # Stop service"
echo ""
echo "Monitoring:"
echo "  curl http://localhost:$PORT/metrics/summary"
echo "  curl http://localhost:$PORT/health/evaluator"
echo ""
print_status "3D Splicer v0.1 is ready for production use!"
