# 🚨 3D Splicer v0.1 - One-Page Ops Runbook

## **Alert → Cause → Fix**

| Alert | Likely Cause | Exact Command to Triage |
|-------|--------------|-------------------------|
| **Pass rate < 80%** | Contradictory specs, tight envelopes | `curl http://localhost:8000/metrics/summary \| jq '.pass_rate'` |
| **p99 iterate > 15s** | Complex geometry, high iteration count | `docker logs splicer \| grep "Optimization complete" \| tail -10` |
| **Non-manifold > 10%** | Parameter clamp issues, template errors | `curl http://localhost:8000/health/evaluator \| jq '.expected_margins'` |
| **Memory > 200MB** | Large STL files, cache accumulation | `docker stats splicer --no-stream` |
| **Health check failing** | CadQuery/OCP issues, template problems | `docker logs splicer \| grep ERROR \| tail -20` |

## **Quick Fixes**

```bash
# Restart service
docker restart splicer

# Check logs
docker logs splicer --tail 50

# Monitor performance
watch "curl -s http://localhost:8000/metrics/summary | jq"

# Test golden specs
python test_golden_specs.py

# Clear old artifacts
find artifacts/ -name "*.stl" -mtime +7 -delete
```

## **Emergency Contacts**
- **On-call**: [Your contact]
- **Circuit.AI**: [Integration contact]
- **Escalation**: [Manager contact]

---
*Updated: $(date)*
