# Foundation Backends

Circuit-AI can run the core API without these packages. Install them when you want
foundation-model assist features for OCR, segmentation, open-vocabulary proposal
generation, and dataset review.

## Installed Smoke-Tested Backends

- PaddleOCR: runs on CPU through `paddlepaddle==3.2.2`; smoke OCR read `ATMEGA328P VII`.
- EasyOCR: runs on CPU; smoke OCR read `ATMEGA328P VIN`.
- SAM 2: `sam2.1_hiera_tiny.pt` is stored at `models/foundation/sam2/sam2.1_hiera_tiny.pt`; CPU mask smoke test passed.
- Grounding DINO: runs through Hugging Face `AutoModelForZeroShotObjectDetection` with `IDEA-Research/grounding-dino-tiny`; synthetic prompt detection passed.
- Florence-2: runs through `microsoft/Florence-2-base` with eager attention and cache disabled; smoke OCR read `ATMEGA328P VIN`.
- supervision: installed for dataset/eval visualization tooling.

## Reproduce

```bash
python3 -m pip install --user --no-deps -r requirements-foundation.txt
mkdir -p models/foundation/sam2
curl -L --fail -o models/foundation/sam2/sam2.1_hiera_tiny.pt \
  https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt
python3 scripts/smoke_foundation_backends.py
python3 scripts/research_tech_radar.py
```

Use `--no-deps` when Torch/torchvision are already installed. Otherwise pip may
try to re-resolve large CUDA wheels through OCR or timm dependencies.

The smoke-test output is written to:

```text
eval/competitive_engine/foundation_backend_smoke.json
```

## Runtime Boundary

Foundation backends are assistive. They can propose text, boxes, masks, captions,
and labels, but production AOI decisions still need trained detectors, golden
references, measurements, or reviewed labels.
