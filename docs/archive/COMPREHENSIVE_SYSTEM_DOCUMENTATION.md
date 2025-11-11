# Circuit.AI - Comprehensive System Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Frontend System](#frontend-system)
5. [Backend Services](#backend-services)
6. [AI/ML Pipeline](#aiml-pipeline)
7. [Data Management](#data-management)
8. [Deployment](#deployment)
9. [API Reference](#api-reference)
10. [Configuration](#configuration)
11. [Development Guide](#development-guide)

## System Overview

Circuit.AI is an advanced PCB (Printed Circuit Board) analysis platform that combines computer vision, machine learning, and educational technology to transform electronic waste into learning opportunities. The system provides:

- **Component Detection**: AI-powered identification of electronic components
- **Functional Analysis**: Understanding component capabilities and specifications
- **Educational Content**: Project recommendations and learning materials
- **Value Assessment**: Market value calculation for salvaged components
- **Real-time Processing**: WebSocket-based live analysis updates

### Key Features
- Multi-model ensemble detection (YOLOv8 + classical CV)
- LLM-powered functional mapping and recommendations
- Real-time WebSocket communication
- Advanced caching and job queue systems
- Professional Next.js frontend with modern UI
- Comprehensive API with FastAPI backend
- Multi-platform deployment support

## Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   AI/ML         │
│   (Next.js)     │◄──►│   (FastAPI)     │◄──►│   Pipeline      │
│                 │    │                 │    │                 │
│ • React 18      │    │ • REST API      │    │ • YOLOv8        │
│ • TypeScript    │    │ • WebSockets    │    │ • OpenCV        │
│ • Tailwind CSS  │    │ • Redis Cache   │    │ • LiteLLM       │
│ • Shadcn/ui     │    │ • Job Queue     │    │ • Multi-model   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Technology Stack
- **Frontend**: Next.js 15, React 18, TypeScript, Tailwind CSS, Shadcn/ui
- **Backend**: FastAPI, Uvicorn, Python 3.11+
- **AI/ML**: YOLOv8, OpenCV, LiteLLM, Cohere/Mistral/Cerebras
- **Database**: SQLite (development), PostgreSQL (production)
- **Cache/Queue**: Redis
- **Deployment**: Docker, Railway, Render, Vercel, Heroku

## Core Components

### 1. Vision System (`src/vision/`)
- **`detector.py`**: YOLOv8-based component detection
- **`enhanced_detector.py`**: Multi-model ensemble detection
- **`classical_cv.py`**: OpenCV-based classical computer vision
- **`ocr.py`**: Optical Character Recognition for component text

### 2. LLM Integration (`src/llm/`)
- **`llm_integration.py`**: LiteLLM provider management
- **`mapper.py`**: Functional analysis and mapping
- **`enhanced_mapper.py`**: Advanced LLM-powered analysis
- **`content_generator.py`**: Educational content generation

### 3. Core Analysis (`src/core/`)
- **`analyzer.py`**: Main analysis orchestrator
- **`enhanced_analyzer.py`**: Advanced analysis pipeline
- **`ingest.py`**: Data ingestion and preprocessing
- **`database.py`**: Database operations and schema

### 4. API Layer (`src/api/`)
- **`main.py`**: FastAPI application entry point
- **`enhanced_api.py`**: Advanced API with WebSocket support
- **`routes/`**: Modular route definitions

### 5. Services (`src/services/`)
- **`websocket_service.py`**: Real-time communication
- **`cache_service.py`**: Advanced caching with Redis
- **`queue_service.py`**: Background job processing
- **`file_service.py`**: File upload and management

## Frontend System

### Next.js Application Structure
```
circuit-ai-frontend/
├── app/                    # App Router pages
│   ├── page.tsx           # Landing page
│   ├── analyze/           # Analysis interface
│   ├── components/        # Component library
│   ├── projects/          # Project recommendations
│   └── dashboard/         # User dashboard
├── components/            # Reusable components
│   ├── ui/               # Shadcn/ui components
│   ├── navbar.tsx        # Navigation
│   └── analytics-dashboard.tsx
├── lib/                  # Utilities and API clients
│   ├── utils.ts          # Tailwind utilities
│   └── enhanced-api.ts   # Backend API client
├── hooks/                # Custom React hooks
│   └── useEnhancedAnalysis.ts
└── public/               # Static assets
```

### Key Frontend Features
- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **Real-time Updates**: WebSocket integration for live analysis
- **Drag & Drop**: File upload with progress tracking
- **Component Library**: Interactive component database
- **Analytics Dashboard**: Usage statistics and metrics
- **Modern UI**: Professional design with Shadcn/ui components

### UI Components
- **Button**: Multiple variants including gradient styles
- **Card**: Information display containers
- **Input**: Form inputs with validation
- **Progress**: Analysis progress indicators
- **Navigation**: Responsive navbar with mobile menu

## Backend Services

### FastAPI Application
- **RESTful API**: Standard HTTP endpoints
- **WebSocket Support**: Real-time communication
- **Automatic Documentation**: OpenAPI/Swagger UI
- **CORS Configuration**: Cross-origin resource sharing
- **Rate Limiting**: API protection and throttling

### Core Endpoints
- `POST /analyze`: Upload and analyze PCB images
- `GET /components`: Retrieve component database
- `GET /projects`: Get project recommendations
- `WebSocket /ws`: Real-time analysis updates
- `GET /health`: System health check

### Service Architecture
- **WebSocket Service**: Manages real-time connections
- **Cache Service**: Redis-based caching with fallback
- **Queue Service**: Background job processing
- **File Service**: Secure file upload and storage

## AI/ML Pipeline

### Computer Vision Pipeline
1. **Image Preprocessing**: Resize, normalize, enhance
2. **Component Detection**: YOLOv8 + classical CV ensemble
3. **OCR Processing**: Text extraction from components
4. **Quality Assessment**: Component condition evaluation
5. **3D Visualization**: Component positioning and layout

### LLM Integration
- **Provider Support**: Cohere, Mistral, Cerebras via LiteLLM
- **Functional Analysis**: Component capability understanding
- **Content Generation**: Educational materials and guides
- **Project Recommendations**: Personalized learning paths
- **Repair Guidance**: Troubleshooting and repair instructions

### Multi-Model Ensemble
- **Primary Model**: YOLOv8 for component detection
- **Secondary Model**: Classical CV for edge cases
- **Confidence Scoring**: Weighted decision making
- **Fallback Mechanisms**: Graceful degradation

## Data Management

### Database Schema
- **Components**: Component specifications and metadata
- **Analyses**: Analysis results and history
- **Projects**: Educational project recommendations
- **Users**: User profiles and preferences
- **Sessions**: Analysis sessions and progress

### Caching Strategy
- **Redis Cache**: High-performance data caching
- **In-Memory Fallback**: Local caching when Redis unavailable
- **Cache Invalidation**: Smart cache management
- **Performance Metrics**: Cache hit/miss tracking

### File Management
- **Secure Upload**: Validated file uploads
- **Image Processing**: Optimized image handling
- **Storage Management**: Efficient file organization
- **Cleanup Policies**: Automatic file cleanup

## Deployment

### Multi-Platform Support
- **Railway**: Primary deployment platform
- **Render**: Alternative cloud platform
- **Vercel**: Frontend deployment
- **Heroku**: Legacy support
- **Docker**: Containerized deployment

### Configuration Files
- `Dockerfile`: Container configuration
- `docker-compose.yml`: Multi-service orchestration
- `deploy/railway.json`: Railway deployment config
- `deploy/render.yaml`: Render deployment config
- `deploy/vercel.json`: Vercel deployment config

### Environment Variables
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `LLM_API_KEY`: LLM provider API key
- `SECRET_KEY`: Application secret key
- `ENVIRONMENT`: Deployment environment

## API Reference

### REST Endpoints

#### Analysis
```http
POST /analyze
Content-Type: multipart/form-data

{
  "image": <file>,
  "options": {
    "include_ocr": true,
    "include_3d": false,
    "analysis_type": "comprehensive"
  }
}
```

#### Components
```http
GET /components?category=resistor&limit=50
GET /components/{component_id}
```

#### Projects
```http
GET /projects?difficulty=beginner&category=arduino
GET /projects/{project_id}
```

### WebSocket Events

#### Client → Server
```javascript
{
  "type": "start_analysis",
  "data": {
    "session_id": "uuid",
    "options": {...}
  }
}
```

#### Server → Client
```javascript
{
  "type": "analysis_progress",
  "data": {
    "progress": 45,
    "stage": "component_detection",
    "message": "Detecting components..."
  }
}
```

## Configuration

### Backend Configuration (`src/config/`)
- **`config.py`**: Main configuration settings
- **`enhanced_config.py`**: Advanced system configuration
- **Environment Variables**: Runtime configuration
- **Validation**: Configuration validation and defaults

### Frontend Configuration
- **`next.config.js`**: Next.js configuration
- **`tailwind.config.ts`**: Tailwind CSS configuration
- **`postcss.config.mjs`**: PostCSS configuration
- **`tsconfig.json`**: TypeScript configuration

### Development Configuration
- **`.env.local`**: Local development environment
- **`.env.example`**: Environment variable template
- **`requirements.txt`**: Python dependencies
- **`package.json`**: Node.js dependencies

## Development Guide

### Getting Started
1. **Clone Repository**: `git clone <repository-url>`
2. **Backend Setup**: 
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Frontend Setup**:
   ```bash
   cd circuit-ai-frontend
   npm install
   ```
4. **Start Services**:
   ```bash
   # Backend
   python -m uvicorn src.api.main:app --reload
   
   # Frontend
   cd circuit-ai-frontend && npm run dev
   ```

### Development Workflow
- **Code Style**: Black, isort, flake8 for Python
- **Type Checking**: mypy for Python, TypeScript for frontend
- **Testing**: pytest for backend, Jest for frontend
- **Linting**: ESLint, Prettier for frontend
- **Git Hooks**: Pre-commit hooks for code quality

### Testing
- **Unit Tests**: Individual component testing
- **Integration Tests**: API endpoint testing
- **E2E Tests**: Full workflow testing
- **Visual Tests**: UI component testing
- **Performance Tests**: Load and stress testing

### Monitoring and Debugging
- **Logging**: Structured logging with loguru
- **Health Checks**: System health monitoring
- **Metrics**: Performance and usage metrics
- **Error Tracking**: Comprehensive error handling
- **Debug Tools**: Development debugging utilities

---

*This documentation serves as a comprehensive knowledge base for the Circuit.AI system, covering all aspects from architecture to deployment.*
