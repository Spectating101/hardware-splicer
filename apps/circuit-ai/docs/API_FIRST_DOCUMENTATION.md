# Circuit.AI - Enterprise PCB Analysis API Platform

> Status note: this document reflects the API-first FastAPI branch direction, not the canonical shipped backend. The current product backend is the Flask server in `api_server.py` exposed by `circuit-ai-api`; use the README and v2 guides for the default contract.
>
> Canonical product/use-case map: [VALUE_AND_WORKFLOWS.md](VALUE_AND_WORKFLOWS.md)

## Executive Summary

Circuit.AI is an enterprise-grade API platform for PCB (Printed Circuit Board) analysis, built for developers and teams. This document describes the API-first product direction and secondary FastAPI-oriented platform surface, including AI-powered component detection, value assessment, and educational insights.

## Platform Overview

### Core Value Proposition
- **API-First Architecture**: Built for developers, integrated by teams
- **Enterprise-Grade**: Production-ready with 99.9% SLA, rate limiting, and monitoring
- **AI-Powered Analysis**: Advanced computer vision and machine learning for component detection
- **Developer Experience**: Clean APIs, comprehensive SDKs, and detailed documentation
- **Scalable Infrastructure**: Handles high-volume requests with Redis caching and job queues

### Key Features
- **Component Detection**: AI-powered identification with 95%+ accuracy
- **Value Assessment**: Real-time market value calculation
- **Educational Content**: Curated learning materials and project recommendations
- **Batch Processing**: Efficient bulk analysis capabilities
- **Real-time Streaming**: WebSocket support for live updates
- **Multi-language SDKs**: Native Python and JavaScript SDKs

## API Architecture

### REST API v1
```
https://api.circuit-ai.com/v1/
├── /analyze              # PCB analysis endpoint
├── /analyze/batch        # Batch analysis
├── /components           # Component information
├── /projects             # Project templates
├── /educational/{id}     # Educational content
├── /analyses             # Analysis history
├── /analyses/{id}        # Specific analysis
├── /usage                # Usage statistics
└── /health               # Health check
```

### Authentication
- **API Key**: Bearer token authentication
- **Rate Limiting**: Tier-based limits (Free/Pro/Enterprise)
- **Usage Tracking**: Comprehensive analytics and monitoring

### Response Format
```json
{
  "success": true,
  "analysis_id": "anal_123456789",
  "components": [
    {
      "type": "ic_chip",
      "name": "Arduino Uno R3",
      "confidence": 0.95,
      "value": 25.00,
      "function": "Main processing unit",
      "bbox": [100, 150, 200, 250],
      "center": {"x": 150, "y": 200},
      "specifications": {
        "voltage": "5V",
        "current": "20mA",
        "pins": 14
      }
    }
  ],
  "total_value": 25.00,
  "analysis_time": 2.3,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## SDKs and Integrations

### Python SDK
```python
import circuitai

client = circuitai.Client(api_key="your-api-key")

# Analyze a PCB image
result = client.analyze_pcb("pcb_image.jpg")

print(f"Found {len(result.components)} components")
for component in result.components:
    print(f"- {component.name}: ${component.value}")
```

### JavaScript SDK
```javascript
import CircuitAI from 'circuit-ai-sdk';

const client = new CircuitAI({ apiKey: 'your-api-key' });

// Analyze a PCB image
const result = await client.analyzePCB('pcb_image.jpg');

