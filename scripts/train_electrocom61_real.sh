#!/bin/bash
# Train Real ElectroCom61 Model
# Trains a production-ready model on the real 61-class ElectroCom61 dataset

set -e

echo "🚀 Training Real ElectroCom61 Model"
echo "==================================="

# Configuration
DATASET_DIR="datasets/electrocom61_real"
MODEL_NAME="electrocom61_v2"
EXPORT_FORMAT="torchscript"

# Check if dataset exists
if [ ! -d "$DATASET_DIR" ]; then
    echo "❌ Dataset not found: $DATASET_DIR"
    echo "💡 Run: ./scripts/setup_electrocom61_real.sh first"
    exit 1
fi

# Check if data.yaml exists
if [ ! -f "$DATASET_DIR/data.yaml" ]; then
    echo "❌ data.yaml not found: $DATASET_DIR/data.yaml"
    exit 1
fi

echo "✅ Found dataset: $DATASET_DIR"

# Validate dataset with YOLO
echo "🔍 Validating dataset..."
source venv/bin/activate

if yolo detect val data="$DATASET_DIR/data.yaml" model=yolov8n.pt imgsz=640 batch=8 > /dev/null 2>&1; then
    echo "✅ Dataset validation passed"
else
    echo "❌ Dataset validation failed"
    echo "💡 Check the dataset structure and data.yaml"
    exit 1
fi

# Get dataset info
NC=$(grep -E "^nc:" "$DATASET_DIR/data.yaml" | awk '{print $2}' | tr -d '[]')
IMG_COUNT=$(find "$DATASET_DIR/images" -name "*.jpg" -o -name "*.png" | wc -l)

echo "📊 Dataset info:"
echo "   Classes: $NC"
echo "   Images: $IMG_COUNT"

# Determine training parameters based on dataset size
if [ "$IMG_COUNT" -gt 2000 ]; then
    echo "🎯 Large dataset detected - using aggressive settings"
    EPOCHS=200
    BATCH=16
    MOSAIC=0.8
    IMGSZ=640
elif [ "$IMG_COUNT" -gt 1000 ]; then
    echo "🎯 Medium dataset detected - using standard settings"
    EPOCHS=150
    BATCH=16
    MOSAIC=0.5
    IMGSZ=640
else
    echo "⚠️ Small dataset detected - using conservative settings"
    EPOCHS=100
    BATCH=8
    MOSAIC=0.3
    IMGSZ=640
fi

echo "🏋️ Training configuration:"
echo "   Model: yolov8m.pt"
echo "   Epochs: $EPOCHS"
echo "   Batch: $BATCH"
echo "   Image size: $IMGSZ"
echo "   Mosaic: $MOSAIC"

# Start training
echo "🚀 Starting training..."
yolo detect train \
    data="$DATASET_DIR/data.yaml" \
    model=yolov8m.pt \
    imgsz=$IMGSZ \
    epochs=$EPOCHS \
    batch=$BATCH \
    lr0=0.01 \
    lrf=0.1 \
    weight_decay=0.0005 \
    mosaic=$MOSAIC \
    hsv_h=0.015 \
    hsv_s=0.7 \
    hsv_v=0.4 \
    project=pcb_runs \
    name=$MODEL_NAME \
    exist_ok=True

if [ $? -eq 0 ]; then
    echo "✅ Training completed successfully!"
else
    echo "❌ Training failed"
    exit 1
fi

# Export model
echo "📦 Exporting model to $EXPORT_FORMAT..."
MODEL_PATH="pcb_runs/$MODEL_NAME/weights/best.pt"

if [ ! -f "$MODEL_PATH" ]; then
    echo "❌ Trained model not found: $MODEL_PATH"
    exit 1
fi

# Create output directory
mkdir -p models/pcb

# Export model
if [ "$EXPORT_FORMAT" = "torchscript" ]; then
    yolo export model="$MODEL_PATH" format=torchscript imgsz=640
    EXPORTED_FILE="pcb_runs/$MODEL_NAME/weights/best.torchscript"
elif [ "$EXPORT_FORMAT" = "onnx" ]; then
    yolo export model="$MODEL_PATH" format=onnx imgsz=640 opset=13 simplify=True
    EXPORTED_FILE="pcb_runs/$MODEL_NAME/weights/best.onnx"
else
    echo "❌ Unsupported export format: $EXPORT_FORMAT"
    exit 1
fi

# Move exported model to models directory
if [ -f "$EXPORTED_FILE" ]; then
    mv "$EXPORTED_FILE" "models/pcb/$MODEL_NAME.$EXPORT_FORMAT"
    echo "✅ Model exported to: models/pcb/$MODEL_NAME.$EXPORT_FORMAT"
else
    echo "❌ Export failed - file not found: $EXPORTED_FILE"
    exit 1
fi

# Create model card
echo "📋 Creating model card..."
cat > "models/pcb/${MODEL_NAME}_card.json" << EOF
{
  "model_name": "$MODEL_NAME",
  "version": "2.0",
  "dataset": {
    "name": "ElectroCom61",
    "classes": $NC,
    "images": $IMG_COUNT,
    "path": "$DATASET_DIR"
  },
  "training": {
    "epochs": $EPOCHS,
    "batch_size": $BATCH,
    "image_size": $IMGSZ,
    "mosaic": $MOSAIC,
    "base_model": "yolov8m.pt"
  },
  "export": {
    "format": "$EXPORT_FORMAT",
    "path": "models/pcb/$MODEL_NAME.$EXPORT_FORMAT"
  },
  "status": "ready_for_deployment"
}
EOF

echo "✅ Model card created: models/pcb/${MODEL_NAME}_card.json"

echo ""
echo "🎉 Training pipeline completed successfully!"
echo "📁 Model: models/pcb/$MODEL_NAME.$EXPORT_FORMAT"
echo "📋 Card: models/pcb/${MODEL_NAME}_card.json"
echo ""
echo "🚀 Next steps:"
echo "   1. Test model: python scripts/evaluate.py --model models/pcb/$MODEL_NAME.$EXPORT_FORMAT"
echo "   2. Deploy to API: Update MODEL_VERSION=$MODEL_NAME"
echo "   3. Set confidence thresholds: Run threshold sweep on validation set"
echo ""
