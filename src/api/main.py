from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import uvicorn

from .v1.main import app as v1_app
from .websocket_handler import websocket_handler
from ..config import settings

# Initialize main FastAPI app
app = FastAPI(
    title="Circuit.AI API",
    description="Enterprise-grade PCB analysis API platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
# Configure allowed origins from environment or use safe defaults
allowed_origins = settings.cors_origins if hasattr(settings, 'cors_origins') else [
    "http://localhost:3000",      # Local development
    "http://localhost:8000",      # Local backend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight for 1 hour
)

# Include API v1 routes
app.include_router(v1_app, prefix="/v1", tags=["v1"])

# WebSocket endpoint for real-time interactive repair
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time interactive repair guidance."""
    await websocket_handler.handle_connection(websocket, client_id)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Circuit.AI Enterprise PCB Analysis API Platform",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "api_version": "v1",
        "endpoints": {
            "v1": "/v1 - Current API version",
            "health": "/v1/health - API health check",
            "analyze": "/v1/analyze - PCB analysis endpoint",
            "components": "/v1/components - Component information",
            "projects": "/v1/projects - Project templates",
            "educational": "/v1/educational/{component_id} - Educational content",
            "analyses": "/v1/analyses - Analysis history",
            "usage": "/v1/usage - API usage statistics"
        },
        "authentication": {
            "type": "API Key",
            "header": "Authorization: Bearer YOUR_API_KEY"
        },
        "rate_limits": {
            "free": "10 requests/minute, 100/hour",
            "pro": "60 requests/minute, 1000/hour", 
            "enterprise": "300 requests/minute, 5000/hour"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "Circuit.AI API"
    }

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)