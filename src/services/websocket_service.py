import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from dataclasses import dataclass, asdict
from datetime import datetime
import threading
import time

@dataclass
class AnalysisProgress:
    analysis_id: str
    step: str
    progress: float
    message: str
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class AnalysisResult:
    analysis_id: str
    success: bool
    result: Dict[str, Any]
    timestamp: datetime
    processing_time: float

class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.analysis_subscriptions: Dict[str, List[str]] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Connect a new WebSocket client."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
            "subscriptions": []
        }
        logger.info(f"WebSocket client {client_id} connected")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connection_established",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        }, client_id)
    
    def disconnect(self, client_id: str):
        """Disconnect a WebSocket client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
        
        # Remove from all subscriptions
        for analysis_id, subscribers in self.analysis_subscriptions.items():
            if client_id in subscribers:
                subscribers.remove(client_id)
        
        logger.info(f"WebSocket client {client_id} disconnected")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
                self.connection_metadata[client_id]["last_activity"] = datetime.now()
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
                self.connection_metadata[client_id]["last_activity"] = datetime.now()
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def subscribe_to_analysis(self, client_id: str, analysis_id: str):
        """Subscribe a client to analysis updates."""
        if analysis_id not in self.analysis_subscriptions:
            self.analysis_subscriptions[analysis_id] = []
        
        if client_id not in self.analysis_subscriptions[analysis_id]:
            self.analysis_subscriptions[analysis_id].append(client_id)
            self.connection_metadata[client_id]["subscriptions"].append(analysis_id)
        
        logger.info(f"Client {client_id} subscribed to analysis {analysis_id}")
    
    async def unsubscribe_from_analysis(self, client_id: str, analysis_id: str):
        """Unsubscribe a client from analysis updates."""
        if analysis_id in self.analysis_subscriptions:
            if client_id in self.analysis_subscriptions[analysis_id]:
                self.analysis_subscriptions[analysis_id].remove(client_id)
        
        if client_id in self.connection_metadata:
            if analysis_id in self.connection_metadata[client_id]["subscriptions"]:
                self.connection_metadata[client_id]["subscriptions"].remove(analysis_id)
        
        logger.info(f"Client {client_id} unsubscribed from analysis {analysis_id}")
    
    async def broadcast_analysis_progress(self, progress: AnalysisProgress):
        """Broadcast analysis progress to subscribed clients."""
        message = {
            "type": "analysis_progress",
            "data": asdict(progress)
        }
        
        analysis_id = progress.analysis_id
        if analysis_id in self.analysis_subscriptions:
            for client_id in self.analysis_subscriptions[analysis_id]:
                await self.send_personal_message(message, client_id)
    
    async def broadcast_analysis_result(self, result: AnalysisResult):
        """Broadcast analysis result to subscribed clients."""
        message = {
            "type": "analysis_complete",
            "data": asdict(result)
        }
        
        analysis_id = result.analysis_id
        if analysis_id in self.analysis_subscriptions:
            for client_id in self.analysis_subscriptions[analysis_id]:
                await self.send_personal_message(message, client_id)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "active_connections": len(self.active_connections),
            "total_subscriptions": sum(len(subscribers) for subscribers in self.analysis_subscriptions.values()),
            "active_analyses": len(self.analysis_subscriptions),
            "connections": [
                {
                    "client_id": client_id,
                    "connected_at": metadata["connected_at"].isoformat(),
                    "last_activity": metadata["last_activity"].isoformat(),
                    "subscriptions": len(metadata["subscriptions"])
                }
                for client_id, metadata in self.connection_metadata.items()
            ]
        }

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

class AnalysisProgressTracker:
    """Tracks and broadcasts analysis progress in real-time."""
    
    def __init__(self, analysis_id: str):
        self.analysis_id = analysis_id
        self.steps = [
            ("uploading", "Uploading image...", 0.1),
            ("preprocessing", "Preprocessing image...", 0.2),
            ("detecting", "Detecting components...", 0.4),
            ("analyzing", "Analyzing capabilities...", 0.6),
            ("mapping", "Mapping functionality...", 0.8),
            ("recommending", "Generating recommendations...", 0.9),
            ("finalizing", "Finalizing results...", 1.0)
        ]
        self.current_step = 0
        self.start_time = time.time()
    
    async def update_progress(self, step_name: str, message: str, progress: float, metadata: Dict[str, Any] = None):
        """Update and broadcast progress."""
        progress_data = AnalysisProgress(
            analysis_id=self.analysis_id,
            step=step_name,
            progress=progress,
            message=message,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        await websocket_manager.broadcast_analysis_progress(progress_data)
        logger.info(f"Analysis {self.analysis_id}: {step_name} - {progress:.1%}")
    
    async def complete_analysis(self, result: Dict[str, Any], success: bool = True):
        """Complete analysis and broadcast result."""
        processing_time = time.time() - self.start_time
        
        result_data = AnalysisResult(
            analysis_id=self.analysis_id,
            success=success,
            result=result,
            timestamp=datetime.now(),
            processing_time=processing_time
        )
        
        await websocket_manager.broadcast_analysis_result(result_data)
        logger.info(f"Analysis {self.analysis_id} completed in {processing_time:.2f}s")
    
    async def simulate_progress(self):
        """Simulate analysis progress for demo purposes."""
        for step_name, message, target_progress in self.steps:
            await self.update_progress(step_name, message, target_progress)
            await asyncio.sleep(1)  # Simulate processing time
