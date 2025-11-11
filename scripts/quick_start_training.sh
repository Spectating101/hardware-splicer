#!/bin/bash

# Circuit.AI Quick Start Training Script
# This script sets up and trains the first working model (ElectroCom61)

set -e  # Exit on any error

echo "🚀 Circuit.AI Quick Start Training"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "src/api/v1/main.py" ]; then
    echo "❌ Error: Please run this script from the Circuit.AI root directory"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Run: source venv/bin/activate"
    exit 1
fi

# Check if ultralytics is installed
if ! python -c "import ultralytics" 2>/dev/null; then
    echo "❌ Error: ultralytics not installed"
    echo "   Run: pip install ultralytics==8.3.0"
    exit 1
fi

echo "✅ Environment check passed"

# Create directories if they don't exist
echo "📁 Creating directories..."
mkdir -p datasets/electrocom61/{images/{train,val,test},labels/{train,val,test}}
mkdir -p models/pcb
mkdir -p pcb_runs

# Check if ElectroCom61 dataset exists
if [ ! -f "datasets/electrocom61/data.yaml" ]; then
    echo "⚠️  Warning: ElectroCom61 dataset not found"
    echo "   Please download and place the dataset in datasets/electrocom61/"
    echo "   Expected structure:"
    echo "   datasets/electrocom61/"
    echo "   ├── data.yaml"
    echo "   ├── images/"
    echo "   │   ├── train/"
    echo "   │   ├── val/"
    echo "   │   └── test/"
    echo "   └── labels/"
    echo "       ├── train/"
    echo "       ├── val/"
    echo "       └── test/"
    echo ""
    echo "   For now, we'll create a minimal dataset for testing..."
    
    # Create a minimal test dataset
    echo "📝 Creating minimal test dataset..."
    
    # Create a simple test image (1x1 pixel)
    python -c "
import numpy as np
from PIL import Image
import os

# Create test directories
os.makedirs('datasets/electrocom61/images/train', exist_ok=True)
os.makedirs('datasets/electrocom61/labels/train', exist_ok=True)

# Create a simple test image
img = Image.new('RGB', (640, 640), color='white')
img.save('datasets/electrocom61/images/train/test.jpg')

# Create a simple test label
with open('datasets/electrocom61/labels/train/test.txt', 'w') as f:
    f.write('0 0.5 0.5 0.1 0.1')  # resistor at center

print('✅ Minimal test dataset created')
"
    
    echo "⚠️  Note: This is a minimal test dataset. For real training, download the full ElectroCom61 dataset."
fi

# Check if we have any images
if [ ! -d "datasets/electrocom61/images/train" ] || [ -z "$(ls -A datasets/electrocom61/images/train 2>/dev/null)" ]; then
    echo "❌ Error: No training images found in datasets/electrocom61/images/train/"
    echo "   Please download the ElectroCom61 dataset or run the script again to create test data"
    exit 1
fi

echo "✅ Dataset structure verified"

# Start training
echo "🏋️  Starting model training..."
echo "   This may take several hours depending on your hardware"
echo "   You can monitor progress in the terminal output"
echo ""

# Run training
python scripts/train_model.py \
    --dataset electrocom61 \
    --data-yaml datasets/electrocom61/data.yaml \
    --project pcb_runs \
    --name electrocom61_v1 \
    --epochs 50 \
    --batch 8 \
    --imgsz 640 \
    --export \
    --export-format onnx \
    --export-dir models/pcb

# Check if training was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Training completed successfully!"
    echo ""
    echo "📊 Results:"
    echo "   Model: pcb_runs/electrocom61_v1/weights/best.pt"
    echo "   Exported: models/pcb/electrocom61_v1.onnx"
    echo ""
    echo "🧪 Testing the model..."
    
    # Test the model
    python -c "
import sys
sys.path.append('src')
from vision.loader import get_detector, get_available_models

print('Available models:', get_available_models())
model = get_detector('electrocom61_v1')
if model:
    print('✅ Model loaded successfully!')
    print('Model info:', model.model)
else:
    print('❌ Failed to load model')
"
    
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Test the API endpoint: curl -X POST http://localhost:8000/v1/analyze-yolo"
    echo "   2. Download real ElectroCom61 dataset for better performance"
    echo "   3. Train FPIC model for v2: python scripts/convert_fpic_to_yolo.py"
    echo "   4. Deploy to production with the trained model"
    echo ""
    echo "📚 Documentation:"
    echo "   - API docs: http://localhost:8000/docs"
    echo "   - Model training: scripts/train_model.py --help"
    echo "   - Dataset conversion: scripts/convert_fpic_to_yolo.py --help"
    
else
    echo "❌ Training failed!"
    echo "   Check the error messages above"
    echo "   Common issues:"
    echo "   - Insufficient GPU memory (try smaller batch size)"
    echo "   - Missing dataset files"
    echo "   - Invalid data.yaml format"
    exit 1
fi

