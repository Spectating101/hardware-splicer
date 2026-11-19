#!/bin/bash

# Configuration
SOURCE_DIR="./circuit_ai_upgrade"
TARGET_DIR="../Circuit-AI"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Circuit-AI Full Stack Upgrade Installer ===${NC}"
echo "Source: $SOURCE_DIR"
echo "Target: $TARGET_DIR"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Target directory not found at $TARGET_DIR"
    exit 1
fi

# 1. FRONTEND UPGRADE
echo -e "\n${BLUE}1. Upgrading Frontend (Circuit IDE)...${NC}"
mkdir -p "$TARGET_DIR/circuit-ai-frontend/components/cad"
mkdir -p "$TARGET_DIR/circuit-ai-frontend/app/cad"
mkdir -p "$TARGET_DIR/circuit-ai-frontend/components/cad"
cp -v "$SOURCE_DIR/components/cad/pcb-viewport.tsx" "$TARGET_DIR/circuit-ai-frontend/components/cad/"
cp -v "$SOURCE_DIR/components/cad/spatial-ui.tsx" "$TARGET_DIR/circuit-ai-frontend/components/cad/"
cp -v "$SOURCE_DIR/app/cad/page.tsx" "$TARGET_DIR/circuit-ai-frontend/app/cad/"

# 2. BACKEND UPGRADE
echo -e "\n${BLUE}2. Installing Backend Engines...${NC}"

# CAM & Robot Control
mkdir -p "$TARGET_DIR/src/engines/cam"
cp -v "$SOURCE_DIR/backend_stub/gcode_engine.py" "$TARGET_DIR/src/engines/cam/"
cp -v "$SOURCE_DIR/backend_stub/robot_driver.py" "$TARGET_DIR/src/engines/cam/"
cp -v "$SOURCE_DIR/backend_stub/repair_orchestrator.py" "$TARGET_DIR/src/engines/cam/"
touch "$TARGET_DIR/src/engines/cam/__init__.py"

# Generative & Routing
mkdir -p "$TARGET_DIR/src/engines/generative"
cp -v "$SOURCE_DIR/backend_stub/routing_engine.py" "$TARGET_DIR/src/engines/generative/"
cp -v "$SOURCE_DIR/backend_stub/generative_design_agent.py" "$TARGET_DIR/src/engines/generative/"
touch "$TARGET_DIR/src/engines/generative/__init__.py"

# MCP Server (Monetization Layer)
cp -v "$SOURCE_DIR/backend_stub/circuit_ai_mcp.py" "$TARGET_DIR/src/engines/circuit_ai_mcp.py"

# 3. DOCUMENTATION UPGRADE
echo -e "\n${BLUE}3. Deploying Documentation...${NC}"
cp -v "$SOURCE_DIR/INTERFACE_UPGRADE_DOCUMENTATION.md" "$TARGET_DIR/"
cp -v "$SOURCE_DIR/USER_STORY_LAYMAN.md" "$TARGET_DIR/"
cp -v "$SOURCE_DIR/USER_SCENARIOS.md" "$TARGET_DIR/"


echo -e "\n${GREEN}Success! The system is now Fully Integrated.${NC}"
echo "Frontend: Circuit IDE installed at /cad"
echo "Backend:  CAM Engine installed at src/engines/cam/"
echo "Backend:  Generative Engine installed at src/engines/generative/"
echo "MCP:      Server installed at src/engines/circuit_ai_mcp.py"
echo "Docs:     INTERFACE_UPGRADE_DOCUMENTATION.md"cp -v ./circuit_ai_upgrade/backend_stub/enhanced_mapper.py ../Circuit-AI/src/llm/enhanced_mapper.py
cp -v ./circuit_ai_upgrade/backend_stub/splicer_engine.py ../Circuit-AI/src/engines/cam/splicer_engine.py
cp -v ./circuit_ai_upgrade/backend_stub/knowledge_bridge.py ../Circuit-AI/src/engines/generative/knowledge_bridge.py