console.log(`Found ${result.components.length} components`);
result.components.forEach(component => {
  console.log(`- ${component.name}: $${component.value}`);
});
```

## Rate Limits and Pricing

### Free Tier
- 50 requests/month
- Basic component detection
- Community support
- No SLA guarantee

### Pro Tier
- $0.10 per request
- Advanced AI detection
- Real-time WebSocket streaming
- 99.9% SLA guarantee
- Priority support

### Enterprise Tier
- Custom volume pricing
- Dedicated infrastructure
- Custom model training
- On-premise deployment
- 24/7 dedicated support

## Technical Architecture

### Backend Services
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │   Core Services │    │   AI/ML Engine  │
│                 │    │                 │    │                 │
│ • Authentication│    │ • Analysis      │    │ • YOLOv8        │
│ • Rate Limiting │    │ • Components    │    │ • OpenCV        │
│ • Monitoring    │    │ • Projects      │    │ • LiteLLM       │
│ • Load Balancing│    │ • Educational   │    │ • Multi-model   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow
1. **Request**: Client sends PCB image via API
2. **Authentication**: API key validation and rate limit check
3. **Processing**: AI pipeline analyzes image for components
4. **Enrichment**: Component data enriched with specifications and values
5. **Response**: Structured JSON response with analysis results

### Infrastructure
- **FastAPI**: High-performance Python web framework
- **Redis**: Caching and session management
- **PostgreSQL**: Primary data storage
- **Docker**: Containerized deployment
- **Prometheus**: Metrics and monitoring
- **WebSocket**: Real-time communication

## Developer Console

### API Documentation
- **Interactive Docs**: Swagger/OpenAPI interface
- **Code Examples**: cURL, Python, JavaScript samples
- **SDK Documentation**: Comprehensive guides and tutorials

### Playground
- **Live Testing**: Upload images and test API endpoints
- **Code Generation**: Automatic SDK code generation
- **Response Preview**: Real-time response visualization

### Monitoring
- **Usage Analytics**: Request counts, success rates, latency
- **Rate Limit Status**: Current usage and remaining quota
- **Error Tracking**: Detailed error logs and debugging info

## Use Cases

### Educational Technology
- **E-learning Platforms**: Integrate PCB analysis into electronics courses
- **Maker Spaces**: Help students identify and reuse components
- **Universities**: Research and educational project development

### Electronics Industry
- **Component Suppliers**: Automated inventory management
- **Manufacturing**: Quality control and component verification
- **Repair Services**: Component identification and sourcing

### E-waste Management
- **Recycling Centers**: Automated component extraction and valuation
- **Sustainability**: Educational programs for component reuse
- **Circular Economy**: Component lifecycle tracking

## Getting Started

### 1. Get API Key
```bash
# Sign up at https://circuit-ai.com
# Get your API key from the dashboard
```

### 2. Install SDK
```bash
# Python
pip install circuit-ai

# JavaScript
npm install circuit-ai-sdk
```

### 3. Make First Request
```python
import circuitai

client = circuitai.Client(api_key="your-api-key")
result = client.analyze_pcb("sample_pcb.jpg")
print(f"Analysis complete: {len(result.components)} components found")
```

## Support and Resources

### Documentation
- **API Reference**: https://docs.circuit-ai.com
- **SDK Guides**: Python and JavaScript tutorials
- **Code Examples**: GitHub repository with samples

### Community
- **GitHub**: https://github.com/circuit-ai
- **Discord**: Developer community and support
- **Stack Overflow**: Tagged questions and answers

### Enterprise Support
- **Email**: enterprise@circuit-ai.com
- **Slack**: Dedicated enterprise channel
- **Phone**: 24/7 support for enterprise customers

## Roadmap

### Q1 2024
- ✅ API v1.0 release
- ✅ Python and JavaScript SDKs
- ✅ Developer console and playground

### Q2 2024
- 🔄 Go and Rust SDKs
- 🔄 Advanced analytics dashboard
- 🔄 Custom model training API

### Q3 2024
- 📋 Mobile SDKs (iOS/Android)
- 📋 GraphQL API
- 📋 Webhook support

### Q4 2024
- 📋 On-premise deployment
- 📋 White-label solutions
- 📋 Advanced security features

---

**Circuit.AI** - Enterprise PCB Analysis API Platform  
Built for developers, integrated by teams.

For more information, visit [https://circuit-ai.com](https://circuit-ai.com)
