# 🚨 3D Splicer v0.1 Production Runbook

## 🚀 **Quick Start Commands**

```bash
# Start production server
docker run -d --name 3d-splicer-prod -p 8000:8000 3d-splicer-v01

# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/geom
curl http://localhost:8000/health/evaluator

# Metrics
curl http://localhost:8000/metrics
curl http://localhost:8000/metrics/summary
```

## 🔍 **Common Issues & Solutions**

### **Issue: Optimization Fails with Low Satisfaction (< 50%)**

**Symptoms:**
- `satisfaction_score < 0.5`
- Multiple iterations with no improvement
- Test failures in logs

**Likely Causes:**
1. **Contradictory spec**: Tight envelope + thick walls + thermal requirements
2. **Unrealistic constraints**: Overhang angle < 45°, wall thickness > 5mm
3. **Material mismatch**: PLA for high-impact applications

**Solutions:**
```bash
# Check spec validation
curl -X POST http://localhost:8000/v1/plan \
  -H "Content-Type: application/json" \
  --data @problematic_spec.json

# Look for validation errors in response
# Common fixes:
# - Increase envelope size by 20%
# - Relax overhang constraint to 55°
# - Use ABS for drop protection
```

### **Issue: Non-Manifold STL Generation**

**Symptoms:**
- `"mesh is not manifold"` in logs
- STL files fail validation
- 3D printer software rejects files

**Likely Causes:**
1. **Overlapping geometry**: Bosses intersecting with shell
2. **Invalid fillets**: Negative or excessive fillet radii
3. **Template issues**: CadQuery script errors

**Solutions:**
```bash
# Check printability evaluator
curl http://localhost:8000/health/evaluator

# Review parameter clamps
# - shell.inner_fillet_mm: 0.0-5.0
# - shell.outer_fillet_mm: 0.0-5.0
# - bosses: ensure no overlap with shell

# Template debugging
# Check functional_case_simple.cq.j2 for syntax errors
```

### **Issue: Keepout Collision Errors**

**Symptoms:**
- `"Keepout collision detected"` in logs
- Geometric evaluation failures
- Case interferes with board components

**Likely Causes:**
1. **Keepout positioning**: Too close to board edges
2. **Shell thickness**: Exceeds keepout margins
3. **Boss placement**: Intersects with keepout regions

**Solutions:**
```bash
# Validate keepout positions
# - Minimum 3mm clearance from board edges
# - Check keepout dimensions vs shell thickness
# - Adjust boss positions to avoid keepouts

# Quick fix: Increase shell.inner_fillet_mm to create clearance
```

### **Issue: High Memory Usage (> 200MB)**

**Symptoms:**
- `docker stats` shows high memory
- Slow response times
- Out of memory errors

**Likely Causes:**
1. **Large STL files**: Complex geometry with many triangles
2. **Cache accumulation**: Too many cached evaluations
3. **Memory leaks**: Unclosed file handles

**Solutions:**
```bash
# Monitor memory usage
docker stats 3d-splicer-prod

# Restart container if needed
docker restart 3d-splicer-prod

# Check artifact sizes
ls -la artifacts/*/final/

# Clear old artifacts (if needed)
find artifacts/ -name "*.stl" -mtime +7 -delete
```

### **Issue: Slow Optimization (> 60 seconds)**

**Symptoms:**
- `p99 iterate > 15s` in metrics
- Timeout errors
- User complaints about slow response

**Likely Causes:**
1. **Complex geometry**: Many keepouts, mounts, IO connectors
2. **High iteration count**: Max iterations reached
3. **Evaluator bottlenecks**: Slow mesh analysis

**Solutions:**
```bash
# Check metrics
curl http://localhost:8000/metrics/summary

# Reduce iteration budget for simple cases
"iteration_budget": {"max_iters": 3, "max_seconds": 60}

# Simplify spec
# - Reduce number of keepouts
# - Use simpler IO configurations
# - Increase envelope margins
```

### **Issue: Determinism Failures**

**Symptoms:**
- Same spec produces different results
- Hash mismatches in golden specs test
- Inconsistent satisfaction scores

**Likely Causes:**
1. **Random seed issues**: Non-deterministic random number generation
2. **Floating point precision**: Different calculation paths
3. **Template variations**: Dynamic content in CadQuery scripts

