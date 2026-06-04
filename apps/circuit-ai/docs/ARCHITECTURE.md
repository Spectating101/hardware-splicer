# Circuit.AI Architecture Documentation

## 🏗️ System Architecture Overview

Circuit.AI is built as a modern, scalable, microservices-oriented platform with real-time capabilities and AI-powered analysis.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    🌐 CLIENT LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  Next.js 14 Frontend (React + TypeScript + Tailwind CSS)       │
│  • Real-time WebSocket connections                             │
│  • Interactive UI components                                   │
│  • Responsive design                                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    🔌 API GATEWAY                              │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Backend (Python 3.8+)                                │
│  • RESTful API endpoints                                       │
│  • WebSocket connections                                       │
│  • CORS middleware                                             │
│  • Authentication & authorization                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    🧠 CORE SERVICES                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ Enhanced    │ │ Enhanced    │ │ Enhanced    │              │
│  │ Detector    │ │ Mapper      │ │ Analyzer    │              │
│  │ (YOLO+CV)   │ │ (LLM)       │ │ (Orchestr.) │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    💾 INFRASTRUCTURE                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ Cache       │ │ Queue       │ │ Database    │              │
│  │ Service     │ │ Service     │ │ (SQLite)    │              │
│  │ (Redis)     │ │ (Redis)     │ │             │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 Core Components

### 1. Enhanced Detector (`src/vision/enhanced_detector.py`)

**Purpose**: Multi-model component detection with quality assessment

**Features**:
- **YOLO Detection**: Deep learning-based component identification
- **Classical CV**: Traditional computer vision techniques
- **OCR Integration**: Text extraction from PCBs
- **Quality Assessment**: Confidence scoring for detections
- **Ensemble Methods**: Combines multiple detection approaches

**Key Classes**:
```python
class EnhancedComponentDetector:
    - detect_components(image, method)
    - _detect_with_yolo(image)
    - _detect_with_classical_cv(image)
    - _perform_ocr(image)
    - assess_detection_quality(detections)
```

### 2. Enhanced Mapper (`src/llm/enhanced_mapper.py`)

**Purpose**: LLM-powered functional analysis and recommendations

**Features**:
- **Multi-LLM Integration**: Cohere, Mistral, Cerebras via LiteLLM
- **Component Database**: Comprehensive metadata lookup
- **Educational Content**: Interactive learning modules
- **Project Recommendations**: Personalized suggestions
- **Repair Guides**: Troubleshooting assistance

**Key Classes**:
```python
class EnhancedFunctionalMapper:
    - map_detections_to_functionality(detections)
    - generate_project_recommendations(components)
    - create_educational_content(component)
    - generate_repair_guide(component)
```

### 3. Enhanced Analyzer (`src/core/enhanced_analyzer.py`)

**Purpose**: Central orchestration and analysis pipeline

**Features**:
- **Real-time Processing**: Live progress updates
- **Batch Analysis**: Multiple PCB processing
- **Caching Integration**: Performance optimization
- **Result Compilation**: Comprehensive analysis reports
- **System Monitoring**: Health checks and metrics

**Key Classes**:
```python
class EnhancedCircuitAnalyzer:
    - analyze_pcb(image, options)
    - batch_analyze(images, options)
    - get_system_health()
    - get_performance_metrics()
```

## 🌐 Service Layer

### 1. WebSocket Service (`src/services/websocket_service.py`)

**Purpose**: Real-time communication for analysis progress

**Features**:
- **Connection Management**: Active client tracking
- **Progress Broadcasting**: Live updates to clients
- **Analysis Subscriptions**: Client-specific updates
- **Error Handling**: Graceful connection management

**Key Classes**:
```python
class WebSocketManager:
    - connect(websocket, client_id)
    - disconnect(client_id)
    - send_personal_message(message, client_id)
    - broadcast(message)
    - subscribe_to_analysis(client_id, analysis_id)
```

### 2. Cache Service (`src/services/cache_service.py`)

**Purpose**: Multi-level caching for performance optimization

**Features**:
- **Redis Integration**: Persistent caching
- **Memory Fallback**: In-memory caching when Redis unavailable
- **TTL Management**: Automatic expiration
- **Statistics Tracking**: Cache hit/miss metrics
- **Decorator Support**: Easy function caching

**Key Classes**:
```python
class CacheService:
    - get(key)
    - set(key, value, ttl)
    - delete(key)
    - exists(key)
    - get_stats()
    - clear(pattern)
```

### 3. Queue Service (`src/services/queue_service.py`)

**Purpose**: Background job processing and management

**Features**:
- **Job Prioritization**: Priority-based processing
- **Retry Mechanisms**: Automatic failure recovery
- **Worker Pool**: Concurrent job processing
- **Status Tracking**: Job state management
- **Statistics**: Queue performance metrics

