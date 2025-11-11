# Circuit.AI API Reference

## 🔌 API Overview

Circuit.AI provides a comprehensive REST API with WebSocket support for real-time communication. The API is built with FastAPI and follows OpenAPI 3.0 specifications.

### Base URL
```
Development: http://localhost:8000
Production: https://your-domain.com
```

### Authentication
Currently, the API uses API key authentication via environment variables. Set your API keys in the `.env` file:

```bash
COHERE_API_KEY=your_cohere_key
MISTRAL_API_KEY=your_mistral_key
CEREBRAS_API_KEY=your_cerebras_key
```

---

## 📡 WebSocket Endpoints

### WebSocket Connection
**Endpoint**: `ws://localhost:8000/ws/{client_id}`

**Description**: Establishes a WebSocket connection for real-time analysis updates.

**Parameters**:
- `client_id` (string): Unique client identifier

**Example**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/client-123');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Progress:', data);
};
```

**Message Types**:
```json
{
    "type": "progress",
    "analysis_id": "analysis-123",
    "step": "component_detection",
    "progress": 0.75,
    "message": "Detecting components...",
    "timestamp": "2024-08-26T10:30:00Z"
}
```

---

## 🔍 Analysis Endpoints

### Analyze PCB
**Endpoint**: `POST /analyze`

**Description**: Analyzes a single PCB image with real-time progress updates.

**Request**:
```http
POST /analyze
Content-Type: multipart/form-data

{
    "file": <image_file>,
    "backend": "ensemble",
    "enable_ocr": true,
    "enable_quality_assessment": true,
    "enable_caching": true
}
```

**Parameters**:
- `file` (file): PCB image file (PNG, JPG, JPEG)
- `backend` (string, optional): Detection backend ("yolo", "classical", "ensemble")
- `enable_ocr` (boolean, optional): Enable OCR text extraction
- `enable_quality_assessment` (boolean, optional): Enable quality assessment
- `enable_caching` (boolean, optional): Enable result caching

**Response**:
```json
{
    "analysis_id": "analysis-123",
    "status": "completed",
    "result": {
        "components": [
            {
                "id": "comp-1",
                "type": "IC",
                "name": "ATmega328P",
                "confidence": 0.95,
                "bbox": [100, 150, 200, 250],
                "value": 2.50,
                "functionality": "8-bit microcontroller"
            }
        ],
        "total_value": 8.75,
        "educational_value": "high",
        "difficulty_level": "intermediate",
        "processing_time": 2.3
    },
    "websocket_url": "ws://localhost:8000/ws/client-123"
}
```

### Batch Analysis
**Endpoint**: `POST /batch_analyze`

**Description**: Submits multiple PCB images for batch analysis.

**Request**:
```http
POST /batch_analyze
Content-Type: application/json