**Solutions:**
```bash
# Run determinism test
python test_golden_specs.py

# Check for non-deterministic code
# - Ensure all random operations use fixed seed
# - Verify template consistency
# - Check for time-based variations

# Fix: Set explicit seed in HeuristicPlanner
planner = HeuristicPlanner(seed=42)
```

## 📊 **Monitoring & Alerts**

### **Key Metrics to Watch**

```bash
# Availability
curl http://localhost:8000/health | jq '.ok'

# Performance
curl http://localhost:8000/metrics | grep splicer_optimization_duration_seconds

# Success rate
curl http://localhost:8000/metrics | grep splicer_optimization_requests_total

# Cache efficiency
curl http://localhost:8000/metrics/summary | jq '.cache_hit_rate'
```

### **Alert Thresholds**

| Metric | Warning | Critical | Action |
|--------|---------|----------|---------|
| Pass rate | < 90% | < 80% | Check specs, review logs |
| p99 iterate | > 12s | > 15s | Reduce complexity, check performance |
| Non-manifold rate | > 5% | > 10% | Review parameter clamps |
| Memory usage | > 150MB | > 200MB | Restart container |
| Cache hit rate | < 70% | < 50% | Check cache configuration |

### **Log Analysis**

```bash
# Check recent errors
docker logs 3d-splicer-prod --tail 100 | grep ERROR

# Monitor optimization patterns
docker logs 3d-splicer-prod | grep "Optimization complete"

# Track satisfaction scores
docker logs 3d-splicer-prod | grep "satisfaction"
```

## 🔧 **Emergency Procedures**

### **Service Recovery**

```bash
# Quick restart
docker restart 3d-splicer-prod

# Full restart with cleanup
docker stop 3d-splicer-prod
docker rm 3d-splicer-prod
docker run -d --name 3d-splicer-prod -p 8000:8000 3d-splicer-v01

# Verify recovery
curl http://localhost:8000/health
```

### **Data Recovery**

```bash
# Backup artifacts
tar -czf artifacts_backup_$(date +%Y%m%d).tar.gz artifacts/

# Restore from backup
tar -xzf artifacts_backup_20240101.tar.gz
```

### **Performance Tuning**

```bash
# Increase timeout for complex cases
export ITER_TIMEOUT_S=60
export JOB_TIMEOUT_S=300

# Reduce iteration budget for simple cases
export MAX_ITERS=3

# Enable caching
export ENABLE_METRICS=true
```

## 🚨 **Escalation Procedures**

### **Level 1: Service Issues**
- **Symptoms**: Health checks failing, high error rates
- **Action**: Restart container, check logs
- **Escalate if**: Multiple restarts needed, persistent errors

### **Level 2: Performance Issues**
- **Symptoms**: Slow response times, high memory usage
- **Action**: Check metrics, tune parameters, review specs
- **Escalate if**: Performance degradation > 50%

### **Level 3: Data Issues**
- **Symptoms**: Determinism failures, incorrect results
- **Action**: Run golden specs test, check parameter clamps
- **Escalate if**: Core functionality compromised

### **Level 4: Security Issues**
- **Symptoms**: Unauthorized access, suspicious requests
- **Action**: Check access logs, review security config
- **Escalate immediately**: Security incidents

## 📞 **Contact Information**

- **On-call Engineer**: [Your contact]
- **Circuit.AI Integration**: [Circuit.AI contact]
- **Escalation**: [Manager contact]

## 🔄 **Maintenance Schedule**

### **Daily**
- Check health endpoints
- Review error logs
- Monitor satisfaction scores

### **Weekly**
- Run golden specs test
- Review performance metrics
- Clean up old artifacts

### **Monthly**
- Update dependencies
- Review security patches
- Performance optimization review

---

## 🎯 **Success Criteria**

**v0.1 is healthy when:**
- ✅ Health checks return `{"ok": true}`
- ✅ Pass rate ≥ 90% for golden specs
- ✅ p99 iterate ≤ 12 seconds
- ✅ Memory usage < 150MB
- ✅ Cache hit rate ≥ 70%
- ✅ Determinism tests pass

**If any criteria fail, follow the troubleshooting procedures above.**