**Key Classes**:
```python
class QueueService:
    - submit_job(task_name, data, priority)
    - get_job(job_id)
    - cancel_job(job_id)
    - get_queue_stats()
    - register_task_handler(task_name, handler)
```

## 📊 Data Flow

### 1. Single Analysis Flow

```
1. User Upload → Frontend
   ↓
2. File Validation → Frontend
   ↓
3. API Request → FastAPI
   ↓
4. WebSocket Connection → WebSocket Manager
   ↓
5. Analysis Job → Queue Service
   ↓
6. Component Detection → Enhanced Detector
   ↓
7. Functional Mapping → Enhanced Mapper
   ↓
8. Result Compilation → Enhanced Analyzer
   ↓
9. Cache Storage → Cache Service
   ↓
10. WebSocket Broadcast → Frontend
    ↓
11. UI Update → User
```

### 2. Batch Analysis Flow

```
1. Multiple Files → Frontend
   ↓
2. Batch Job Creation → Queue Service
   ↓
3. Worker Processing → Multiple Analysis Jobs
   ↓
4. Parallel Detection → Enhanced Detector Pool
   ↓
5. Concurrent Mapping → Enhanced Mapper Pool
   ↓
6. Result Aggregation → Enhanced Analyzer
   ↓
7. Progress Updates → WebSocket Broadcast
   ↓
8. Final Results → Frontend
```

## 🔒 Security Architecture

### 1. Authentication & Authorization
- **API Key Management**: Environment-based configuration
- **CORS Configuration**: Cross-origin request handling
- **Input Validation**: Pydantic model validation
- **Rate Limiting**: Request throttling

### 2. Data Protection
- **File Upload Security**: Type and size validation
- **Temporary Storage**: Secure file handling
- **Cache Security**: Sensitive data protection
- **Database Security**: SQL injection prevention

## 📈 Scalability Considerations

### 1. Horizontal Scaling
- **Stateless Services**: Easy replication
- **Load Balancing**: Multiple service instances
- **Database Scaling**: Read replicas and sharding
- **Cache Distribution**: Redis cluster support

### 2. Performance Optimization
- **Async Processing**: Non-blocking operations
- **Connection Pooling**: Database and Redis pools
- **Compression**: Response size optimization
- **CDN Integration**: Static asset delivery

## 🚀 Deployment Architecture

### 1. Container Strategy
```
┌─────────────────────────────────────────────────────────────────┐
│                    🐳 DOCKER CONTAINERS                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ Frontend    │ │ Backend     │ │ Redis       │              │
│  │ Container   │ │ Container   │ │ Container   │              │
│  │ (Next.js)   │ │ (FastAPI)   │ │ (Cache)     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Cloud Deployment
- **Railway**: Easy deployment with auto-scaling
- **Render**: Managed platform with health checks
- **Vercel**: Frontend optimization and CDN
- **Heroku**: Traditional hosting with add-ons

## 🔍 Monitoring & Observability

### 1. Health Checks
- **Service Health**: Individual service monitoring
- **Dependency Health**: Database and Redis status
- **Performance Metrics**: Response times and throughput
- **Error Tracking**: Exception monitoring

### 2. Logging Strategy
- **Structured Logging**: JSON-formatted logs
- **Log Levels**: Debug, Info, Warning, Error
- **Log Aggregation**: Centralized log management
- **Performance Logging**: Request/response timing

## 🔄 Configuration Management

### 1. Environment Configuration
```python
class EnhancedSettings(BaseSettings):
    # Application settings
    app_name: str = "Circuit.AI Enhanced"
    app_version: str = "2.0.0"
    debug: bool = Field(False, env="DEBUG")
    
    # Service configurations
    redis_url: Optional[str] = Field(None, env="REDIS_URL")
    database_url: str = Field("sqlite:///./circuit_ai.db", env="DATABASE_URL")
    
    # AI model configurations
    yolo_model_path: str = Field("models/yolov8n.pt", env="YOLO_MODEL_PATH")
    llm_provider: str = Field("cohere", env="LLM_PROVIDER")
```

### 2. Feature Flags
- **AI Features**: Enable/disable specific AI capabilities
- **Service Toggles**: Activate/deactivate services
- **Performance Modes**: Optimize for speed vs accuracy
- **Debug Modes**: Development vs production settings

---

## 📚 Related Documentation

- **[API Reference](API_REFERENCE.md)** - Complete API documentation
- **[Frontend Guide](FRONTEND_GUIDE.md)** - UI/UX architecture
- **[AI Models](AI_MODELS.md)** - Machine learning model details
- **[Performance](PERFORMANCE.md)** - Performance optimization guide
- **[Testing](TESTING.md)** - Testing strategy and implementation