{
    "image_paths": ["image1.png", "image2.png", "image3.png"],
    "options": {
        "backend": "ensemble",
        "enable_ocr": true,
        "enable_quality_assessment": true,
        "enable_caching": true
    }
}
```

**Response**:
```json
{
    "job_id": "batch-2024-001",
    "status": "submitted",
    "image_count": 3,
    "estimated_duration": 15,
    "websocket_url": "ws://localhost:8000/ws/client-123"
}
```

### Get Batch Job Status
**Endpoint**: `GET /job/{job_id}`

**Description**: Retrieves the status of a batch analysis job.

**Response**:
```json
{
    "job_id": "batch-2024-001",
    "status": "processing",
    "progress": 0.67,
    "completed": 2,
    "total": 3,
    "results": [
        {
            "image": "image1.png",
            "status": "completed",
            "components": [...],
            "value": 8.75
        },
        {
            "image": "image2.png",
            "status": "completed",
            "components": [...],
            "value": 15.20
        },
        {
            "image": "image3.png",
            "status": "processing",
            "progress": 0.45
        }
    ]
}
```

---

## 📊 System Endpoints

### Health Check
**Endpoint**: `GET /health`

**Description**: Returns system health status.

**Response**:
```json
{
    "status": "healthy",
    "timestamp": "2024-08-26T10:30:00Z",
    "version": "2.0.0",
    "uptime": 86400,
    "services": {
        "detector": "online",
        "mapper": "online",
        "cache": "online",
        "queue": "online"
    }
}
```

### System Statistics
**Endpoint**: `GET /statistics`

**Description**: Returns comprehensive system statistics.

**Response**:
```json
{
    "requests_per_minute": 45,
    "average_response_time": 2.3,
    "success_rate": 0.987,
    "cache_hit_rate": 0.873,
    "queue_length": 3,
    "active_websocket_connections": 12,
    "total_analyses": 1234,
    "total_components_detected": 5678
}
```

### Cache Statistics
**Endpoint**: `GET /cache/stats`

**Description**: Returns cache performance statistics.

**Response**:
```json
{
    "hits": 1234,
    "misses": 156,
    "hit_rate": 0.887,
    "total_entries": 89,
    "memory_usage": "45.2 MB",
    "evictions": 12
}
```

### Queue Statistics
**Endpoint**: `GET /queue/stats`

**Description**: Returns queue performance statistics.

**Response**:
```json
{
    "pending_jobs": 3,
    "running_jobs": 1,
    "completed_jobs": 1234,
    "failed_jobs": 5,
    "average_processing_time": 3.2,
    "workers_active": 2
}
```

### WebSocket Statistics
**Endpoint**: `GET /ws/stats`

**Description**: Returns WebSocket connection statistics.

**Response**:
```json
{
    "active_connections": 12,
    "total_connections": 1234,
    "messages_sent": 5678,
    "average_latency": 0.15
}
```

---

## 🗄️ Data Endpoints

### Get Component Database
**Endpoint**: `GET /components`

**Description**: Returns the component database.

**Response**:
```json
{
    "components": [
        {
            "id": "atmega328p",
            "name": "ATmega328P",
            "type": "microcontroller",
            "manufacturer": "Microchip",
            "description": "8-bit AVR microcontroller",
            "specifications": {
                "flash_memory": "32KB",
                "sram": "2KB",
                "eeprom": "1KB",
                "operating_voltage": "5V"
            },
            "typical_value": 2.50,
            "educational_value": "high",
            "difficulty_level": "intermediate"
        }
    ]
}
```

### Get Project Templates
**Endpoint**: `GET /projects`

**Description**: Returns available project templates.

**Response**:
```json
{
    "projects": [
        {
            "id": "led-blink",
            "name": "LED Blink Project",
            "difficulty": "beginner",
            "duration": "1-2 hours",
            "cost": 5.00,
            "components_required": ["atmega328p", "led", "resistor"],
            "description": "Learn basic Arduino programming",
            "instructions": "..."
        }
    ]
}
```

### Get Educational Content
**Endpoint**: `GET /educational`

**Description**: Returns educational content and learning modules.

**Response**:
```json
{
    "modules": [
        {
            "id": "microcontroller-basics",
            "title": "Microcontroller Basics",
            "difficulty": "beginner",
            "duration": "2 hours",
            "content": "...",
            "quiz": [
                {
                    "question": "What voltage does ATmega328P operate at?",
                    "options": ["3.3V", "5V", "12V", "24V"],
                    "correct_answer": 1
                }
            ]
        }
    ]
}
```

### Get Repair Guides
**Endpoint**: `GET /repair`

**Description**: Returns repair and troubleshooting guides.

**Response**:
```json
{
    "guides": [
        {
            "component_id": "atmega328p",
            "title": "ATmega328P Troubleshooting",
            "common_issues": [
                {
                    "issue": "Board not responding",
                    "symptoms": ["No LED activity", "Serial communication fails"],
                    "solutions": [
                        "Check power supply (5V required)",
                        "Verify USB connection",
                        "Install correct drivers"
                    ]
                }
            ]
        }
    ]
}
```

---

## 🛠️ Management Endpoints

### Clear Cache
**Endpoint**: `POST /cache/clear`

**Description**: Clears cache entries.

**Request**:
```http
POST /cache/clear
Content-Type: application/json

{
    "pattern": "analysis_*"
}
```

**Response**:
```json
{
    "deleted_entries": 45,
    "message": "Cache cleared successfully"
}
```

---

## 📝 Error Responses

### Standard Error Format
```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid file format. Supported formats: PNG, JPG, JPEG",
        "details": {
            "field": "file",
            "value": "document.pdf"
        }
    },
    "timestamp": "2024-08-26T10:30:00Z"
}
```

### Common Error Codes
- `VALIDATION_ERROR`: Invalid input parameters
- `FILE_TOO_LARGE`: Uploaded file exceeds size limit
- `UNSUPPORTED_FORMAT`: File format not supported
- `ANALYSIS_FAILED`: Analysis processing failed
- `SERVICE_UNAVAILABLE`: Required service unavailable
- `RATE_LIMIT_EXCEEDED`: Too many requests

---

## 🔧 SDK Examples

### Python Client
```python
import requests
import json

class CircuitAIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def analyze_pcb(self, image_path, options=None):
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = options or {}
            response = requests.post(f"{self.base_url}/analyze", files=files, data=data)
            return response.json()
    
    def get_health(self):
        response = requests.get(f"{self.base_url}/health")
        return response.json()

# Usage
client = CircuitAIClient()
result = client.analyze_pcb("pcb_image.png", {
    "backend": "ensemble",
    "enable_ocr": True
})
```

### JavaScript Client
```javascript
class CircuitAIClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async analyzePCB(file, options = {}) {
        const formData = new FormData();
        formData.append('file', file);
        
        Object.entries(options).forEach(([key, value]) => {
            formData.append(key, value);
        });
        
        const response = await fetch(`${this.baseUrl}/analyze`, {
            method: 'POST',
            body: formData
        });
        
        return response.json();
    }
    
    async getHealth() {
        const response = await fetch(`${this.baseUrl}/health`);
        return response.json();
    }
}

// Usage
const client = new CircuitAIClient();
const result = await client.analyzePCB(fileInput.files[0], {
    backend: 'ensemble',
    enable_ocr: true
});
```

---

## 📚 Related Documentation

- **[Architecture](ARCHITECTURE.md)** - System architecture overview
- **[Frontend Guide](FRONTEND_GUIDE.md)** - Frontend integration guide
- **[Testing](TESTING.md)** - API testing strategies
- **[Performance](PERFORMANCE.md)** - Performance optimization guide

