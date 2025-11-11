#!/usr/bin/env python3
"""
Enhanced Circuit.AI System Startup Script
Initializes and runs the complete enhanced system with all features.
"""

import asyncio
import sys
import os
import signal
import time
from pathlib import Path
from typing import Dict, Any
import uvicorn
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.enhanced_config import enhanced_settings
from src.services.queue_service import queue_service
from src.services.cache_service import cache_service
from src.services.websocket_service import websocket_manager
from src.core.enhanced_analyzer import enhanced_analyzer
from src.vision.enhanced_detector import enhanced_detector
from src.llm.enhanced_mapper import enhanced_mapper

class EnhancedCircuitAISystem:
    """Enhanced Circuit.AI system manager."""
    
    def __init__(self):
        self.services = {}
        self.running = False
        self.startup_time = None
        
    async def initialize_system(self):
        """Initialize all system components."""
        logger.info("🚀 Initializing Enhanced Circuit.AI System...")
        
        try:
            # Validate configuration
            warnings = enhanced_settings.validate_settings()
            if warnings:
                logger.warning("Configuration warnings found:")
                for warning in warnings:
                    logger.warning(f"  - {warning}")
            else:
                logger.info("✅ Configuration validation passed")
            
            # Initialize cache service
            logger.info("📦 Initializing cache service...")
            cache_config = enhanced_settings.get_cache_config()
            # Cache service is already initialized as a global instance
            logger.info("✅ Cache service initialized")
            
            # Initialize queue service
            logger.info("🔄 Initializing job queue service...")
            queue_config = enhanced_settings.get_queue_config()
            # Queue service is already initialized as a global instance
            logger.info("✅ Job queue service initialized")
            
            # Initialize enhanced detector
            logger.info("🔍 Initializing enhanced computer vision...")
            detection_config = enhanced_settings.get_detection_config()
            # Enhanced detector is already initialized as a global instance
            logger.info("✅ Enhanced computer vision initialized")
            
            # Initialize enhanced mapper
            logger.info("🧠 Initializing enhanced AI mapper...")
            llm_config = enhanced_settings.get_llm_config()
            # Enhanced mapper is already initialized as a global instance
            logger.info("✅ Enhanced AI mapper initialized")
            
            # Initialize enhanced analyzer
            logger.info("⚡ Initializing enhanced analyzer...")
            # Enhanced analyzer is already initialized as a global instance
            logger.info("✅ Enhanced analyzer initialized")
            
            # Start queue workers
            logger.info("👥 Starting queue workers...")
            queue_service.start_workers()
            logger.info(f"✅ Started {enhanced_settings.queue_max_workers} queue workers")
            
            # Initialize WebSocket manager
            logger.info("🌐 Initializing WebSocket manager...")
            websocket_config = enhanced_settings.get_websocket_config()
            if websocket_config["enabled"]:
                logger.info("✅ WebSocket manager initialized")
            else:
                logger.warning("⚠️ WebSocket disabled in configuration")
            
            # Create necessary directories
            logger.info("📁 Creating necessary directories...")
            directories = [
                enhanced_settings.data_dir,
                enhanced_settings.models_dir,
                enhanced_settings.cache_dir,
                enhanced_settings.temp_dir,
                enhanced_settings.upload_dir
            ]
            
            for directory in directories:
                Path(directory).mkdir(parents=True, exist_ok=True)
            
            logger.info("✅ Directories created")
            
            # System health check
            logger.info("🏥 Performing system health check...")
            health = enhanced_analyzer.get_system_health()
            logger.info(f"✅ System health: {health['status']}")
            
            self.startup_time = time.time()
            logger.info("🎉 Enhanced Circuit.AI System initialization complete!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}")
            return False
    
    async def start_api_server(self):
        """Start the FastAPI server."""
        logger.info("🌐 Starting Enhanced API server...")
        
        try:
            # Import the enhanced API
            from src.api.enhanced_api import app
            
            # Configure uvicorn
            config = uvicorn.Config(
                app=app,
                host=enhanced_settings.host,
                port=enhanced_settings.port,
                workers=enhanced_settings.workers,
                log_level=enhanced_settings.log_level.lower(),
                access_log=True,
                reload=enhanced_settings.debug
            )
            
            # Create and start server
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            logger.error(f"❌ API server failed to start: {e}")
            raise
    
    async def run_system(self):
        """Run the complete enhanced system."""
        logger.info("🚀 Starting Enhanced Circuit.AI System...")
        
        # Initialize system
        if not await self.initialize_system():
            logger.error("❌ System initialization failed")
            return False
        
        self.running = True
        
        try:
            # Start API server
            await self.start_api_server()
            
        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal")
        except Exception as e:
            logger.error(f"❌ System error: {e}")
        finally:
            await self.shutdown_system()
    
    async def shutdown_system(self):
        """Gracefully shutdown the system."""
        if not self.running:
            return
        
        logger.info("🛑 Shutting down Enhanced Circuit.AI System...")
        
        try:
            # Stop queue workers
            logger.info("👥 Stopping queue workers...")
            queue_service.stop_workers()
            logger.info("✅ Queue workers stopped")
            
            # Close WebSocket connections
            logger.info("🌐 Closing WebSocket connections...")
            for client_id in list(websocket_manager.active_connections.keys()):
                websocket_manager.disconnect(client_id)
            logger.info("✅ WebSocket connections closed")
            
            # Clear cache
            logger.info("📦 Clearing cache...")
            cache_service.clear()
            logger.info("✅ Cache cleared")
            
            if self.startup_time:
                uptime = time.time() - self.startup_time
                logger.info(f"⏱️ System uptime: {uptime:.2f} seconds")
            
            self.running = False
            logger.info("✅ Enhanced Circuit.AI System shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        if not self.running:
            return {"status": "not_running"}
        
        try:
            return {
                "status": "running",
                "uptime": time.time() - self.startup_time if self.startup_time else 0,
                "health": enhanced_analyzer.get_system_health(),
                "statistics": enhanced_analyzer.get_analysis_statistics(),
                "cache_stats": cache_service.get_stats(),
                "queue_stats": queue_service.get_queue_stats(),
                "websocket_stats": websocket_manager.get_connection_stats(),
                "configuration": {
                    "environment": enhanced_settings.environment,
                    "debug": enhanced_settings.debug,
                    "features": {
                        "websocket": enhanced_settings.feature_websocket,
                        "batch_analysis": enhanced_settings.feature_batch_analysis,
                        "educational_content": enhanced_settings.feature_educational_content,
                        "repair_guides": enhanced_settings.feature_repair_guides,
                        "advanced_analytics": enhanced_settings.feature_advanced_analytics,
                        "real_time_progress": enhanced_settings.feature_real_time_progress
                    }
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"🛑 Received signal {signum}")
    sys.exit(0)

async def main():
    """Main entry point."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format=enhanced_settings.log_format,
        level=enhanced_settings.log_level,
        colorize=True
    )
    
    if enhanced_settings.log_file:
        logger.add(
            enhanced_settings.log_file,
            format=enhanced_settings.log_format,
            level=enhanced_settings.log_level,
            rotation=enhanced_settings.log_rotation,
            retention=enhanced_settings.log_retention
        )
    
    # Create and run system
    system = EnhancedCircuitAISystem()
    
    try:
        await system.run_system()
    except Exception as e:
        logger.error(f"❌ Fatal system error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the system
    asyncio.run(main())

