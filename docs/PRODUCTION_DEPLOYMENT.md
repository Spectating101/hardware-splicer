# Circuit.AI - Production Deployment Guide

**Last Updated**: 2025-11-01
**Version**: 1.0
**Status**: Production Ready (MVP)

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose (v20+)
- 4GB RAM minimum (8GB recommended)
- 10GB disk space
- Linux/macOS/Windows with WSL2

### Deploy in 3 Commands
```bash
# 1. Clone and navigate
cd Circuit-AI

# 2. Set environment variables
cp deploy/env.production.example .env
# Edit .env with your settings

# 3. Launch production stack
docker-compose -f deploy/docker/docker-compose.production.yml up -d
```

**Access**:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Metrics: http://localhost:9090 (Prometheus)
- Dashboard: http://localhost:3001 (Grafana)

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Environment Setup](#environment-setup)
3. [Deployment Methods](#deployment-methods)
4. [Configuration](#configuration)
5. [Monitoring & Observability](#monitoring--observability)
6. [Security](#security)
7. [Scaling](#scaling)
8. [Backup & Recovery](#backup--recovery)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## 🏗️ Architecture Overview

### Production Stack Components

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                │
│                   SSL/TLS Termination                   │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────▼────────┐    ┌────────▼────────┐
│  API Instance 1 │    │  API Instance 2 │
│  (Gunicorn+UV)  │    │  (Gunicorn+UV)  │
└────────┬────────┘    └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────▼────────┐    ┌────────▼────────┐
│  Redis Cache    │    │   SQLite DB     │
│  (In-Memory)    │    │  (Persistent)   │
└─────────────────┘    └─────────────────┘
         │
┌────────▼────────────────────────────┐
│  Monitoring Stack                   │
│  - Prometheus (Metrics)             │
│  - Grafana (Visualization)          │
│  - Loguru (Structured Logging)      │
└─────────────────────────────────────┘
```

### Key Features

✅ **High Availability**: Multiple API workers with health checks
✅ **Performance**: Redis caching + ML model preloading
✅ **Security**: JWT auth, rate limiting, CORS, SSL/TLS
✅ **Observability**: Prometheus metrics + structured logs
✅ **Scalability**: Horizontal scaling with Docker Swarm/K8s ready
✅ **Reliability**: Auto-restart, graceful shutdown, timeout handling

---

## 🔧 Environment Setup

### Production Environment Variables

Create `.env` file in project root:

```bash
# Application
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=info

# Security
JWT_SECRET_KEY=your-super-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Database
DATABASE_URL=sqlite:///./data/circuit_ai.db

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50

# Rate Limiting
RATE_LIMIT_ENABLED=true
MAX_REQUESTS_PER_MINUTE=60
MAX_REQUESTS_PER_HOUR=1000
MAX_UPLOAD_SIZE_MB=10

# CORS
ENABLE_CORS=true
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Features
ENABLE_METRICS=true
ENABLE_OCR=true
ML_MODEL_WARMUP=true

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PASSWORD=change-this-admin-password

# External Services (optional)
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=your-key-here
```

### Security Checklist

Before deploying to production:

- [ ] Change `JWT_SECRET_KEY` to strong random value
- [ ] Set `GRAFANA_PASSWORD` to secure password
- [ ] Configure `CORS_ORIGINS` to your domain(s)
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Set up backup procedures
- [ ] Configure monitoring alerts

---

## 🚢 Deployment Methods

### Method 1: Docker Compose (Recommended for Single Server)

```bash
# Production deployment with all services
docker-compose -f deploy/docker/docker-compose.production.yml up -d

# Check status
docker-compose -f deploy/docker/docker-compose.production.yml ps

# View logs
docker-compose -f deploy/docker/docker-compose.production.yml logs -f

# Stop services
docker-compose -f deploy/docker/docker-compose.production.yml down
```

### Method 2: Docker Swarm (Multi-Node)

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c deploy/docker/docker-compose.production.yml circuit-ai

# Check services
docker service ls

# Scale API
docker service scale circuit-ai_circuit-ai-api=4

# Remove stack
docker stack rm circuit-ai
```

### Method 3: Kubernetes (Enterprise)

```bash
# Apply manifests (create these based on docker-compose)
kubectl apply -f deploy/k8s/

# Check deployment
kubectl get pods -n circuit-ai

# Scale
kubectl scale deployment circuit-ai-api --replicas=4 -n circuit-ai

# Expose service
kubectl expose deployment circuit-ai-api --type=LoadBalancer --port=8000
```

### Method 4: Cloud Platforms

#### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway up
```

#### Render
- Connect GitHub repo at https://render.com
- Use `deploy/render.yaml` for configuration
- Deploy automatically on push

#### Vercel (Frontend only)
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy frontend
cd circuit-ai-frontend
vercel --prod
```

#### AWS EC2 (Manual)
```bash
# SSH to instance
ssh -i your-key.pem ubuntu@your-instance-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone repo and deploy
git clone https://github.com/your-repo/Circuit-AI.git
cd Circuit-AI
docker-compose -f deploy/docker/docker-compose.production.yml up -d
```

---

## ⚙️ Configuration

### Nginx Configuration

Edit `deploy/nginx/nginx.conf`:

```nginx
# SSL Configuration (production)
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Your existing proxy configuration
}
```

### Gunicorn Configuration

API runs with Gunicorn + Uvicorn workers:

```bash
# In Dockerfile.production
CMD ["gunicorn", "src.api.main:app",
     "--worker-class", "uvicorn.workers.UvicornWorker",
     "--workers", "4",              # CPU cores * 2 + 1
     "--bind", "0.0.0.0:8000",
     "--timeout", "120",             # 2 minute timeout
     "--keep-alive", "5",
     "--access-logfile", "-",
     "--error-logfile", "-"]
```

### Worker Count Calculation

**Formula**: `(2 × CPU_CORES) + 1`

| CPU Cores | Workers | RAM (Est) |
|-----------|---------|-----------|
| 1         | 3       | 2GB       |
| 2         | 5       | 4GB       |
| 4         | 9       | 8GB       |
| 8         | 17      | 16GB      |

---

## 📊 Monitoring & Observability

### Prometheus Metrics

Available at `http://localhost:9090`

**Key Metrics**:
- `circuit_ai_requests_total` - Total API requests
- `circuit_ai_analyze_duration_seconds` - Analysis latency
- `circuit_ai_model_load_time_seconds` - Model loading time
- `circuit_ai_cache_hit_ratio` - Cache effectiveness
- `circuit_ai_active_connections` - Current connections

**Example Queries**:
```promql
# Request rate (per second)
rate(circuit_ai_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, circuit_ai_analyze_duration_seconds)

# Error rate
rate(circuit_ai_requests_total{status="error"}[5m])
```

### Grafana Dashboard

Access at `http://localhost:3001`

**Default credentials**:
- Username: `admin`
- Password: Set in `GRAFANA_PASSWORD` env var

**Pre-built Dashboards**:
1. **API Performance** - Latency, throughput, errors
2. **Resource Usage** - CPU, memory, disk
3. **ML Pipeline** - Detection accuracy, processing time
4. **Cache Performance** - Hit rate, evictions

### Structured Logging

Logs are stored in `/app/logs/` with rotation:

```bash
# View live logs
docker-compose logs -f circuit-ai-api

# Check error logs
docker exec circuit-ai-api tail -f logs/errors_*.log

# Search logs
docker exec circuit-ai-api grep "ERROR" logs/circuit_ai_*.log
```

**Log Levels**:
- `DEBUG` - Development troubleshooting
- `INFO` - General operational messages
- `WARNING` - Potential issues
- `ERROR` - Recoverable errors
- `CRITICAL` - System failures

---

## 🔒 Security

### SSL/TLS Setup

#### Let's Encrypt (Free)
```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot certonly --standalone -d api.yourdomain.com

# Copy to nginx
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem deploy/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem deploy/nginx/ssl/key.pem

# Restart nginx
docker-compose restart nginx
```

#### Self-Signed (Development)
```bash
# Generate certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout deploy/nginx/ssl/key.pem \
  -out deploy/nginx/ssl/cert.pem
```

### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### API Key Rotation

```bash
# Generate new JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update .env
JWT_SECRET_KEY=new-secret-key

# Restart services
docker-compose restart
```

### Rate Limiting

Configured in Nginx:
- `/analyze`: 2 requests/second, burst 5
- `/api/*`: 10 requests/second, burst 20
- Global: 60 requests/minute per IP

---

## 📈 Scaling

### Vertical Scaling (Increase Resources)

```bash
# Edit docker-compose.production.yml
services:
  circuit-ai-api:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
```

### Horizontal Scaling (Add Instances)

```bash
# Docker Compose
docker-compose -f deploy/docker/docker-compose.production.yml up -d --scale circuit-ai-api=4

# Docker Swarm
docker service scale circuit-ai_circuit-ai-api=4

# Kubernetes
kubectl scale deployment circuit-ai-api --replicas=4
```

### Database Scaling

**Migrate from SQLite to PostgreSQL**:

```yaml
# docker-compose.production.yml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: circuit_ai
      POSTGRES_USER: circuit_ai
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data

  circuit-ai-api:
    environment:
      - DATABASE_URL=postgresql://circuit_ai:${DB_PASSWORD}@postgres:5432/circuit_ai
```

### Cache Scaling

```bash
# Increase Redis memory
docker-compose -f deploy/docker/docker-compose.production.yml up -d \
  redis --maxmemory 1gb
```

---

## 💾 Backup & Recovery

### Automated Backups

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/circuit-ai"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
docker exec circuit-ai-api cp /app/data/circuit_ai.db /tmp/
docker cp circuit-ai-api:/tmp/circuit_ai.db $BACKUP_DIR/db_$DATE.db

# Backup uploaded images
docker cp circuit-ai-api:/app/data/uploads $BACKUP_DIR/uploads_$DATE/

# Backup models
docker cp circuit-ai-api:/app/models $BACKUP_DIR/models_$DATE/

# Compress and upload to S3 (optional)
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz $BACKUP_DIR/*_$DATE*
aws s3 cp $BACKUP_DIR/backup_$DATE.tar.gz s3://your-bucket/backups/

# Clean old backups (keep 30 days)
find $BACKUP_DIR -mtime +30 -delete
EOF

chmod +x backup.sh

# Add to cron (daily at 2 AM)
echo "0 2 * * * /path/to/backup.sh" | crontab -
```

### Restore from Backup

```bash
# Stop services
docker-compose down

# Restore database
docker cp db_20251101_020000.db circuit-ai-api:/app/data/circuit_ai.db

# Restore data
docker cp uploads_20251101_020000/ circuit-ai-api:/app/data/uploads/

# Restart
docker-compose up -d
```

---

## 🔧 Troubleshooting

### Common Issues

#### API Not Responding
```bash
# Check if container is running
docker ps | grep circuit-ai-api

# Check logs
docker logs circuit-ai-api --tail 100

# Restart service
docker-compose restart circuit-ai-api
```

#### High Memory Usage
```bash
# Check resource usage
docker stats circuit-ai-api

# Reduce workers in .env
WORKERS=2

# Restart
docker-compose restart
```

#### Model Loading Fails
```bash
# Check if model file exists
docker exec circuit-ai-api ls -lh /app/models/

# Download model
docker exec circuit-ai-api python -c "
from ultralytics import YOLO
model = YOLO('yolov8m.pt')
"

# Check permissions
docker exec circuit-ai-api chown -R circuitai:circuitai /app/models
```

#### Database Locked
```bash
# Stop all connections
docker-compose down

# Check for corruption
sqlite3 data/circuit_ai.db "PRAGMA integrity_check;"

# Restore from backup if needed
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Detailed health
curl http://localhost:8000/health | jq .

# Metrics
curl http://localhost:8000/metrics

# Redis
docker exec circuit-ai-redis redis-cli ping
```

### Performance Tuning

```bash
# Enable ML model caching
ML_MODEL_WARMUP=true

# Increase Redis memory
# In docker-compose.production.yml
redis:
  command: redis-server --maxmemory 512mb

# Optimize worker count
WORKERS=9  # For 4-core CPU

# Enable gzip in nginx (already configured)
```

---

## 🔄 Maintenance

### Updates & Upgrades

```bash
# Pull latest code
git pull origin main

# Rebuild containers
docker-compose -f deploy/docker/docker-compose.production.yml build

# Zero-downtime update
docker-compose -f deploy/docker/docker-compose.production.yml up -d --no-deps --build circuit-ai-api

# Rollback if needed
git checkout previous-commit
docker-compose up -d --build
```

### Database Migrations

```bash
# Backup first!
./backup.sh

# Run migrations (if using Alembic)
docker exec circuit-ai-api alembic upgrade head

# Or manual SQL
docker exec circuit-ai-api sqlite3 /app/data/circuit_ai.db < migration.sql
```

### Log Rotation

Logs auto-rotate at 100MB. Manual rotation:

```bash
# Compress old logs
docker exec circuit-ai-api gzip /app/logs/*.log.1

# Clear logs
docker exec circuit-ai-api truncate -s 0 /app/logs/circuit_ai.log
```

---

## 📝 Runbook

### Daily Checks
- [ ] Check health endpoint: `curl http://localhost:8000/health`
- [ ] Review error logs: `docker logs circuit-ai-api | grep ERROR`
- [ ] Check disk space: `df -h`

### Weekly Checks
- [ ] Review Grafana dashboards
- [ ] Check backup integrity
- [ ] Update dependencies: `pip list --outdated`
- [ ] Review rate limiting stats

### Monthly Checks
- [ ] Security updates: `apt-get update && apt-get upgrade`
- [ ] SSL certificate renewal
- [ ] Performance optimization review
- [ ] Capacity planning

---

## 🆘 Support

**Issues**: https://github.com/your-repo/issues
**Documentation**: `docs/`
**Community**: Join our Discord

---

**Production Ready Checklist**:
- [x] Docker production setup
- [x] SSL/TLS configuration
- [x] Monitoring & alerts
- [x] Backup procedures
- [x] Error handling
- [x] Rate limiting
- [x] Health checks
- [x] Logging
- [x] Security hardening
- [x] Documentation

**Status**: ✅ Ready for Production Deployment
