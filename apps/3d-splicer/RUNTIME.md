# Runtime Requirements

## Recommended: Docker (Zero Wheel Pain)

The **fastest path to green** is using CadQuery's prebuilt Docker base image:

```bash
# Build and run
make docker-build
make docker-run

# Test
make test
```

This approach:
- ✅ Uses tested CadQuery/OCP/OCC stack
- ✅ Avoids Python 3.13 wheel compatibility issues  
- ✅ No local dependency management
- ✅ Production-ready containerization

## Alternative: Local Python 3.11

For local development:

```bash
# Install Python 3.11 (pyenv recommended)
pyenv install 3.11.9
pyenv local 3.11.9

# Set up environment
make local-setup

# Run
make run
```

## Why Python 3.13 Fails

- **cadquery-ocp** wheels trail new Python releases
- **casadi** and **nlopt** have spotty Python 3.13 support
- **numpy 2.x** ABI changes break some geometry libs

## Version Pinning

- **NumPy**: `<2.0.0` (ABI compatibility)
- **CadQuery**: Latest stable (2.3.x)
- **FastAPI**: `>=0.110` (modern async support)

## Health Checks

- `/health` - Basic API status
- `/health/geom` - Validates CadQuery/OCP stack with actual STL export

## Testing

```bash
# Quick health check
make test

# Minimal case test
make test-min

# Full iPhone 7 test  
make test-iphone

# CadQuery diagnostics
make diag
```

## Production Deployment

The Docker approach is production-ready:

```bash
# Build production image
docker build -t 3d-splicer:latest .

# Run with volume mounts
docker run -d \
  --name splicer-api \
  -p 8000:8000 \
  -v /path/to/stl:/app/stl \
  3d-splicer:latest
```
