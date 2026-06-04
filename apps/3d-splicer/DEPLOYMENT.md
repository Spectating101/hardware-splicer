# 3D Splicer MVP - Deployment Guide

## 🚀 **Production Deployment**

### Docker (Recommended)

```bash
# Build production image
docker build -t 3d-splicer:latest .

# Run container
docker run -d \
  --name splicer-api \
  -p 8000:8000 \
  -v /path/to/stl:/app/stl \
  --restart unless-stopped \
  3d-splicer:latest

# Verify deployment
curl http://localhost:8000/health/geom
```

### Local Python 3.11

```bash
# Set up environment
pyenv install 3.11.9
pyenv local 3.11.9
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install "numpy<2" cadquery cadquery-ocp \
  fastapi uvicorn[standard] jinja2 pydantic trimesh \
  multimethod pyparsing typish nptyping ezdxf

# Run server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## 🔧 **Circuit.AI Integration**

### Environment Setup

```bash
export SPLICER_URL="http://your-splicer-host:8000"
```

### Python Client Usage

```python
from circuit_ai_client import generate_case, health_check

# Health check
health = health_check()
print(f"Splicer status: {health}")

# Generate case
payload = {
    "version": "v1",
    "device": "your_device",
    "pcb": {
        "width_mm": 70.0,
        "height_mm": 35.0,
        "thickness_mm": 1.2,
        "corner_radius_mm": 3.0
    },
    "enclosure": {
        "wall_mm": 1.6,
        "clearance_mm": 0.6,
        "lip_mm": 1.2,
        "fillet_mm": 1.0
    },
    "ports": [...],
    "mounts": [...]
}

result = generate_case(payload)
print(f"Generated: {result['stl_path']}")
```

## 🏥 **Health Monitoring**

### Endpoints

- `GET /health` - Basic API status
- `GET /health/geom` - CadQuery/OCP stack validation

### Health Check Response

```json
{
  "ok": true,
  "bytes": 684
}
```

## 📊 **API Endpoints**

### Generate Case
```bash
curl -X POST http://localhost:8000/v1/splice \
  -H "Content-Type: application/json" \
  --data @examples/min_case.json
```

### Download STL
```bash
curl -O http://localhost:8000/v1/stl/device_case_v1.stl
```

## 🔒 **Production Considerations**

### Security
- Run behind reverse proxy (nginx/traefik)
- Use HTTPS in production
- Implement rate limiting
- Add authentication if needed

### Performance
- Monitor STL generation timeouts
- Implement request queuing for high load
- Use persistent volume for STL storage
- Consider horizontal scaling

### Monitoring
- Set up health check alerts
- Monitor `/health/geom` for geometry stack issues
- Track STL generation success rates
- Log generation times and errors

## 🐛 **Troubleshooting**

### Common Issues

1. **OCP Compatibility Error**
   ```
   'OCP.OCP.TopoDS.TopoDS_Vertex' object has no attribute 'HashCode'
   ```
   **Solution**: Use Python 3.11 or Docker base image

2. **NumPy ABI Issues**
   ```
   module 'numpy' has no attribute 'bool8'
   ```
   **Solution**: Pin `numpy<2` in requirements

3. **Memory Issues**
   **Solution**: Increase container memory limits for large STL generation

### Debug Commands

```bash
# Check geometry stack
curl http://localhost:8000/health/geom

# Test minimal case
curl -X POST http://localhost:8000/v1/splice \
  -H "Content-Type: application/json" \
  --data @examples/min_case.json

# View logs
docker logs splicer-api
```

## 📈 **Scaling**

### Horizontal Scaling
- Deploy multiple containers behind load balancer
- Use shared storage for STL files
- Implement request queuing (Redis/RabbitMQ)

### Vertical Scaling
- Increase container memory/CPU
- Optimize CadQuery template complexity
- Cache frequently generated cases

---

## 🎯 **Ready for Production**

The 3D Splicer MVP is production-ready with:
- ✅ Docker containerization
- ✅ Health monitoring
- ✅ Circuit.AI integration client
- ✅ CI/CD pipeline
- ✅ Comprehensive error handling
- ✅ Scalable architecture

**Deploy with confidence!** 🚀
