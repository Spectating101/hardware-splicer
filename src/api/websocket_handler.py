"""
WebSocket Handler for Real-time Interactive Repair

Enables real-time bidirectional communication for:
- Streaming video from user's camera/microscope
- Live component detection overlay
- Interactive chatbot conversation
- Step-by-step repair guidance
"""

import asyncio
import json
import base64
from typing import Dict, Optional, Set
import cv2
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from src.vision.enhanced_detector import enhanced_detector
from src.intelligence.interactive_repair_chatbot import interactive_repair_chatbot
from src.intelligence.visual_overlay import visual_overlay_renderer
from src.intelligence.connection_mapper import connection_mapper


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        """Initialize manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.conversations: Dict[str, str] = {}  # client_id -> conversation_id

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        """Remove disconnected client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.conversations:
            del self.conversations[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def send_message(self, client_id: str, message: dict):
        """Send message to specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        for client_id, websocket in self.active_connections.items():
            await websocket.send_json(message)


manager = ConnectionManager()


class WebSocketHandler:
    """Handle WebSocket messages for interactive repair."""

    def __init__(self):
        """Initialize handler."""
        self.frame_skip = 2  # Process every Nth frame
        self.frame_counter: Dict[str, int] = {}

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        """
        Handle WebSocket connection lifecycle.

        Message types:
        - "video_frame": Base64 encoded frame from camera
        - "chat_message": User message for chatbot
        - "start_repair": Start new repair session
        - "get_history": Get conversation history
        """
        await manager.connect(websocket, client_id)

        self.frame_counter[client_id] = 0

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()

                message_type = data.get('type')

                if message_type == 'video_frame':
                    await self._handle_video_frame(client_id, data)

                elif message_type == 'chat_message':
                    await self._handle_chat_message(client_id, data)

                elif message_type == 'start_repair':
                    await self._handle_start_repair(client_id, data)

                elif message_type == 'get_history':
                    await self._handle_get_history(client_id)

                elif message_type == 'ping':
                    await manager.send_message(client_id, {'type': 'pong'})

                else:
                    logger.warning(f"Unknown message type: {message_type}")

        except WebSocketDisconnect:
            manager.disconnect(client_id)
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
            manager.disconnect(client_id)

    async def _handle_video_frame(self, client_id: str, data: dict):
        """
        Process video frame and return annotated frame.

        Expected data:
        {
            "type": "video_frame",
            "frame": "<base64 encoded image>",
            "timestamp": 1234567890
        }
        """
        # Skip frames for performance
        self.frame_counter[client_id] = (self.frame_counter[client_id] + 1) % self.frame_skip
        if self.frame_counter[client_id] != 0:
            return

        try:
            # Decode frame
            frame_b64 = data.get('frame')
            frame_bytes = base64.b64decode(frame_b64)
            frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is None:
                return

            # Detect components
            detections = enhanced_detector.detect(frame)

            # Create overlay
            annotated = frame.copy()

            # Draw bounding boxes and labels
            for det in detections:
                x1, y1, x2, y2 = det['bbox']
                label = det['label']
                confidence = det['confidence']

                # Draw box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Draw label
                label_text = f"{label} {confidence:.2f}"
                cv2.putText(annotated, label_text, (x1, y1 - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Encode annotated frame
            _, buffer = cv2.imencode('.jpg', annotated)
            annotated_b64 = base64.b64encode(buffer).decode('utf-8')

            # Send back
            await manager.send_message(client_id, {
                'type': 'video_frame_result',
                'frame': annotated_b64,
                'detections': detections,
                'timestamp': data.get('timestamp')
            })

        except Exception as e:
            logger.error(f"Error processing video frame: {e}")

    async def _handle_chat_message(self, client_id: str, data: dict):
        """
        Handle chatbot message.

        Expected data:
        {
            "type": "chat_message",
            "message": "The LED is on",
            "metadata": {"voltage": 5.1}  # Optional
        }
        """
        try:
            user_message = data.get('message')
            metadata = data.get('metadata')

            # Get or create conversation
            if client_id not in manager.conversations:
                # No active conversation
                await manager.send_message(client_id, {
                    'type': 'error',
                    'message': 'No active repair session. Start a repair first.'
                })
                return

            conversation_id = manager.conversations[client_id]

            # Send to chatbot
            bot_response = interactive_repair_chatbot.send_message(
                conversation_id, user_message, metadata
            )

            # Get conversation state
            conversation = interactive_repair_chatbot.conversations[conversation_id]

            # Send response
            await manager.send_message(client_id, {
                'type': 'chat_response',
                'message': bot_response,
                'state': conversation.state.value,
                'measurements': conversation.measurements,
                'findings': conversation.findings
            })

        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            await manager.send_message(client_id, {
                'type': 'error',
                'message': str(e)
            })

    async def _handle_start_repair(self, client_id: str, data: dict):
        """
        Start new repair session.

        Expected data:
        {
            "type": "start_repair",
            "device_type": "Arduino Uno",
            "symptoms": ["won't upload", "USB not recognized"],
            "image": "<base64 encoded PCB image>"  # Optional
        }
        """
        try:
            device_type = data.get('device_type')
            symptoms = data.get('symptoms', [])
            image_b64 = data.get('image')

            # Create conversation ID
            conversation_id = f"{client_id}_{len(manager.conversations)}"

            # Analyze image if provided
            schematic = None
            if image_b64:
                # Decode image
                image_bytes = base64.b64decode(image_b64)
                image_array = np.frombuffer(image_bytes, dtype=np.uint8)
                image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

                # Detect components
                detections = enhanced_detector.detect(image)

                # Build schematic (simplified)
                from src.intelligence.connection_mapper import CircuitSchematic
                schematic = CircuitSchematic(
                    ics=[],
                    connections=[],
                    nets=[],
                    power_rails={"VCC_5V": 5.0},
                    ground_pins=[],
                    unconnected_pins=[],
                    confidence=0.5
                )

            # Start conversation
            response = interactive_repair_chatbot.start_conversation(
                conversation_id, device_type, schematic or self._create_default_schematic(), symptoms
            )

            # Save conversation ID
            manager.conversations[client_id] = conversation_id

            # Send response
            await manager.send_message(client_id, {
                'type': 'repair_started',
                'conversation_id': conversation_id,
                'message': response
            })

        except Exception as e:
            logger.error(f"Error starting repair: {e}")
            await manager.send_message(client_id, {
                'type': 'error',
                'message': str(e)
            })

    async def _handle_get_history(self, client_id: str):
        """Get conversation history."""
        try:
            if client_id not in manager.conversations:
                await manager.send_message(client_id, {
                    'type': 'history',
                    'messages': []
                })
                return

            conversation_id = manager.conversations[client_id]
            history = interactive_repair_chatbot.get_conversation_history(conversation_id)

            await manager.send_message(client_id, {
                'type': 'history',
                'messages': history
            })

        except Exception as e:
            logger.error(f"Error getting history: {e}")

    def _create_default_schematic(self):
        """Create default empty schematic."""
        from src.intelligence.connection_mapper import CircuitSchematic
        return CircuitSchematic(
            ics=[],
            connections=[],
            nets=[],
            power_rails={},
            ground_pins=[],
            unconnected_pins=[],
            confidence=0.0
        )


# Global handler
websocket_handler = WebSocketHandler()
