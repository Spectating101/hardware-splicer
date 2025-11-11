#!/bin/bash
# Setup Real ElectroCom61 Dataset
# Downloads and configures the 61-class ElectroCom61 dataset

set -e

echo "🚀 Setting up Real ElectroCom61 Dataset"
echo "========================================"

# Configuration
DATASET_DIR="datasets/electrocom61_real"
ZIP_FILE="datasets/electrocom61_real.zip"
TEMP_DIR="datasets/electrocom61_real_tmp"

# Check if zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "❌ Zip file not found: $ZIP_FILE"
    echo ""
    echo "📥 Please download the ElectroCom61 dataset:"
    echo "   1. Visit: https://data.mendeley.com/datasets/6scy6h8sjz/2"
    echo "   2. Download the ZIP file"
    echo "   3. Save it as: $ZIP_FILE"
    echo ""
    echo "💡 Alternative: If you have the zip elsewhere, copy it:"
    echo "   cp /path/to/your/electrocom61.zip $ZIP_FILE"
    exit 1
fi

echo "✅ Found zip file: $ZIP_FILE"

# Create directories
echo "📁 Creating directories..."
mkdir -p "$DATASET_DIR"
mkdir -p "$TEMP_DIR"

# Extract zip file
echo "📦 Extracting dataset..."
unzip -q "$ZIP_FILE" -d "$TEMP_DIR"

# Find the actual dataset directory (might be nested)
echo "🔍 Finding dataset structure..."
DATASET_ROOT=""
for dir in "$TEMP_DIR"/*; do
    if [ -d "$dir" ]; then
        # Check if this directory contains images/ and labels/
        if [ -d "$dir/images" ] && [ -d "$dir/labels" ]; then
            DATASET_ROOT="$dir"
            break
        fi
        # Check if this directory contains subdirectories with images/ and labels/
        for subdir in "$dir"/*; do
            if [ -d "$subdir" ] && [ -d "$subdir/images" ] && [ -d "$subdir/labels" ]; then
                DATASET_ROOT="$subdir"
                break
            fi
        done
    fi
done

if [ -z "$DATASET_ROOT" ]; then
    echo "❌ Could not find dataset structure (images/ and labels/ directories)"
    echo "📋 Contents of extracted files:"
    find "$TEMP_DIR" -type d | head -20
    exit 1
fi

echo "✅ Found dataset at: $DATASET_ROOT"

# Copy dataset to final location
echo "📋 Copying dataset to final location..."
rsync -a "$DATASET_ROOT/" "$DATASET_DIR/"

# Check if data.yaml exists
if [ -f "$DATASET_DIR/data.yaml" ]; then
    echo "✅ Found existing data.yaml"
    
    # Check if it has the right number of classes
    NC=$(grep -E "^nc:" "$DATASET_DIR/data.yaml" | awk '{print $2}' | tr -d '[]')
    if [ "$NC" = "61" ]; then
        echo "✅ data.yaml has correct number of classes (61)"
    else
        echo "⚠️ data.yaml has $NC classes, expected 61"
    fi
else
    echo "⚠️ No data.yaml found, creating one..."
    
    # Count images and labels to determine structure
    TRAIN_IMGS=$(find "$DATASET_DIR/images" -name "*.jpg" -o -name "*.png" | wc -l)
    TRAIN_LABELS=$(find "$DATASET_DIR/labels" -name "*.txt" | wc -l)
    
    echo "📊 Found $TRAIN_IMGS images and $TRAIN_LABELS labels"
    
    # Find max class ID
    MAX_CLASS_ID=-1
    for label_file in "$DATASET_DIR/labels"/*.txt; do
        if [ -f "$label_file" ]; then
            while read -r line; do
                if [ -n "$line" ]; then
                    CLASS_ID=$(echo "$line" | awk '{print int($1)}')
                    if [ "$CLASS_ID" -gt "$MAX_CLASS_ID" ]; then
                        MAX_CLASS_ID=$CLASS_ID
                    fi
                fi
            done < "$label_file"
        fi
    done
    
    NUM_CLASSES=$((MAX_CLASS_ID + 1))
    echo "📊 Detected $NUM_CLASSES classes (max class ID: $MAX_CLASS_ID)"
    
    # Create data.yaml
    cat > "$DATASET_DIR/data.yaml" << EOF
# ElectroCom61 Dataset Configuration
# $NUM_CLASSES-class PCB component detection dataset

# Dataset paths
path: $(pwd)/$DATASET_DIR
train: images/train
val: images/val
test: images/test

# Classes ($NUM_CLASSES classes)
nc: $NUM_CLASSES
names:
EOF
    
    # Add class names
    for i in $(seq 0 $MAX_CLASS_ID); do
        echo "  - class$i" >> "$DATASET_DIR/data.yaml"
    done
    
    cat >> "$DATASET_DIR/data.yaml" << EOF

# Additional metadata
description: "ElectroCom61 - $NUM_CLASSES-class PCB component detection dataset"
version: "1.0"
license: "MIT"
url: "https://data.mendeley.com/datasets/6scy6h8sjz/2"
EOF
    
    echo "✅ Created data.yaml with $NUM_CLASSES classes"
fi

# Clean up temp directory
echo "🧹 Cleaning up..."
rm -rf "$TEMP_DIR"

# Validate dataset structure
echo "🔍 Validating dataset structure..."
if [ -d "$DATASET_DIR/images" ] && [ -d "$DATASET_DIR/labels" ]; then
    echo "✅ Dataset structure is correct"
    
    # Count images and labels
    IMG_COUNT=$(find "$DATASET_DIR/images" -name "*.jpg" -o -name "*.png" | wc -l)
    LABEL_COUNT=$(find "$DATASET_DIR/labels" -name "*.txt" | wc -l)
    
    echo "📊 Dataset summary:"
    echo "   Images: $IMG_COUNT"
    echo "   Labels: $LABEL_COUNT"
    echo "   Classes: $(grep -E "^nc:" "$DATASET_DIR/data.yaml" | awk '{print $2}' | tr -d '[]')"
    
    if [ "$IMG_COUNT" -gt 1000 ] && [ "$LABEL_COUNT" -gt 1000 ]; then
        echo "✅ Dataset appears complete and ready for training!"
    else
        echo "⚠️ Dataset appears small, but ready for training"
    fi
else
    echo "❌ Dataset structure is incorrect"
    exit 1
fi

echo ""
echo "🎉 ElectroCom61 dataset setup complete!"
echo "📁 Dataset location: $DATASET_DIR"
echo "📄 Data YAML: $DATASET_DIR/data.yaml"
echo ""
echo "🚀 Next steps:"
echo "   1. Validate: yolo detect val data=$DATASET_DIR/data.yaml model=yolov8n.pt"
echo "   2. Train: yolo detect train data=$DATASET_DIR/data.yaml model=yolov8m.pt epochs=150"
echo ""
