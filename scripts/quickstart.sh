#!/bin/bash
# Circuit.AI - Quick Start Script
# Launches backend, frontend, and provides access URLs

set -e

PROJECT_DIR="/home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI"
VENV_PATH="$PROJECT_DIR/venv/bin/activate"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         Circuit.AI - Quick Start & MVP Launch               ║"
echo "║                                                               ║"
echo "║  Status: ✅ Ready for Deployment                            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check if we're in the right directory
if [ ! -f "$VENV_PATH" ]; then
    echo "❌ Error: Virtual environment not found at $VENV_PATH"
    echo "Please run from: $PROJECT_DIR"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH"

echo "📋 Pre-flight Checks:"
echo ""

# Check database
if [ -f "data/circuit_ai.db" ]; then
    DB_SIZE=$(ls -lh data/circuit_ai.db | awk '{print $5}')
    echo "✅ Database: $DB_SIZE"
else
    echo "❌ Database not found - run: sqlite3 data/circuit_ai.db < db/schema_sqlite.sql"
    exit 1
fi

# Check model
if [ -f "models/yolov8n.pt" ]; then
    echo "✅ Model: YOLOv8n ready"
else
    echo "❌ Model not found - run: python -c \"from ultralytics import YOLO; YOLO('yolov8n.pt')\""
    exit 1
fi

# Check .env
if [ -f ".env" ]; then
    echo "✅ Configuration: .env found"
else
    echo "⚠️  Warning: .env not found - using defaults"
fi

# Check frontend
if [ -d "circuit-ai-frontend" ]; then
    echo "✅ Frontend: Ready"
else
    echo "⚠️  Warning: Frontend directory not found"
fi

echo ""
echo "🚀 Starting Services:"
echo ""

# Kill any existing processes on ports
echo "🧹 Cleaning up old processes..."
lsof -i :8000 -sTCP:LISTEN 2>/dev/null | grep -v COMMAND | awk '{print $2}' | xargs kill -9 2>/dev/null || true
lsof -i :3000 -sTCP:LISTEN 2>/dev/null | grep -v COMMAND | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 1

# Create log directories
mkdir -p logs

# Start backend
echo "📡 Starting Backend API (port 8000)..."
nohup python -m uvicorn src.api.v1.main:app --host 0.0.0.0 --port 8000 --reload > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"
sleep 3

# Check if backend started successfully
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Backend failed to start!"
    echo "Check logs: tail -f logs/backend.log"
    exit 1
fi
echo "   ✅ Backend running"

# Start frontend (if npm is available)
if command -v npm &> /dev/null; then
    echo "🎨 Starting Frontend (port 3000)..."
    cd circuit-ai-frontend
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "   📦 Installing npm dependencies..."
        npm install > /dev/null 2>&1
    fi
    
    # Start frontend
    nohup npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "   Frontend PID: $FRONTEND_PID"
    sleep 5
    cd ..
    
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "   ✅ Frontend running"
    else
        echo "   ⚠️  Frontend may not be ready yet"
    fi
else
    echo "⚠️  npm not found - skipping frontend"
    echo "   Start manually: cd circuit-ai-frontend && npm run dev"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 MVP READY TO USE!                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

echo "📍 Access Points:"
echo "   Frontend:      http://localhost:3000"
echo "   Backend API:   http://localhost:8000"
echo "   API Docs:      http://localhost:8000/docs"
echo "   ReDoc:         http://localhost:8000/redoc"
echo "   Health Check:  http://localhost:8000/health"
echo ""

echo "📊 Test Commands:"
echo ""
echo "   # Health check:"
echo "   curl http://localhost:8000/health"
echo ""
echo "   # Get component classes:"
echo "   curl http://localhost:8000/v1/components/classes | head -20"
echo ""
echo "   # Analyze image (create test.jpg first):"
echo "   curl -X POST \"http://localhost:8000/v1/analyze-yolo\" -F \"file=@test.jpg\""
echo ""

echo "📚 Documentation:"
echo "   • MVP_DEPLOYMENT.md - Comprehensive deployment guide"
echo "   • TRAINING_AND_DEPLOYMENT.md - Model training instructions"
echo "   • IMPLEMENTATION_GUIDE.md - Implementation details"
echo ""

echo "📋 View Logs:"
echo "   Backend:  tail -f logs/backend.log"
echo "   Frontend: tail -f logs/frontend.log"
echo ""

echo "⏹️  To stop all services:"
echo "   kill $BACKEND_PID $(pgrep -f 'npm run dev' || echo '')"
echo ""

echo "💡 Next Steps:"
echo "   1. Open http://localhost:3000 in browser"
echo "   2. Test file upload functionality"
echo "   3. Try analyzing PCB images"
echo "   4. Check API docs at http://localhost:8000/docs"
echo ""

# Keep script running to show status
while true; do
    # Check if services are still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "⚠️  Backend process died! Restart with: python -m uvicorn src.api.v1.main:app --host 0.0.0.0 --port 8000"
    fi
    
    sleep 30
done
